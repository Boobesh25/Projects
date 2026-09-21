"""FastAPI application factory."""

from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.database import init_db
from src.api.routes import router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("initializing database")
    await init_db()
    logger.info("database ready")

    # Flush answer cache on startup (ensures fresh state after code updates)
    try:
        import redis
        from src.config.settings import settings
        r = redis.from_url(settings.redis_url)
        # Only flush answer cache keys, not embedding cache
        for key in r.scan_iter("ans:*"):
            r.delete(key)
        logger.info("answer_cache_flushed_on_startup")
    except Exception as e:
        logger.warning("redis_flush_failed", error=str(e))

    yield
    logger.info("app shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="GenAI Project Chat API",
        description="Real-time chat with a Gemini Flash powered multi-agent team",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS for Streamlit frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    return app


app = create_app()
