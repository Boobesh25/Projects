"""Multi-Agent LangGraph Workflow with Parallel & Sequential Orchestration.

Orchestrates:
1. 🎯 Smart Router Agent (Query decomposition & planning)
2. 📊 SQL Analyst Agent (PostgreSQL & CSV querying)
3. 📄 Document Expert Agent (Vector store RAG & document retrieval)
4. 🌐 Web Researcher Agent (MCP live internet search)
5. ✨ Response Synthesizer Agent (Harmonization, formatting & citations)
"""

import asyncio
import structlog
from typing import Literal
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, START, END

from src.graph.state import MultiAgentState, ExecutionPlan, SubTask, AgentFinding
from src.graph.router import plan_execution
from src.graph.sql_agent import run_sql_analyst
from src.graph.doc_agent import run_document_expert
from src.graph.web_agent import run_web_researcher
from src.graph.synthesizer import synthesize_response
from src.graph.llm import get_llm, extract_text_content
from src.graph.tools_registry import calculator

logger = structlog.get_logger(__name__)


def build_graph(
    user_id: str = "",
    api_key: str = "",
    include_shared: bool = True,
):
    """Build the compiled Multi-Agent LangGraph workflow."""

    async def router_node(state: MultiAgentState) -> dict:
        """Smart Router analyzes intent and creates the ExecutionPlan."""
        logger.info("multi_agent_router_node_start", user_id=user_id)
        plan = await plan_execution(state.messages, user_id=user_id, api_key=api_key)
        
        trace = list(state.reasoning_trace)
        trace.append(f"🎯 Smart Router: Plan generated ({'Complex Multi-Agent' if plan.is_complex else 'Single Agent: ' + (plan.subtasks[0].agent if plan.subtasks else 'direct')})")
        
        # If clarification is needed, set direct response
        if plan.is_clarification_needed and plan.clarification_question:
            return {
                "plan": plan,
                "final_answer": plan.clarification_question,
                "reasoning_trace": trace,
            }

        return {
            "plan": plan,
            "reasoning_trace": trace,
        }

    async def execute_subtask(task: SubTask, context: str = "") -> AgentFinding:
        """Helper to run a specific worker agent for a subtask."""
        if task.agent == "sql_analyst":
            return await run_sql_analyst(
                task_id=task.task_id,
                instruction=task.instruction,
                context_findings=context,
                user_id=user_id,
                api_key=api_key,
                include_shared=include_shared,
            )
        elif task.agent == "document_expert":
            return await run_document_expert(
                task_id=task.task_id,
                instruction=task.instruction,
                context_findings=context,
                user_id=user_id,
                api_key=api_key,
                include_shared=include_shared,
            )
        elif task.agent == "web_researcher":
            return await run_web_researcher(
                task_id=task.task_id,
                instruction=task.instruction,
                context_findings=context,
                user_id=user_id,
                api_key=api_key,
            )
        else:
            # Direct / calculation node
            llm = get_llm(temperature=0.2, user_id=user_id, node_name="direct_assistant", api_key=api_key)
            resp = await llm.ainvoke([HumanMessage(content=task.instruction)])
            return AgentFinding(
                task_id=task.task_id,
                agent="direct",
                status="success",
                content=extract_text_content(resp),
                sources=[],
            )

    async def sql_analyst_node(state: MultiAgentState) -> dict:
        """Dedicated SQL Analyst Agent node."""
        plan = state.plan
        task = next((t for t in plan.subtasks if t.agent == "sql_analyst"), None) if plan else None
        instruction = task.instruction if task else (state.messages[-1].content if state.messages else "")
        task_id = task.task_id if task else "sql_1"

        finding = await execute_subtask(SubTask(task_id=task_id, agent="sql_analyst", instruction=str(instruction)))
        
        findings = dict(state.findings)
        findings[f"sql_analyst_{task_id}"] = finding.content
        trace = list(state.reasoning_trace)
        trace.append("📊 SQL Analyst: Executed database schema and SQL analysis")

        return {"findings": findings, "reasoning_trace": trace}

    async def doc_expert_node(state: MultiAgentState) -> dict:
        """Dedicated Document Expert Agent node."""
        plan = state.plan
        task = next((t for t in plan.subtasks if t.agent == "document_expert"), None) if plan else None
        instruction = task.instruction if task else (state.messages[-1].content if state.messages else "")
        task_id = task.task_id if task else "doc_1"

        finding = await execute_subtask(SubTask(task_id=task_id, agent="document_expert", instruction=str(instruction)))
        
        findings = dict(state.findings)
        findings[f"document_expert_{task_id}"] = finding.content
        trace = list(state.reasoning_trace)
        trace.append("📄 Document Expert: Queried knowledge base and vector chunks")

        return {"findings": findings, "reasoning_trace": trace}

    async def web_researcher_node(state: MultiAgentState) -> dict:
        """Dedicated Web Researcher Agent node."""
        plan = state.plan
        task = next((t for t in plan.subtasks if t.agent == "web_researcher"), None) if plan else None
        instruction = task.instruction if task else (state.messages[-1].content if state.messages else "")
        task_id = task.task_id if task else "web_1"

        finding = await execute_subtask(SubTask(task_id=task_id, agent="web_researcher", instruction=str(instruction)))
        
        findings = dict(state.findings)
        findings[f"web_researcher_{task_id}"] = finding.content
        trace = list(state.reasoning_trace)
        trace.append("🌐 Web Researcher: Performed real-time MCP web searches")

        return {"findings": findings, "reasoning_trace": trace}

    async def direct_node(state: MultiAgentState) -> dict:
        """Direct Assistant node for conversation, calculations, and general knowledge."""
        plan = state.plan
        task = next((t for t in plan.subtasks if t.agent == "direct"), None) if plan else None
        instruction = task.instruction if task else (state.messages[-1].content if state.messages else "")
        task_id = task.task_id if task else "direct_1"

        finding = await execute_subtask(SubTask(task_id=task_id, agent="direct", instruction=str(instruction)))
        
        findings = dict(state.findings)
        findings[f"direct_{task_id}"] = finding.content
        trace = list(state.reasoning_trace)
        trace.append("💬 Assistant: Processed general explanation / calculation")

        return {"findings": findings, "reasoning_trace": trace}

    async def complex_orchestrator_node(state: MultiAgentState) -> dict:
        """Handles complex multi-agent queries via Parallel and Sequential execution."""
        plan = state.plan
        if not plan or not plan.subtasks:
            return {"findings": state.findings}

        findings = dict(state.findings)
        trace = list(state.reasoning_trace)

        # 1. Separate independent vs dependent tasks
        independent_tasks = [t for t in plan.subtasks if not t.depends_on]
        dependent_tasks = [t for t in plan.subtasks if t.depends_on]

        # 2. Execute independent tasks IN PARALLEL (Fan-out)
        if independent_tasks:
            trace.append(f"⚡ Parallel Execution: Running {len(independent_tasks)} independent subtasks simultaneously")
            parallel_results = await asyncio.gather(*[execute_subtask(t) for t in independent_tasks])
            for t, res in zip(independent_tasks, parallel_results):
                findings[f"{t.agent}_{t.task_id}"] = res.content
                trace.append(f"✓ {t.agent} finished ({t.task_id})")

        # 3. Execute dependent tasks IN SEQUENCE (Chaining)
        for dtask in dependent_tasks:
            # Build context from completed prerequisite tasks
            prereq_context = "\n\n".join(
                f"Output from {pid}:\n{findings.get(f'{pid}', findings.get(f'{dtask.agent}_{pid}', ''))}"
                for pid in dtask.depends_on
            )
            trace.append(f"🔗 Sequential Execution: Running {dtask.agent} ({dtask.task_id}) with context from {dtask.depends_on}")
            d_res = await execute_subtask(dtask, context=prereq_context)
            findings[f"{dtask.agent}_{dtask.task_id}"] = d_res.content
            trace.append(f"✓ {dtask.agent} finished ({dtask.task_id})")

        return {"findings": findings, "reasoning_trace": trace}

    async def synthesizer_node(state: MultiAgentState) -> dict:
        """Response Synthesizer harmonizes all findings into the final response."""
        # If final answer already produced (e.g. clarification), preserve it
        if state.final_answer:
            return {"final_answer": state.final_answer}

        logger.info("multi_agent_synthesizer_start", num_findings=len(state.findings))
        final_answer = await synthesize_response(state, user_id=user_id, api_key=api_key)
        
        trace = list(state.reasoning_trace)
        trace.append("✨ Response Synthesizer: Synthesized and formatted final answer with citations")

        return {
            "final_answer": final_answer,
            "reasoning_trace": trace,
        }

    def route_decision(state: MultiAgentState) -> Literal["clarification", "complex", "sql_analyst", "document_expert", "web_researcher", "direct"]:
        """Determine next node from Smart Router's ExecutionPlan."""
        plan = state.plan
        if not plan:
            return "direct"
        if plan.is_clarification_needed:
            return "clarification"
        if plan.is_complex or len(plan.subtasks) > 1:
            return "complex"
        
        single_agent = plan.subtasks[0].agent if plan.subtasks else "direct"
        return single_agent

    # ─── Build LangGraph StateGraph ──────────────────────────────────────────
    workflow = StateGraph(MultiAgentState)

    # Register Nodes
    workflow.add_node("router", router_node)
    workflow.add_node("sql_analyst", sql_analyst_node)
    workflow.add_node("document_expert", doc_expert_node)
    workflow.add_node("web_researcher", web_researcher_node)
    workflow.add_node("direct", direct_node)
    workflow.add_node("complex_orchestrator", complex_orchestrator_node)
    workflow.add_node("synthesizer", synthesizer_node)

    # Connect Edges
    workflow.add_edge(START, "router")

    workflow.add_conditional_edges(
        "router",
        route_decision,
        {
            "clarification": END,
            "complex": "complex_orchestrator",
            "sql_analyst": "sql_analyst",
            "document_expert": "document_expert",
            "web_researcher": "web_researcher",
            "direct": "direct",
        },
    )

    # All workers route to synthesizer
    workflow.add_edge("sql_analyst", "synthesizer")
    workflow.add_edge("document_expert", "synthesizer")
    workflow.add_edge("web_researcher", "synthesizer")
    workflow.add_edge("direct", "synthesizer")
    workflow.add_edge("complex_orchestrator", "synthesizer")
    workflow.add_edge("synthesizer", END)

    return workflow.compile()
