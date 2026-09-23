"""Smart Router Agent: Analyzes user intent, resolves context/pronouns, and builds an ExecutionPlan."""

import json
import structlog
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from src.graph.llm import get_llm, extract_text_content
from src.graph.state import ExecutionPlan, SubTask

logger = structlog.get_logger(__name__)

ROUTER_SYSTEM_PROMPT = """You are the Smart Router & Orchestration Supervisor for an Enterprise Agentic AI system.

YOUR SPECIALIZED AGENT TEAM:
1. "sql_analyst": Specialized in querying structured CSV datasets & PostgreSQL tables (e.g., pricing, schemas, metrics, row filtering, table aggregations).
2. "document_expert": Specialized in unstructured text documents (PDF, DOCX, TXT, MD, meeting notes, guides, contracts). Can list uploaded files and perform semantic vector searches.
3. "web_researcher": Specialized in live, real-time web searches and current information (via MCP tools).
4. "direct": For general chit-chat, conceptual software explanations, mathematical calculations, or greetings.

YOUR RESPONSIBILITIES:
1. CONTEXT REWRITING:
   - Read the conversation history.
   - Resolve all pronouns ("it", "this", "that", "the previous file", "those numbers") into self-contained explicit nouns.
   
2. AMBIGUITY CHECK:
   - If the request is too vague to act on, set is_clarification_needed=True and formulate a friendly question in clarification_question.

3. WORKFLOW PLANNING (PARALLEL & SEQUENTIAL):
   - Single Task: Create 1 subtask for the appropriate agent.
   - Independent Multi-Task (Parallel): If the user asks two independent things (e.g. "Check CSV table costs AND search the web for latest trends"), create 2 subtasks with empty depends_on ([]).
   - Dependent Multi-Task (Sequential): If Task 2 requires data from Task 1 (e.g. "Find the top customer in the CSV, then search our PDF agreements for their contract terms"), create task_1 (sql_analyst) and task_2 (document_expert) with depends_on=["task_1"].

Respond strictly with valid JSON matching the ExecutionPlan schema.
"""


async def plan_execution(
    messages: list,
    user_id: str = "",
    api_key: str = "",
) -> ExecutionPlan:
    """Analyze messages and generate an ExecutionPlan."""
    llm = get_llm(temperature=0.0, user_id=user_id, node_name="smart_router", api_key=api_key)
    
    # Try structured output first
    try:
        structured_llm = llm.with_structured_output(ExecutionPlan)
        prompt_messages = [SystemMessage(content=ROUTER_SYSTEM_PROMPT)] + messages
        plan: ExecutionPlan = await structured_llm.ainvoke(prompt_messages)
        if plan and plan.subtasks:
            logger.info("router_plan_created", plan=plan.dict())
            return plan
    except Exception as e:
        logger.warning("structured_router_failed_fallback_to_json", error=str(e))

    # Fallback to standard JSON prompting
    prompt_messages = [
        SystemMessage(content=ROUTER_SYSTEM_PROMPT + "\n\nReturn JSON ONLY with keys: standalone_query, is_clarification_needed, clarification_question, is_complex, subtasks."),
    ] + messages

    try:
        response = await llm.ainvoke(prompt_messages)
        text_resp = extract_text_content(response).strip()
        # Clean potential markdown formatting
        if "```json" in text_resp:
            text_resp = text_resp.split("```json")[1].split("```")[0].strip()
        elif "```" in text_resp:
            text_resp = text_resp.split("```")[1].split("```")[0].strip()

        data = json.loads(text_resp)
        return ExecutionPlan(**data)
    except Exception as e:
        logger.error("router_fallback_failed_defaulting", error=str(e))
        last_msg = messages[-1].content if messages else "help"
        # Safe default to document expert or direct
        return ExecutionPlan(
            standalone_query=str(last_msg),
            is_complex=False,
            subtasks=[
                SubTask(
                    task_id="task_1",
                    agent="document_expert" if any(w in str(last_msg).lower() for w in ["doc", "file", "pdf", "search", "read"]) else "direct",
                    instruction=str(last_msg),
                    depends_on=[],
                )
            ],
        )
