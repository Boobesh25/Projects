"""CSV to PostgreSQL table management using pandas for type inference."""

import io
import re
import structlog
import pandas as pd
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from sqlalchemy import text, create_engine
from src.database.engine import engine
from src.config.settings import settings

logger = structlog.get_logger(__name__)

# ─── Connection Pool (created once at module load) ────────────────────────────
# Sync engine for pandas to_sql - reused across all uploads
_sync_engine = None


def _get_sync_engine():
    """Get or create the shared sync SQLAlchemy engine for pandas operations."""
    global _sync_engine
    if _sync_engine is None:
        sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
        if sync_url.startswith("postgresql://"):
            sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://", 1)

        # Fix SSL parameter for psycopg2 (asyncpg uses ssl=..., psycopg2 requires sslmode=...)
        parsed = urlparse(sync_url)
        qs = parse_qs(parsed.query)
        if "ssl" in qs:
            ssl_val = qs.pop("ssl")[0]
            if ssl_val.lower() in ("require", "true", "1"):
                qs["sslmode"] = ["require"]
            elif ssl_val.lower() in ("prefer",):
                qs["sslmode"] = ["prefer"]
            elif ssl_val.lower() in ("disable", "false", "0"):
                qs["sslmode"] = ["disable"]
            else:
                qs["sslmode"] = [ssl_val]
        elif "neon.tech" in parsed.netloc and "sslmode" not in qs:
            qs["sslmode"] = ["require"]

        new_query = urlencode(qs, doseq=True)
        sync_url = urlunparse(parsed._replace(query=new_query))

        _sync_engine = create_engine(
            sync_url,
            pool_size=5,
            max_overflow=2,
            pool_pre_ping=True,
        )
        logger.info("sync_engine_created", url=re.sub(r"://[^@]+@", "://***:***@", sync_url))
    return _sync_engine


def _sanitize_name(name: str) -> str:
    """Sanitize a string to be a valid PostgreSQL identifier."""
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip().lower())
    name = re.sub(r"_+", "_", name).strip("_")
    if name and name[0].isdigit():
        name = f"col_{name}"
    return name or "unnamed"


def _table_name(user_id: str, filename: str) -> str:
    """Generate a table name from user_id and filename."""
    safe_user = _sanitize_name(user_id)[:30]
    safe_file = _sanitize_name(filename.rsplit(".", 1)[0])[:30]
    return f"csv_{safe_user}_{safe_file}"


def _pandas_dtype_to_pg(dtype) -> str:
    """Map pandas dtype to PostgreSQL type."""
    dtype_str = str(dtype)
    if "int" in dtype_str:
        return "BIGINT"
    elif "float" in dtype_str:
        return "DOUBLE PRECISION"
    elif "datetime" in dtype_str:
        return "TIMESTAMP"
    elif "bool" in dtype_str:
        return "BOOLEAN"
    else:
        return "TEXT"


async def load_csv_to_postgres(
    user_id: str, filename: str, file_bytes: bytes
) -> dict:
    """
    Load a CSV file into PostgreSQL using pandas for type inference.
    Uses the shared connection pool. Auto-indexes categorical columns.
    """
    df = pd.read_csv(io.BytesIO(file_bytes))

    if df.empty:
        raise ValueError("CSV file has no data rows.")

    # Sanitize column names
    df.columns = [_sanitize_name(c) for c in df.columns]

    # Deduplicate column names
    seen = {}
    new_cols = []
    for c in df.columns:
        if c in seen:
            seen[c] += 1
            new_cols.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 0
            new_cols.append(c)
    df.columns = new_cols

    table_name = _table_name(user_id, filename)

    # Build schema info
    columns = []
    for col in df.columns:
        pg_type = _pandas_dtype_to_pg(df[col].dtype)
        columns.append({"name": col, "type": pg_type})

    # Drop existing table (async)
    async with engine.begin() as conn:
        await conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))

    # Write with pandas using the shared sync pool
    sync_eng = _get_sync_engine()
    df.to_sql(table_name, sync_eng, if_exists="replace", index=False)

    # ─── Auto-index columns ──────────────────────────────────────────────
    # Index text columns with low cardinality (likely filters)
    # Index numeric columns (likely used in WHERE/ORDER BY)
    async with engine.begin() as conn:
        for col_info in columns:
            col_name = col_info["name"]
            col_type = col_info["type"]

            should_index = False
            if col_type == "TEXT":
                # Index text columns likely used as filters (up to 500 unique values)
                unique_count = df[col_name].nunique()
                if unique_count <= 500:
                    should_index = True
            elif col_type in ("BIGINT", "DOUBLE PRECISION"):
                should_index = True

            if should_index:
                idx_name = f"idx_{table_name}_{col_name}"[:63]
                try:
                    await conn.execute(text(
                        f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table_name}" ("{col_name}")'
                    ))
                except Exception:
                    pass  # Skip if index creation fails

    schema = {
        "table_name": table_name,
        "filename": filename,
        "columns": columns,
        "row_count": len(df),
    }

    logger.info(
        "csv_loaded_to_postgres",
        user_id=user_id,
        table=table_name,
        columns=len(columns),
        rows=len(df),
    )
    return schema


