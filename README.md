# Web Search MCP Service

This project exposes a simple web search endpoint that can be deployed on Render and called from a low-code app.

## Run locally

```bash
python -m pip install -r requirements.txt
python app.py
```

Then open:

- http://127.0.0.1:8000/ -> health check
- http://127.0.0.1:8000/search -> POST JSON search endpoint

Example request:

```bash
curl -X POST http://127.0.0.1:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query":"python mcp server","limit":3}'
```

## Deploy to Render

1. Push this folder to GitHub.
2. Create a new Web Service on Render.
3. Connect the repository.
4. Use these settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python app.py`
5. Render will provide a public URL such as:
   `https://your-service-name.onrender.com`

## Low-code app usage

Call the Render URL with a POST request to `/search`:

```json
{
  "query": "latest AI news",
  "limit": 5
}
```
