"""Web Researcher Agent: Specialized in real-time internet search via MCP."""

import structlog
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from src.graph.llm import get_llm, extract_text_content
from src.mcp.client import get_mcp_tools
from src.graph.state import AgentFinding

logger = structlog.get_logger(__name__)

WEB_AGENT_PROMPT = """You are the specialized Web Researcher Agent for this system.
Your sole responsibility is to find up-to-date, live information from the internet using your web search tools.

GUIDELINES:
1. Formulate concise, effective search queries for `web_search` and `web_search_news`.
2. Synthesize search results into accurate, clear summaries.
3. Always cite web domains or URLs found in the search results (e.g. `[Source: cloud.google.com]`).
"""


async def run_web_researcher(
    task_id: str,
    instruction: str,
    context_findings: str = "",
    user_id: str = "",
    api_key: str = "",
) -> AgentFinding:
    """Execute live web search for a given instruction."""
    logger.info("web_researcher_start", task_id=task_id, instruction=instruction)
    llm = get_llm(temperature=0.1, user_id=user_id, node_name="web_researcher", api_key=api_key)
    tools = get_mcp_tools()
    
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SystemMessage(content=WEB_AGENT_PROMPT),
    )

    prompt = instruction
    if context_findings:
        prompt = f"{instruction}\n\nContext from previous steps:\n{context_findings}"

    try:
        result = await agent.ainvoke({"messages": [HumanMessage(content=prompt)]})
        messages = result.get("messages", [])
        last_msg = messages[-1] if messages else HumanMessage(content="No web results found.")
        text_content = extract_text_content(last_msg)
        
        return AgentFinding(
            task_id=task_id,
            agent="web_researcher",
            status="success",
            content=text_content,
            sources=["Live Web Search"],
        )
    except Exception as e:
        logger.error("web_researcher_error", task_id=task_id, error=str(e))
        return AgentFinding(
            task_id=task_id,
            agent="web_researcher",
            status="error",
            content=f"Web Researcher encountered an issue: {e}",
            sources=[],
        )
