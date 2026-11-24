"""
Database Engine & Connection Manager
====================================
Provides async SQLAlchemy session factory for PostgreSQL (with SQLite fallback).
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
try:
    from core.db_models import Base
except ImportError:
    from db_models import Base

RAW_DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/career_portal")

def get_clean_db_url(raw_url: str) -> str:
    url = (raw_url or "").strip().strip('"').strip("'")
    if not url:
        db_file = "data/career_portal.db" if os.path.exists("data") else "career_portal.db"
        return f"sqlite+aiosqlite:///{db_file}"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url

DATABASE_URL = get_clean_db_url(RAW_DB_URL)

_engine = None
_session_factory = None
_is_initialized = False

def get_engine():
    global _engine, DATABASE_URL
    if _engine is None:
        _engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
    return _engine

def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _session_factory

async def init_db():
    """Initializes tables on startup with seamless offline/SQLite fallback."""
    global _engine, _session_factory, DATABASE_URL, _is_initialized
    eng = get_engine()
    from sqlalchemy import text
    try:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            try:
                if "sqlite" in DATABASE_URL:
                    try:
                        await conn.execute(text("ALTER TABLE company_jobs ADD COLUMN is_active BOOLEAN DEFAULT 1;"))
                    except Exception:
                        pass
                    try:
                        await conn.execute(text("ALTER TABLE company_jobs ADD COLUMN posted_date DATETIME;"))
                    except Exception:
                        pass
                else:
                    await conn.execute(text("ALTER TABLE company_jobs ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
                    await conn.execute(text("ALTER TABLE company_jobs ADD COLUMN IF NOT EXISTS posted_date TIMESTAMP;"))
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_company_jobs_is_active ON company_jobs(is_active);"))
                    try:
                        await conn.execute(text("ALTER TABLE company_jobs ALTER COLUMN location TYPE VARCHAR(1024);"))
                        await conn.execute(text("ALTER TABLE company_jobs ALTER COLUMN title TYPE VARCHAR(512);"))
                    except Exception:
                        pass
            except Exception as e_mig:
                print(f"Migration notice: {e_mig}")
            print(f"Connected to PostgreSQL database ({DATABASE_URL})")
            _is_initialized = True
    except Exception as e:
        print(f"PostgreSQL not reachable at {DATABASE_URL} ({e}).")
        db_file = "data/career_portal.db" if os.path.exists("data") else "career_portal.db"
        print(f"Seamlessly falling back to local SQLite database ({db_file})...")
        DATABASE_URL = f"sqlite+aiosqlite:///{db_file}"
        _engine = create_async_engine(DATABASE_URL, echo=False)
        _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            try:
                try:
                    await conn.execute(text("ALTER TABLE company_jobs ADD COLUMN is_active BOOLEAN DEFAULT 1;"))
                except Exception:
                    pass
                try:
                    await conn.execute(text("ALTER TABLE company_jobs ADD COLUMN posted_date DATETIME;"))
                except Exception:
                    pass
            except Exception:
                pass
        print("Local SQLite database initialized successfully.")
        _is_initialized = True

async def ensure_db():
    if not _is_initialized:
        await init_db()

@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Async session context manager for application services."""
    await ensure_db()
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI session dependency."""
    await ensure_db()
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
