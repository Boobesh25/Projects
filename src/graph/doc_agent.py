"""Document Expert Agent: Specialized in semantic vector RAG and unstructured documents."""

import structlog
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from src.graph.llm import get_llm, extract_text_content
from src.graph.tools_registry import create_rag_tools
from src.graph.state import AgentFinding

logger = structlog.get_logger(__name__)

DOC_AGENT_PROMPT = """You are the specialized Document Expert Agent for this system.
Your sole responsibility is to answer questions using uploaded documents (PDF, DOCX, TXT, MD) and the knowledge base.

GUIDELINES:
1. When asked what documents exist, call `list_uploaded_documents`.
2. When searching for specific information, call `search_documents` with focused keywords and standalone semantic queries.
3. Extract exact facts, terms, numbers, and definitions from retrieved chunks.
4. If information is not found in the documents, state clearly: "Not found in the uploaded documents."
5. Always preserve and note source filenames (e.g. `[Source: document.pdf]`).
"""


async def run_document_expert(
    task_id: str,
    instruction: str,
    context_findings: str = "",
    user_id: str = "",
    api_key: str = "",
    include_shared: bool = True,
) -> AgentFinding:
    """Execute document search and RAG extraction for a given instruction."""
    logger.info("doc_expert_start", task_id=task_id, instruction=instruction)
    llm = get_llm(temperature=0.1, user_id=user_id, node_name="document_expert", api_key=api_key)
    tools = create_rag_tools(user_id=user_id, api_key=api_key, include_shared=include_shared)
    
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SystemMessage(content=DOC_AGENT_PROMPT),
    )

    prompt = instruction
    if context_findings:
        prompt = f"{instruction}\n\nContext from previous steps:\n{context_findings}"

    try:
        result = await agent.ainvoke({"messages": [HumanMessage(content=prompt)]})
        messages = result.get("messages", [])
        last_msg = messages[-1] if messages else HumanMessage(content="No relevant documents found.")
        text_content = extract_text_content(last_msg)
        
        return AgentFinding(
            task_id=task_id,
            agent="document_expert",
            status="success",
            content=text_content,
            sources=["Uploaded Document Store"],
        )
    except Exception as e:
        logger.error("doc_expert_error", task_id=task_id, error=str(e))
        return AgentFinding(
            task_id=task_id,
            agent="document_expert",
            status="error",
            content=f"Document Expert encountered an issue: {e}",
            sources=[],
        )
