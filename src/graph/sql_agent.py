"""SQL Analyst Agent: Specialized in querying PostgreSQL & CSV datasets."""

import structlog
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from src.graph.llm import get_llm, extract_text_content
from src.graph.tools_registry import create_sql_tools, calculator
from src.graph.state import AgentFinding

logger = structlog.get_logger(__name__)

SQL_AGENT_PROMPT = """You are the specialized SQL Analyst Agent for this system.
Your sole responsibility is to analyze structured CSV datasets and execute SQL queries in PostgreSQL.

GUIDELINES:
1. ALWAYS inspect available tables by calling `get_data_schema` before writing SQL queries.
2. Always write standard read-only SELECT queries with double quotes around table and column names (e.g. `SELECT "flavor_cost", "os_name" FROM "csv_user_table"`).
3. If calculations or aggregations are needed, combine SQL with the `calculator` tool when appropriate.
4. Format output data clearly using markdown tables or key-value summaries.
5. In your final text, mention which table(s) the data originated from (e.g. `[Source: dataset.csv]`).
"""


async def run_sql_analyst(
    task_id: str,
    instruction: str,
    context_findings: str = "",
    user_id: str = "",
    api_key: str = "",
    include_shared: bool = True,
) -> AgentFinding:
    """Execute SQL analysis for a given instruction."""
    logger.info("sql_analyst_start", task_id=task_id, instruction=instruction)
    llm = get_llm(temperature=0.0, user_id=user_id, node_name="sql_analyst", api_key=api_key)
    tools = create_sql_tools(user_id=user_id, include_shared=include_shared) + [calculator]
    
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SystemMessage(content=SQL_AGENT_PROMPT),
    )

    prompt = instruction
    if context_findings:
        prompt = f"{instruction}\n\nContext from previous steps:\n{context_findings}"

    try:
        result = await agent.ainvoke({"messages": [HumanMessage(content=prompt)]})
        messages = result.get("messages", [])
        last_msg = messages[-1] if messages else HumanMessage(content="No data found.")
        text_content = extract_text_content(last_msg)
        
        return AgentFinding(
            task_id=task_id,
            agent="sql_analyst",
            status="success",
            content=text_content,
            sources=["PostgreSQL Data Tables"],
        )
    except Exception as e:
        logger.error("sql_analyst_error", task_id=task_id, error=str(e))
        return AgentFinding(
            task_id=task_id,
            agent="sql_analyst",
            status="error",
            content=f"SQL Analyst encountered an issue: {e}",
            sources=[],
        )
