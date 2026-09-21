"""Per-user full answer cache using Redis.

Cache key = hash(user_id + normalized_question + data_version)
- data_version increments on every upload/delete for that user
- Cache is automatically invalidated when data changes
- TTL: 1 hour for data queries, 24 hours for general/math
"""

import json
import hashlib
import structlog
import redis as redis_lib

from src.config.settings import settings

logger = structlog.get_logger(__name__)

# TTL by intent type
CACHE_TTL = {
    "data": 3600,       # 1 hour (data might be re-uploaded)
    "rag": 14400,       # 4 hours (docs change less)
    "math": 86400,      # 24 hours (never changes)
    "general": 86400,   # 24 hours
}

_redis: redis_lib.Redis | None = None


def _get_redis() -> redis_lib.Redis:
    global _redis
    if _redis is None:
        _redis = redis_lib.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _normalize_query(question: str) -> str:
    """Normalize question for cache key: lowercase, strip, collapse spaces."""
    return " ".join(question.lower().strip().split())


def _cache_key(user_id: str, question: str) -> str:
    """Generate cache key including data version for invalidation."""
    r = _get_redis()
    data_version = r.get(f"data_version:{user_id}") or "0"
    normalized = _normalize_query(question)
    raw = f"{user_id}:{normalized}:v{data_version}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:24]
    return f"ans:{h}"


def get_cached_answer(user_id: str, question: str) -> str | None:
    """Try to get a cached answer. Returns None on miss."""
    try:
        r = _get_redis()
        key = _cache_key(user_id, question)
        cached = r.get(key)
        if cached:
            logger.debug("answer_cache_hit", user_id=user_id, question=question[:50])
            return cached
    except Exception:
        pass
    return None


def set_cached_answer(user_id: str, question: str, answer: str, intent: str):
    """Store answer in cache with appropriate TTL."""
    try:
        r = _get_redis()
        key = _cache_key(user_id, question)
        ttl = CACHE_TTL.get(intent, 3600)
        r.setex(key, ttl, answer)
        logger.debug("answer_cached", user_id=user_id, intent=intent, ttl=ttl)
    except Exception:
        pass


def invalidate_user_cache(user_id: str):
    """Invalidate all cached answers for a user (called on data upload/delete)."""
    try:
        r = _get_redis()
        # Increment data version — all old cache keys become unreachable
        r.incr(f"data_version:{user_id}")
        logger.info("user_cache_invalidated", user_id=user_id)
    except Exception:
        pass
