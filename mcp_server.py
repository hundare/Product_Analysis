#!/usr/bin/env python3
"""
Wrapper to run the MCP server.
This allows the server to be invoked as:
  python mcp_server.py
"""
import asyncio
from app import server


async def main():
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
