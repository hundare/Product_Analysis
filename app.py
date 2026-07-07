import os
import json
import asyncio
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from mcp.server import Server
from mcp.types import Tool, TextContent

load_dotenv()


# ==================== Models ====================

# Country names used for geo-targeting via Tavily query context
COUNTRY_NAMES = {
    "USA": "United States", "UK": "United Kingdom", "CANADA": "Canada",
    "AUSTRALIA": "Australia", "GERMANY": "Germany", "FRANCE": "France",
    "INDIA": "India", "JAPAN": "Japan", "BRAZIL": "Brazil",
    "MEXICO": "Mexico", "SPAIN": "Spain", "ITALY": "Italy",
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
            parsed = urlparse(href)
            if parsed.scheme not in {"http", "https"} and "uddg=" in href:
                values = parse_qs(parsed.query)
                href = values["uddg"][0] if "uddg" in values and values["uddg"] else href
            results.append(SearchResultObj(title=title, url=href, snippet=snippet))
    return results


def search_tavily(query: str, limit: int, country: str | None = None) -> list[SearchResultObj]:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise EnvironmentError("TAVILY_API_KEY environment variable is not set")

    # Append country context to query for geo-targeted results
    if country:
        country_name = COUNTRY_NAMES.get(country.upper())
        if country_name:
            query = f"{query} in {country_name}"

    payload: dict[str, Any] = {
        "api_key": api_key,
        "query": query,
        "max_results": limit,
        "search_depth": "advanced",
        "include_answer": False,
        "include_raw_content": False,
    }

    response = httpx.post(
        "https://api.tavily.com/search",
        json=payload,
        timeout=20.0,
    )
    response.raise_for_status()
    data = response.json()

    results: list[SearchResultObj] = []
    for item in data.get("results", [])[:limit]:
        results.append(
            SearchResultObj(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
            )
        )
    return results


def search_web(query: str, limit: int, country: str | None = None) -> list[SearchResultObj]:
    tavily_error: str | None = None

    try:
        results = search_tavily(query, limit, country)
        if results:
            return results
    except Exception as e:
        tavily_error = str(e)

    # DuckDuckGo fallback
    country_name = COUNTRY_NAMES.get((country or "").upper(), "")
    ddg_query = f"{query} in {country_name}" if country_name else query
    try:
        response = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": ddg_query},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
            timeout=15.0,
        )
        response.raise_for_status()
        ddg_results = parse_duckduckgo_html(response.text, limit)
        if ddg_results:
            return ddg_results
    except Exception:
        pass

    detail = f"Tavily: {tavily_error}. DuckDuckGo: returned no results (may be blocked by cloud IP)." if tavily_error else "DuckDuckGo returned no results (may be blocked by cloud IP)."
    raise RuntimeError(detail)


# ==================== FastAPI HTTP Endpoints ====================

app = FastAPI(title="Web Search MCP", version="1.0.0")


@app.get("/")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "web-search-mcp",
        "mode": "http+mcp",
        "tavily_api_key_set": bool(os.getenv("TAVILY_API_KEY")),
    }


@app.post("/search", response_model=list[SearchResult])
def search_endpoint(req: SearchRequest) -> list[SearchResult]:
    try:
        results = search_web(req.query, req.limit, req.country)
        return [r.to_model() for r in results]
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
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

