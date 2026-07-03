# Web Search MCP Server

A proper **Model Context Protocol (MCP)** server that exposes a web search tool. This allows Claude, Cursor, and other MCP-compatible clients to call web search as a native tool.

## Features

- **Standard MCP Protocol**: Fully compatible with Claude, Cursor IDE, and other MCP clients
- **Web Search Tool**: Search the web using DuckDuckGo or Brave API (if configured)
- **No HTTP overhead**: Communicates via efficient stdio transport

## Installation

```bash
pip install -r requirements.txt
```

## Run locally

```bash
python mcp_server.py
```

The server runs on stdio (standard input/output), which is the MCP standard.

## Use with Cursor

1. Add this to your `.cursor/rules` or Cursor settings:

```json
{
  "tools": [
    {
      "name": "web-search-mcp",
      "type": "mcp",
      "command": "python /path/to/mcp_server.py"
    }
  ]
}
```

2. Cursor will now have access to the `web_search` tool.

## Use with Claude Desktop

1. Add to `~/.claude/config.json`:

```json
{
  "tools": {
    "web_search": {
      "type": "stdio",
      "command": "python /path/to/mcp_server.py"
    }
  }
}
```

## Tool specification

### web_search

**Description**: Search the web for information.

**Parameters**:
- `query` (string, required): Search query
- `limit` (integer, optional): Number of results to return (1-10, default: 5)

**Returns**: JSON array of results with `title`, `url`, and `snippet`.

Example result:

```json
[
  {
    "title": "Python MCP Server Guide",
    "url": "https://example.com/mcp-guide",
    "snippet": "Learn how to build MCP servers in Python..."
  }
]
```

## Optional: Brave Search API

To use the Brave Search API (better results, requires API key):

```bash
export BRAVE_API_KEY=your_api_key_here
python mcp_server.py
```

If no API key is set, the server falls back to DuckDuckGo.

## Deploy to Render

1. Push to GitHub.
2. Create a Web Service on Render.
3. Connect the repo.
4. Keep the default settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python mcp_server.py`

## Architecture

```
┌─────────────────────────┐
│  Cursor / Claude        │
│  (MCP Client)           │
└────────────┬────────────┘
             │ (stdio)
             │
┌────────────▼────────────┐
│   MCP Server            │
│  - Defines web_search   │
│  - Handles tool calls   │
└────────────┬────────────┘
             │
             │ (httpx)
             │
┌────────────▼────────────┐
│  DuckDuckGo / Brave     │
│  Search APIs            │
└─────────────────────────┘
```