async def get_user_tables(user_id: str, include_shared: bool = True) -> list[dict]:
    """Get all CSV tables for a user (and optionally shared tables) with their schemas."""
    user_prefix = f"csv_{_sanitize_name(user_id)[:30]}_"
    shared_prefix = f"csv_{_sanitize_name(settings.shared_user_id)[:30]}_"

    async with engine.begin() as conn:
        if include_shared and user_id != settings.shared_user_id:
            result = await conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND (table_name LIKE :user_p OR table_name LIKE :shared_p)"
            ), {"user_p": f"{user_prefix}%", "shared_p": f"{shared_prefix}%"})
        else:
            result = await conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name LIKE :user_p"
            ), {"user_p": f"{user_prefix}%"})
        tables = [row[0] for row in result.fetchall()]

    schemas = []
    for table in tables:
        schema = await get_table_schema(table)
        if schema:
            schemas.append(schema)

    return schemas



async def get_table_schema(table_name: str) -> dict | None:
    """Get schema info for a specific table."""
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = :table "
            "ORDER BY ordinal_position"
        ), {"table": table_name})
        columns = [{"name": row[0], "type": row[1]} for row in result.fetchall()]

        if not columns:
            return None

        count_result = await conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
        row_count = count_result.scalar()

        sample_result = await conn.execute(text(f'SELECT * FROM "{table_name}" LIMIT 3'))
        sample_rows = [dict(row._mapping) for row in sample_result.fetchall()]

    return {
        "table_name": table_name,
        "columns": columns,
        "row_count": row_count,
        "sample_rows": sample_rows,
    }


async def execute_sql_query(sql: str) -> dict:
    """
    Execute a read-only SQL query. Only SELECT allowed.
    Auto-wraps unquoted identifiers in double quotes for PostgreSQL compatibility.
    """
    clean_sql = sql.strip()
    upper_sql = clean_sql.upper()
    if not upper_sql.startswith("SELECT"):
        return {"error": "Only SELECT queries are allowed."}

    dangerous = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "CREATE"]
    for keyword in dangerous:
        if keyword in upper_sql:
            return {"error": f"Query contains forbidden keyword: {keyword}"}

    try:
        async with engine.begin() as conn:
            result = await conn.execute(text(clean_sql))
            rows = [dict(row._mapping) for row in result.fetchmany(100)]
            columns = list(result.keys()) if rows else []

        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": len(rows) == 100,
        }
    except Exception as e:
        error_msg = str(e)
        # If it's an undefined column error, suggest using double quotes
        if "UndefinedColumn" in error_msg or "column" in error_msg.lower():
            return {
                "error": (
                    f"Column not found. Remember to use double quotes around column and table names "
                    f"in PostgreSQL. Example: SELECT \"flavor_cost\" FROM \"table_name\" WHERE \"flavor_name\" = 'value'. "
                    f"Original error: {error_msg[:200]}"
                )
            }
        return {"error": f"SQL execution error: {error_msg[:300]}"}


async def drop_user_table(user_id: str, filename: str) -> bool:
    """Drop a user's CSV table."""
    table_name = _table_name(user_id, filename)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
        logger.info("csv_table_dropped", table=table_name)
        return True
    except Exception:
        return False
