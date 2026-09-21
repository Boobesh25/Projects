"""
MCP Client: Connects to the web search MCP server and exposes tools as LangChain tools.
This bridges MCP → LangChain so the agent can use MCP tools seamlessly.
"""

import os
import socket
from urllib.parse import urlparse
from langchain_core.tools import tool


MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001")


def _call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Call an MCP tool using the proper MCP client library."""
    import asyncio

    async def _do_call():
        from mcp.client.streamable_http import streamablehttp_client
        from mcp import ClientSession

        async with streamablehttp_client(f"{MCP_SERVER_URL}/mcp") as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                # Extract text content from result
                if result.content:
                    texts = [c.text for c in result.content if hasattr(c, 'text')]
                    return "\n".join(texts)
                return "No results."

    try:
        # Run the async MCP call
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_do_call())
        finally:
            loop.close()
    except Exception as e:
        if "Connect" in str(e) or "refused" in str(e):
            return "⚠️ Web search unavailable (MCP server not running)."
        return f"Web search error: {e}"


@tool
def web_search(query: str) -> str:
    """
    Search the web for current information not found in uploaded documents.
    Use this when:
    - Document search returns no relevant results
    - User asks about current events, latest versions, or live data
    - User explicitly asks to search the web
    NOT for questions about uploaded documents — use search_documents for those.
    """
    return _call_mcp_tool("web_search", {"query": query, "max_results": 3})


@tool
def web_search_news(query: str) -> str:
    """
    Search for recent news articles on a topic.
    Use for current events, announcements, or breaking news.
    """
    return _call_mcp_tool("web_search_news", {"query": query, "max_results": 3})


def get_mcp_tools() -> list:
    """Return MCP-backed tools only if the MCP server is reachable."""
    try:
        # Check if the MCP server host/port is open
        parsed = urlparse(MCP_SERVER_URL)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8001
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        if result == 0:
            return [web_search, web_search_news]
        return []
    except Exception:
        return []
