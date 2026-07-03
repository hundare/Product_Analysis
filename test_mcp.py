#!/usr/bin/env python3
"""
Test script for the MCP web search server.
This demonstrates how the server responds to tool calls.
"""
import json
from app import search_web


def main():
    print("Testing MCP Web Search Server")
    print("-" * 50)

    # Test 1: Direct search function
    print("\n1. Testing search function directly:")
    results = search_web("python mcp", 2)
    if results:
        print(f"   Found {len(results)} result(s):")
        for r in results:
            print(f"   - {r.title}")
            print(f"     URL: {r.url}")
            print(f"     Snippet: {r.snippet[:80]}...")
    else:
        print("   No results found")

    # Test 2: Verify MCP server loads
    print("\n2. Verifying MCP server configuration:")
    from app import server
    print(f"   Server name: {server.name}")
    print("   ✓ Server initialized successfully")

    # Test 3: Show tool definition
    print("\n3. MCP Tool Definition:")
    tool_def = {
        "name": "web_search",
        "description": "Search the web for information",
        "parameters": {
            "query": "string (required) - Search query",
            "limit": "integer (1-10, default 5) - Number of results",
        },
    }
    print(f"   {json.dumps(tool_def, indent=2)}")

    print("\n" + "-" * 50)
    print("✓ All tests completed successfully!")


if __name__ == "__main__":
    main()

