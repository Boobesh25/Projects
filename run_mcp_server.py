"""Run the MCP Web Search server with HTTP transport."""

import os
os.environ["FASTMCP_PORT"] = "8001"
os.environ["PORT"] = "8001"
os.environ["HOST"] = "0.0.0.0"

from src.mcp.web_search_server import mcp

if __name__ == "__main__":
    print("🌐 Starting MCP Web Search Server...")
    print("   Endpoint: http://localhost:8001/mcp")
    print("   Tools: web_search, web_search_news, fetch_webpage")
    print()
    mcp.settings.port = 8001
    mcp.settings.host = "0.0.0.0"
    mcp.run(transport="streamable-http")
