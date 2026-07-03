# Integration Guide: Web Search MCP (Dual Mode)

Your server now runs in **two modes simultaneously**:
1. **HTTP mode** (for low-code apps: Zapier, Make, n8n, etc.)
2. **MCP mode** (for Claude, Cursor IDE)

## Quick Start

### Run the Server

**HTTP + MCP (Recommended):**
```bash
cd Product_Analysis
python app.py
```

Starts on `http://0.0.0.0:8000` with both HTTP endpoints and MCP server capability.

**MCP-only (for Claude Desktop / Cursor):**
```bash
python mcp_server.py
```

Runs pure MCP server on stdio (no HTTP).

---

## 1. HTTP Endpoints (for Low-Code Apps)

When running `python app.py`, you get REST endpoints:

### Health Check
```
GET http://localhost:8000/
```

Response:
```json
{
  "status": "ok",
  "service": "web-search-mcp",
  "mode": "http+mcp"
}
```

### Search
```
POST http://localhost:8000/search
Content-Type: application/json

{
  "query": "python web scraping",
  "limit": 5
}
```

Response:
```json
[
  {
    "title": "Beautiful Soup Documentation",
    "url": "https://www.crummy.com/software/BeautifulSoup/",
    "snippet": "Beautiful Soup is a library for pulling data out of HTML..."
  },
  ...
]
```

### Use in Make.com Example

**HTTP Request Module:**
- URL: `https://your-render-url.onrender.com/search`
- Method: POST
- Headers: `Content-Type: application/json`
- Body:
  ```json
  {
    "query": "{{trigger.search_query}}",
    "limit": 5
  }
  ```

### Use in Zapier

**Webhook by Zapier:**
- Action: POST
- URL: `https://your-render-url.onrender.com/search`
- Data:
  ```json
  {
    "query": "my search term",
    "limit": 5
  }
  ```

---

## 2. MCP Mode (for Claude & Cursor)

### Use with Cursor

Add to `.cursor/rules` or Cursor settings:

```json
{
  "mcpServers": {
    "web-search": {
      "command": "python",
      "args": ["/full/path/to/Product_Analysis/mcp_server.py"]
    }
  }
}
```

Restart Cursor. The `web_search` tool will appear.

### Use with Claude Desktop

Edit `~/.claude/config.json` (macOS/Linux) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "web-search": {
      "command": "python",
      "args": ["/full/path/to/Product_Analysis/mcp_server.py"]
    }
  }
}
```

Restart Claude Desktop.

---

## 3. Deployment to Render

Since Render supports both HTTP and background processes:

1. Push to GitHub
2. Create Web Service on Render
3. Settings:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python app.py`
4. Render assigns a public URL: `https://your-service-name.onrender.com`

Now you have:
- ✅ HTTP endpoint at `https://your-service-name.onrender.com/search`
- ✅ Available for low-code apps

---

## Tool Reference

### web_search

**Description:** Search the web and return top results.

**Parameters:**
- `query` (string, required): Search term
- `limit` (integer, 1-10, default 5): Number of results

**Example HTTP Request:**
```bash
curl -X POST https://your-service.onrender.com/search \
  -H "Content-Type: application/json" \
  -d '{"query":"machine learning","limit":3}'
```

**Example Response:**
```json
[
  {
    "title": "Machine Learning - Wikipedia",
    "url": "https://en.wikipedia.org/wiki/Machine_learning",
    "snippet": "Machine learning (ML) is a branch of artificial intelligence..."
  },
  {
    "title": "Machine Learning by Andrew Ng",
    "url": "https://www.coursera.org/learn/machine-learning",
    "snippet": "Learn Machine Learning from Stanford University..."
  },
  {
    "title": "TensorFlow - Machine Learning",
    "url": "https://www.tensorflow.org/",
    "snippet": "An open-source machine learning platform..."
  }
]
```

---

## Optional: Brave Search API

For better results (optional, requires free API key):

1. Get key from: https://api.search.brave.com
2. Set environment variable:
   ```bash
   export BRAVE_API_KEY=your_key_here
   python app.py
   ```

If no API key is set, falls back to DuckDuckGo automatically.

---

## Testing Locally

### Test HTTP endpoint:
```bash
python -m pytest test_mcp.py -v
```

Or manually:
```bash
python app.py
# In another terminal:
$body = @{query="test"; limit=2} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/search" -Method Post -ContentType "application/json" -Body $body
```

### Test MCP server:
```bash
python test_mcp.py
```

---

## Architecture

```
┌──────────────────────────────────────────────┐
│        python app.py                         │
│   (Hybrid HTTP + MCP Server)                 │
└──────────────┬───────────────────────────────┘
               │
        ┌──────┴───────────┐
        │                  │
    ┌───▼────┐        ┌────▼────┐
    │  HTTP  │        │   MCP    │
    │ Mode   │        │ Mode     │
    └───┬────┘        └────┬─────┘
        │                  │
   ┌────▼─────────┐   ┌────▼──────────┐
   │ Low-code     │   │ Claude/Cursor │
   │ Apps         │   │ (IDE)         │
   └──────────────┘   └───────────────┘
        │
   ┌────▼─────────────────────┐
   │ DuckDuckGo / Brave API   │
   └──────────────────────────┘
```

---

## Troubleshooting

**Q: Port 8000 already in use?**
A: Kill existing process or use different port: `PORT=8001 python app.py`

**Q: Tool not appearing in Cursor/Claude?**
A: Restart the IDE after updating config file. Ensure path is absolute and correct.

**Q: No search results?**
A: Check internet connection. Brave API key is optional (uses DuckDuckGo by default).

**Q: How do I use ONLY HTTP (no MCP)?**
A: Run `python app.py` — it works as pure HTTP server. MCP is only active if a client connects via stdio.

---

## Next Steps

1. **Deploy to Render** for production use
2. **Connect** to your low-code workflow (Make, Zapier, etc.)
3. **Optional:** Use MCP with Claude Desktop for local AI integration
4. **Extend:** Add more tools (code search, docs lookup, etc.) following the same pattern

