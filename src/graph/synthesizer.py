"""Response Synthesizer Agent: Merges findings from specialist agents into a polished final answer."""

import structlog
from langchain_core.messages import SystemMessage, HumanMessage
from src.graph.llm import get_llm, extract_text_content
from src.graph.state import MultiAgentState

logger = structlog.get_logger(__name__)

SYNTHESIZER_SYSTEM_PROMPT = """You are the Response Synthesizer Agent for an Enterprise Multi-Agent AI system.
Your job is to take the findings collected by specialized worker agents (SQL Analyst, Document Expert, Web Researcher) and synthesize a cohesive, beautiful, user-ready response.

RULES:
1. HARMONIZE FINDINGS:
   - Combine data, documents, and web facts into a logical, easy-to-read answer.
   - If multiple agents contributed, clearly present the relationship between their findings (e.g. comparing database figures with live web figures).
2. FORMATTING:
   - Use clean Markdown with headers, bullet points, and tables where appropriate.
   - Format numbers cleanly (e.g. "$0.106 / hr", "1,240 requests").
3. PRIVACY & CLEANLINESS:
   - NEVER expose internal SQL queries, table prefixes (csv_...), chunk IDs, or internal routing details.
4. CITATIONS:
   - At the bottom of your response, provide clear source citations:
     - 📄 Source: document_name.pdf
     - 📊 Source: dataset_name.csv
     - 🌐 Source: domain.com
5. IF NO DATA WAS FOUND:
   - Politely explain what was checked and advise the user on how to proceed.
"""


async def synthesize_response(
    state: MultiAgentState,
    user_id: str = "",
    api_key: str = "",
) -> str:
    """Synthesize final response from accumulated agent findings."""
    llm = get_llm(temperature=0.2, user_id=user_id, node_name="response_synthesizer", api_key=api_key)

    plan = state.plan
    query = plan.standalone_query if plan else "User query"
    findings = state.findings

    findings_text = "\n\n".join(
        f"--- Agent: {agent_name} (Task: {tid}) ---\n{content}"
        for tid, content in findings.items()
        for agent_name in [tid.split("_")[0] if "_" in tid else "specialist"]
    )

    prompt = f"""Original User Query: {query}

Accumulated Findings from Specialized Agents:
{findings_text}

Synthesize a comprehensive, polished response addressing the user's query following the system rules.
"""

    try:
        response = await llm.ainvoke([
            SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        final_answer = extract_text_content(response).strip()
        logger.info("response_synthesized", length=len(final_answer))
        return final_answer
    except Exception as e:
        logger.error("synthesizer_error", error=str(e))
        # Fallback: join raw findings
        return "\n\n".join(findings.values()) or "Unable to synthesize response."
