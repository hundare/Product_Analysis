import os
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Web Search MCP", version="1.0.0")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(5, ge=1, le=10)


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class MCPRequest(BaseModel):
    tool: str | None = None
    method: str | None = None
    arguments: dict[str, Any] | None = None


def parse_duckduckgo_html(html: str, limit: int) -> list[SearchResult]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[SearchResult] = []

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
            results.append(SearchResult(title=title, url=decode_duckduckgo_url(href), snippet=snippet))

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


def search_brave(query: str, limit: int) -> list[SearchResult]:
    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        return []

    response = httpx.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={"X-Search-Api-Key": api_key},
        params={"q": query, "count": limit},
        timeout=15.0,
    )
    response.raise_for_status()
    payload = response.json()

    results: list[SearchResult] = []
    for item in payload.get("web", {}).get("results", [])[:limit]:
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("description", ""),
            )
        )

    return results


def search_web(query: str, limit: int) -> list[SearchResult]:
    brave_results = search_brave(query, limit)
    if brave_results:
        return brave_results

    response = httpx.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15.0,
    )
    response.raise_for_status()
    return parse_duckduckgo_html(response.text, limit)


@app.get("/")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "web-search-mcp", "mode": "http"}


@app.post("/search", response_model=list[SearchResult])
def search_endpoint(req: SearchRequest) -> list[SearchResult]:
    try:
        return search_web(req.query, req.limit)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"search provider error: {exc}") from exc


@app.post("/mcp")
def mcp_endpoint(req: MCPRequest) -> dict[str, Any]:
    tool_name = req.tool or req.method or "web_search"
    if tool_name != "web_search":
        raise HTTPException(status_code=404, detail="unsupported tool")

    args = req.arguments or {}
    query = str(args.get("query", "")).strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    limit = int(args.get("limit", 5))
    return {
        "ok": True,
        "tool": tool_name,
        "results": search_web(query, limit),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)
