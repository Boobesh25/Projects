"""Usage tracking — logs every LLM and embedding call to PostgreSQL."""

import structlog
from datetime import datetime, timezone
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from src.database.engine import async_session
from src.database.models import UsageLog
from src.config.settings import settings

logger = structlog.get_logger(__name__)

# Gemini pricing (per 1M tokens)
PRICING = {
    "gemini-3.6-flash": {"input": 0.15, "output": 3.50},
    "gemini-3.5-flash": {"input": 1.50, "output": 9.00},
    "gemini-2.5-flash-lite": {"input": 0.15, "output": 0.60},
    "gemini-2.5-flash": {"input": 0.15, "output": 3.50},
    "default": {"input": 0.50, "output": 2.00},
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD based on token counts."""
    prices = PRICING.get(model, PRICING["default"])
    cost = (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000
    return round(cost, 6)


class UsageTrackingCallback(AsyncCallbackHandler):
    """LangChain callback that logs token usage to PostgreSQL."""

    def __init__(self, user_id: str, node_name: str = "unknown"):
        self.user_id = user_id
        self.node_name = node_name

    async def on_llm_end(self, response: LLMResult, **kwargs):
        """Called after every LLM call with token usage info."""
        input_tokens = 0
        output_tokens = 0
        model = "unknown"

        # Try to get usage from generation metadata (langchain-google-genai puts it here)
        if response.generations:
            for gen_list in response.generations:
                for gen in gen_list:
                    info = getattr(gen, "generation_info", None) or {}
                    usage = info.get("usage_metadata", {})
                    if usage:
                        input_tokens = usage.get("input_tokens", 0)
                        output_tokens = usage.get("output_tokens", 0)
                        break

        # Try llm_output as fallback
        if not input_tokens and response.llm_output:
            usage = response.llm_output.get("token_usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            model = response.llm_output.get("model_name", "unknown")

        if not model or model == "unknown":
            if response.llm_output:
                model = response.llm_output.get("model_name", settings.gemini_model)
            else:
                model = settings.gemini_model

        cost = _estimate_cost(model, input_tokens, output_tokens)

        # Store in DB
        try:
            async with async_session() as session:
                log = UsageLog(
                    user_id=self.user_id,
                    call_type="llm",
                    model=model,
                    node_name=self.node_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached=False,
                    cost_usd=cost,
                )
                session.add(log)
                await session.commit()
        except Exception as e:
            logger.warning("usage_log_failed", error=str(e))


async def log_llm_usage(user_id: str, node_name: str, input_tokens: int, output_tokens: int):
    """Log LLM usage directly (called from nodes with response.usage_metadata)."""
    model = settings.gemini_model
    cost = _estimate_cost(model, input_tokens, output_tokens)
    try:
        async with async_session() as session:
            log = UsageLog(
                user_id=user_id,
                call_type="llm",
                model=model,
                node_name=node_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached=False,
                cost_usd=cost,
            )
            session.add(log)
            await session.commit()
    except Exception as e:
        logger.warning("llm_usage_log_failed", error=str(e))


async def log_embedding_usage(
    user_id: str,
    model: str,
    token_count: int,
    cached: bool = False,
):
    """Log an embedding API call."""
    cost = (token_count * 0.10) / 1_000_000 if not cached else 0.0  # Gemini embedding pricing

    try:
        async with async_session() as session:
            log = UsageLog(
                user_id=user_id,
                call_type="embedding",
                model=model,
                node_name="embedding",
                input_tokens=token_count,
                output_tokens=0,
                cached=cached,
                cost_usd=round(cost, 6),
            )
            session.add(log)
            await session.commit()
    except Exception as e:
        logger.warning("embedding_usage_log_failed", error=str(e))


async def get_user_usage(user_id: str) -> dict:
    """Get usage summary for a specific user."""
    from sqlalchemy import select, func, Integer
    async with async_session() as session:
        # Total stats
        result = await session.execute(
            select(
                func.count(UsageLog.id).label("total_calls"),
                func.sum(UsageLog.input_tokens).label("total_input_tokens"),
                func.sum(UsageLog.output_tokens).label("total_output_tokens"),
                func.sum(UsageLog.cost_usd).label("total_cost"),
            ).where(UsageLog.user_id == user_id)
        )
        row = result.one()

        # By call type
        by_type = await session.execute(
            select(
                UsageLog.call_type,
                func.count(UsageLog.id).label("count"),
                func.sum(UsageLog.input_tokens).label("tokens"),
            ).where(UsageLog.user_id == user_id).group_by(UsageLog.call_type)
        )

        # Cache stats
        cache_result = await session.execute(
            select(
                func.count(UsageLog.id).label("total"),
                func.sum(func.cast(UsageLog.cached, Integer)).label("cached"),
            ).where(UsageLog.user_id == user_id, UsageLog.call_type == "embedding")
        )
        cache_row = cache_result.one()

        # Recent calls (last 20)
        recent = await session.execute(
            select(UsageLog)
            .where(UsageLog.user_id == user_id)
            .order_by(UsageLog.timestamp.desc())
            .limit(20)
        )
        recent_logs = [
            {
                "time": log.timestamp.strftime("%H:%M:%S"),
                "type": log.call_type,
                "node": log.node_name,
                "tokens": log.input_tokens + log.output_tokens,
                "cached": log.cached,
                "cost": log.cost_usd,
            }
            for log in recent.scalars().all()
        ]

    return {
        "total_calls": row.total_calls or 0,
        "total_input_tokens": row.total_input_tokens or 0,
        "total_output_tokens": row.total_output_tokens or 0,
        "total_cost_usd": round(row.total_cost or 0, 4),
        "by_type": {r.call_type: {"count": r.count, "tokens": r.tokens or 0} for r in by_type},
        "cache_hit_rate": round((cache_row.cached or 0) / max(cache_row.total or 1, 1) * 100, 1),
        "recent": recent_logs,
    }


async def get_admin_usage() -> dict:
    """Get usage summary across all users (admin view)."""
    from sqlalchemy import select, func

    async with async_session() as session:
        # Per-user summary
        per_user = await session.execute(
            select(
                UsageLog.user_id,
                func.count(UsageLog.id).label("calls"),
                func.sum(UsageLog.input_tokens + UsageLog.output_tokens).label("tokens"),
                func.sum(UsageLog.cost_usd).label("cost"),
            ).group_by(UsageLog.user_id).order_by(func.sum(UsageLog.cost_usd).desc())
        )

        # Daily totals (last 7 days)
        daily = await session.execute(
            select(
                func.date_trunc("day", UsageLog.timestamp).label("day"),
                func.count(UsageLog.id).label("calls"),
                func.sum(UsageLog.input_tokens + UsageLog.output_tokens).label("tokens"),
                func.sum(UsageLog.cost_usd).label("cost"),
            ).group_by("day").order_by("day").limit(7)
        )

    return {
        "per_user": [
            {"user_id": r.user_id, "calls": r.calls, "tokens": r.tokens or 0, "cost": round(r.cost or 0, 4)}
            for r in per_user
        ],
        "daily": [
            {"day": str(r.day)[:10], "calls": r.calls, "tokens": r.tokens or 0, "cost": round(r.cost or 0, 4)}
            for r in daily
        ],
    }
