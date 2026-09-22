"""Database engine and session factory."""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.config.settings import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=10,
    max_overflow=5,
    pool_recycle=60,       # Recycle connections every 60s to prevent stale sockets with Neon
    pool_pre_ping=True,    # Test connections prior to query execution
    pool_timeout=30,
    connect_args={
        "command_timeout": 30,
        "server_settings": {
            "application_name": "rag_project",
        },
    },
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """Create all tables and add any missing columns."""
    from src.database.models import Base
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Add Google OAuth columns if missing (for existing deployments)
        alter_statements = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(256) UNIQUE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(256)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(32) DEFAULT 'google'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS encrypted_api_key TEXT",
            # Session support
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS session_id VARCHAR(64) DEFAULT 'default'",
        ]
        for stmt in alter_statements:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass  # Column already exists or DB doesn't support IF NOT EXISTS
