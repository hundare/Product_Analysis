import os
import json
import asyncio
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from mcp.server import Server
from mcp.types import Tool, TextContent


# ==================== Models ====================

# ISO 3166-1 alpha-2 country codes supported by Brave Search
BRAVE_COUNTRY_CODES = {
    "USA": "us", "UK": "gb", "CANADA": "ca", "AUSTRALIA": "au",
    "GERMANY": "de", "FRANCE": "fr", "INDIA": "in", "JAPAN": "jp",
    "BRAZIL": "br", "MEXICO": "mx", "SPAIN": "es", "ITALY": "it",
}


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(5, ge=1, le=10)
    country: str | None = Field(None, description="Country for geo-targeted results (e.g. USA, UK, INDIA)")


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class SearchResultObj:
    """Internal result object for consistency"""

    def __init__(self, title: str, url: str, snippet: str):
        self.title = title
        self.url = url
        self.snippet = snippet

    def to_dict(self) -> dict[str, str]:
        return {"title": self.title, "url": self.url, "snippet": self.snippet}

    def to_model(self) -> SearchResult:
        return SearchResult(title=self.title, url=self.url, snippet=self.snippet)


# ==================== Search Logic ====================

def parse_duckduckgo_html(html: str, limit: int) -> list[SearchResultObj]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[SearchResultObj] = []

    for a in soup.select("a.result__a")[:limit]:
        title = a.get_text(" ", strip=True)
        href = a.get("href", "")
        snippet = ""

        parent = a.find_parent("div", class_="result__body")
        if parent:
            snippet_tag = parent.select_one(".result__snippet")
            if snippet_tag:
                snippet = snippet_tag.get_text(" ", strip=True)

        if href:
            results.append(
                SearchResultObj(title=title, url=decode_duckduckgo_url(href), snippet=snippet)
            )

    return results


def decode_duckduckgo_url(href: str) -> str:
    parsed = urlparse(href)
    if parsed.scheme in {"http", "https"}:
        return href

    if "uddg=" in href:
        values = parse_qs(parsed.query)
        if "uddg" in values and values["uddg"]:
            return values["uddg"][0]

    return href


def search_brave(query: str, limit: int, country: str | None = None) -> list[SearchResultObj]:
    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        return []

    params: dict[str, Any] = {"q": query, "count": limit}
    if country:
        country_code = BRAVE_COUNTRY_CODES.get(country.upper())
        if country_code:
            params["country"] = country_code

    try:
        response = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"X-Search-Api-Key": api_key},
            params=params,
            timeout=15.0,
        )
        response.raise_for_status()
        payload = response.json()

        results: list[SearchResultObj] = []
        for item in payload.get("web", {}).get("results", [])[:limit]:
            results.append(
                SearchResultObj(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                )
            )
        return results
    except Exception:
        return []


def search_web(query: str, limit: int, country: str | None = None) -> list[SearchResultObj]:
    brave_results = search_brave(query, limit, country)
    if brave_results:
        return brave_results

    # DuckDuckGo fallback: append country to query string since HTML endpoint has no geo param
    ddg_query = f"{query} site:.{BRAVE_COUNTRY_CODES.get(country.upper(), '')}" if country and BRAVE_COUNTRY_CODES.get((country or "").upper()) else query
    try:
        response = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": ddg_query},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15.0,
        )
        response.raise_for_status()
        return parse_duckduckgo_html(response.text, limit)
    except httpx.HTTPError:
        return []


# ==================== FastAPI HTTP Endpoints ====================

app = FastAPI(title="Web Search MCP", version="1.0.0")


@app.get("/")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "web-search-mcp", "mode": "http+mcp"}


@app.post("/search", response_model=list[SearchResult])
def search_endpoint(req: SearchRequest) -> list[SearchResult]:
    try:
        results = search_web(req.query, req.limit, req.country)
        return [r.to_model() for r in results]
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"search provider error: {exc}") from exc


# ==================== MCP Server ====================

server = Server("web-search-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="web_search",
            description="Search the web for information. Returns top results with title, URL, and snippet.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of results to return (1-10)",
                        "default": 5,
                    },
                    "country": {
                        "type": "string",
                        "description": "Country for geo-targeted results (e.g. USA, UK, INDIA, GERMANY)",
                    },
                },
                "required": ["query"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name != "web_search":
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    query = arguments.get("query", "").strip()
    if not query:
        return [TextContent(type="text", text="Error: query is required")]

    limit = min(int(arguments.get("limit", 5)), 10)
    country: str | None = arguments.get("country")

    try:
        results = search_web(query, limit, country)
        if not results:
            return [TextContent(type="text", text="No results found")]

        results_json = json.dumps([r.to_dict() for r in results], indent=2)
        return [TextContent(type="text", text=results_json)]
    except Exception as e:
        return [TextContent(type="text", text=f"Search error: {str(e)}")]


# ==================== Entry Points ====================

if __name__ == "__main__":
    import uvicorn

    # Start FastAPI server on HTTP port
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)

