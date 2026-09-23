"""WebSocket handler using LangGraph ReAct agent."""

import json
import structlog
from fastapi import WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage

from src.database.repository import ChatRepository
from src.graph.workflow import build_graph
from src.graph.answer_cache import get_cached_answer, set_cached_answer, invalidate_user_cache
from src.config.settings import settings

logger = structlog.get_logger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active[user_id] = websocket
        logger.info("ws_connected", user_id=user_id)

    def disconnect(self, user_id: str):
        self.active.pop(user_id, None)
        logger.info("ws_disconnected", user_id=user_id)

    @property
    def count(self) -> int:
        return len(self.active)


manager = ConnectionManager()


async def handle_websocket(websocket: WebSocket, user_id: str):
    """Main WebSocket handler with ReAct agent."""
    await manager.connect(user_id, websocket)

    # Build agent graph for this user (tools are user-bound)
    agent = build_graph(user_id=user_id)

    # Current session ID — None until user sends first message or switches session
    current_session_id = None

    # Conversation messages — only Human + AI final answers (no tool calls)
    messages = []
    MAX_HISTORY_PAIRS = 10  # Keep last 10 Q&A pairs (20 messages)

    try:
        await websocket.send_json({
            "type": "status",
            "content": "🔗 Connected! Ready to help!",
            "agent_name": None,
        })

        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)
            msg_type = payload.get("type", "")

            if msg_type == "logout":
                await websocket.send_json({
                    "type": "status",
                    "content": "👋 Session saved. Goodbye!",
                    "agent_name": None,
                })
                invalidate_user_cache(user_id)
                return

            # ─── Switch session ───────────────────────────────────
            if msg_type == "switch_session":
                new_session_id = payload.get("session_id")
                current_session_id = new_session_id
                messages = []
                if current_session_id:
                    history = await ChatRepository.load_history(user_id, 10, session_id=current_session_id)
                    if history:
                        from langchain_core.messages import AIMessage
                        for msg in history:
                            if msg["role"] == "user":
                                messages.append(HumanMessage(content=msg["content"]))
                            elif msg["role"] == "assistant":
                                messages.append(AIMessage(content=msg["content"]))
                await websocket.send_json({
                    "type": "session_switched",
                    "content": current_session_id or "",
                    "agent_name": None,
                })
                continue

            # ─── New session ──────────────────────────────────────
            if msg_type == "new_session":
                from src.database.repository import ChatSessionRepo
                new_session = await ChatSessionRepo.create_session(user_id)
                current_session_id = new_session["id"]
                messages = []  # Fresh conversation
                await websocket.send_json({
                    "type": "session_created",
                    "content": json.dumps(new_session),
                    "agent_name": None,
                })
                continue

            if msg_type == "message":
                user_content = payload.get("content", "").strip()
                if not user_content:
                    continue

                # ─── Daily message limit check ────────────────────
                daily_count = await ChatRepository.get_daily_message_count(user_id)
                if daily_count >= settings.daily_message_limit:
                    await websocket.send_json({
                        "type": "response",
                        "content": (
                            f"⚠️ You've reached your daily message limit "
                            f"({settings.daily_message_limit} messages per day). "
                            f"Please try again tomorrow. This limit helps manage API costs."
                        ),
                        "agent_name": "system",
                    })
                    continue

                # Auto-create a session if none exists
                if not current_session_id:
                    from src.database.repository import ChatSessionRepo
                    new_session = await ChatSessionRepo.create_session(user_id)
                    current_session_id = new_session["id"]
                    # Title from first message
                    title = user_content[:50] + ("..." if len(user_content) > 50 else "")
                    await ChatSessionRepo.update_title(current_session_id, title)
                    await websocket.send_json({
                        "type": "session_created",
                        "content": json.dumps({"id": current_session_id, "title": title}),
                        "agent_name": None,
                    })

                await ChatRepository.save_message(user_id, "user", user_content, session_id=current_session_id)

                # Auto-title session from first message (if session was pre-created via "new_session")
                if current_session_id and len(messages) == 0:
                    from src.database.repository import ChatSessionRepo
                    title = user_content[:50] + ("..." if len(user_content) > 50 else "")
                    await ChatSessionRepo.update_title(current_session_id, title)

                # ─── Check cache ──────────────────────────────────
                cached = get_cached_answer(user_id, user_content)
                if cached:
                    await websocket.send_json({
                        "type": "status",
                        "content": "⚡ Found in cache!",
                        "agent_name": None,
                    })
                    await websocket.send_json({
                        "type": "response",
                        "content": cached,
                        "agent_name": "assistant",
                    })
                    continue

                await websocket.send_json({
                    "type": "status",
                    "content": "🧠 Working on your question...",
                    "agent_name": None,
                })

                # ─── Run Multi-Agent Graph ──────────────────────────────
                try:
                    from src.graph.state import MultiAgentState
                    from langchain_core.messages import AIMessage

                    # Add user message to conversation (clean history)
                    messages.append(HumanMessage(content=user_content))

                    trace_steps = []
                    final_answer = ""

                    init_state = MultiAgentState(
                        messages=messages,
                        user_id=user_id,
                        session_id=current_session_id or "",
                        include_shared=True,
                    )

                    async for chunk in agent.astream(
                        init_state,
                        stream_mode="updates",
                        config={
                            "recursion_limit": 40,
                            "metadata": {"user_id": user_id},
                            "tags": [f"user:{user_id}"],
                        },
                    ):
                        for node_name, node_output in chunk.items():
                            if node_name == "router":
                                plan = node_output.get("plan")
                                if plan:
                                    if plan.is_clarification_needed and plan.clarification_question:
                                        final_answer = plan.clarification_question
                                    elif plan.is_complex or len(plan.subtasks) > 1:
                                        agents = list({t.agent for t in plan.subtasks})
                                        await websocket.send_json({
                                            "type": "status",
                                            "content": f"⚡ Multi-Agent Orchestrator: Coordinating {len(plan.subtasks)} subtasks across {len(agents)} agents...",
                                            "agent_name": "orchestrator",
                                        })
                                    elif plan.subtasks:
                                        single = plan.subtasks[0].agent
                                        friendly = {
                                            "sql_analyst": "📊 SQL Analyst: Inspecting schema & querying PostgreSQL tables...",
                                            "document_expert": "📄 Document Expert: Searching knowledge base & vector store...",
                                            "web_researcher": "🌐 Web Researcher: Conducting real-time web search via MCP...",
                                        }.get(single, "💬 Assistant: Processing response...")
                                        await websocket.send_json({
                                            "type": "status",
                                            "content": friendly,
                                            "agent_name": single,
                                        })
                            elif node_name == "sql_analyst":
                                await websocket.send_json({
                                    "type": "status",
                                    "content": "✓ SQL Analyst finished querying data tables",
                                    "agent_name": "sql_analyst",
                                })
                            elif node_name == "document_expert":
                                await websocket.send_json({
                                    "type": "status",
                                    "content": "✓ Document Expert finished retrieving information",
                                    "agent_name": "document_expert",
                                })
                            elif node_name == "web_researcher":
                                await websocket.send_json({
                                    "type": "status",
                                    "content": "✓ Web Researcher gathered live internet facts",
                                    "agent_name": "web_researcher",
                                })
                            elif node_name == "complex_orchestrator":
                                await websocket.send_json({
                                    "type": "status",
                                    "content": "✓ Multi-agent subtasks completed",
                                    "agent_name": "orchestrator",
                                })
                            elif node_name == "synthesizer":
                                ans = node_output.get("final_answer", "")
                                if ans:
                                    final_answer = ans
                                trace_steps = node_output.get("reasoning_trace", trace_steps)

                            if "final_answer" in node_output and node_output["final_answer"]:
                                final_answer = node_output["final_answer"]
                            if "reasoning_trace" in node_output:
                                trace_steps = node_output["reasoning_trace"]

                    if not final_answer:
                        final_answer = "I've processed your request. Please try asking again if anything is missing."

                    messages.append(AIMessage(content=final_answer))
                    if len(messages) > MAX_HISTORY_PAIRS * 2:
                        messages = messages[-(MAX_HISTORY_PAIRS * 2):]

                    trace_display = "\n".join(trace_steps) if trace_steps else ""

                except Exception as e:
                    logger.error("agent_error", error=str(e), user_id=user_id)
                    final_answer = "Sorry, something went wrong. Please try again."
                    trace_display = f"❌ Error: {str(e)[:200]}"

                # ─── Send response ────────────────────────────────
                await ChatRepository.save_message(user_id, "assistant", final_answer, "agent", session_id=current_session_id)

                # Cache answer (only if it's a real answer, not an error)
                if "went wrong" not in final_answer and "try again" not in final_answer:
                    set_cached_answer(user_id, user_content, final_answer, "general")

                if trace_display:
                    await websocket.send_json({
                        "type": "trace",
                        "content": trace_display,
                        "agent_name": None,
                    })

                await websocket.send_json({
                    "type": "status",
                    "content": "📨 Here's your answer!",
                    "agent_name": None,
                })

                await websocket.send_json({
                    "type": "response",
                    "content": final_answer,
                    "agent_name": "assistant",
                })

    except WebSocketDisconnect:
        logger.info("ws_client_disconnected", user_id=user_id)
    except Exception as e:
        logger.error("ws_handler_error", error=str(e), user_id=user_id)
    finally:
        manager.disconnect(user_id)


def _tool_status(tool_name: str) -> str:
    """User-friendly status for tool calls."""
    mapping = {
        "get_data_schema": "📂 Checking your data tables...",
        "run_sql_query": "🗄️ Querying your data...",
        "search_documents": "📖 Searching documents...",
        "calculator": "🧮 Calculating...",
    }
    return mapping.get(tool_name, f"⚙️ Using {tool_name}...")
