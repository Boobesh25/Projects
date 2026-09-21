"""
MCP Server: Web Search Tool
Transport: Streamable HTTP (accessible over HTTP by any MCP client)

This exposes a web search tool via MCP protocol over HTTP.
Any MCP-compatible client (Kiro, Claude Desktop, Cursor, custom agents)
can connect to this server and use the search tools.

Run: python -m src.mcp.web_search_server
Endpoint: http://localhost:8001/mcp
"""

from mcp.server.fastmcp import FastMCP
from duckduckgo_search import DDGS

# Create the MCP server
mcp = FastMCP(
    name="web-search",
    instructions="Web search tools for finding current information from the internet.",
)


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo.
    Returns titles, snippets, and URLs of top results.
    Use this when you need current information, latest versions,
    news, or anything not found in local documents.
    """
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))

    if not results:
        return "No web results found for this query."

    output = []
    for i, r in enumerate(results, 1):
        output.append(
            f"[{i}] **{r['title']}**\n"
            f"{r['body']}\n"
            f"Source: {r['href']}"
        )

    return "\n\n---\n\n".join(output)


@mcp.tool()
def web_search_news(query: str, max_results: int = 5) -> str:
    """
    Search for recent news articles.
    Returns the latest news headlines and summaries.
    """
    with DDGS() as ddgs:
        results = list(ddgs.news(query, max_results=max_results))

    if not results:
        return "No news results found."

    output = []
    for i, r in enumerate(results, 1):
        output.append(
            f"[{i}] **{r['title']}**\n"
            f"{r['body']}\n"
            f"Published: {r.get('date', 'Unknown')}\n"
            f"Source: {r['url']}"
        )

    return "\n\n---\n\n".join(output)


@mcp.tool()
def fetch_webpage(url: str) -> str:
    """
    Fetch and extract text content from a specific URL.
    Use this to read a webpage that was found via web_search.
    Returns the main text content (limited to first 5000 chars).
    """
    import httpx
    from html.parser import HTMLParser

    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text_parts: list[str] = []
            self.skip_tags = {"script", "style", "nav", "header", "footer"}
            self._skip = False

        def handle_starttag(self, tag, attrs):
            if tag in self.skip_tags:
                self._skip = True

        def handle_endtag(self, tag):
            if tag in self.skip_tags:
                self._skip = False

        def handle_data(self, data):
            if not self._skip:
                text = data.strip()
                if text:
                    self.text_parts.append(text)

    try:
        response = httpx.get(url, timeout=10, follow_redirects=True)
        response.raise_for_status()

        parser = TextExtractor()
        parser.feed(response.text)
        content = "\n".join(parser.text_parts)

        # Limit output
        if len(content) > 5000:
            content = content[:5000] + "\n\n[... content truncated at 5000 chars]"

        return content if content else "No text content extracted from this page."

    except Exception as e:
        return f"Error fetching URL: {e}"


if __name__ == "__main__":
    # Run with Streamable HTTP transport on port 8001
    mcp.settings.port = 8001
    mcp.settings.host = "0.0.0.0"
    mcp.run(transport="streamable-http")
