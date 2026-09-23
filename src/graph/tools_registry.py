"""All tools available to the ReAct agent, registered as LangChain tools."""

import math
from langchain_core.tools import tool
from src.database.csv_tables import get_user_tables, execute_sql_query
from src.rag.vectorstore import vectorstore


# ─── Calculator ──────────────────────────────────────────────────────────────

@tool
def calculator(expression: str) -> str:
    """
    Evaluate a math expression. Supports: +, -, *, /, **, sqrt, abs, round, log.
    Examples: '25 * 4', 'sqrt(10)', '0.106 * 24 * 365', 'round(928.56, 2)'
    Use this for any arithmetic or computation.
    """
    safe_funcs = {
        "sqrt": math.sqrt, "abs": abs, "round": round,
        "ceil": math.ceil, "floor": math.floor,
        "log": math.log, "log10": math.log10,
        "pi": math.pi, "e": math.e, "pow": pow,
    }
    try:
        result = eval(expression, {"__builtins__": {}}, safe_funcs)
        return str(result)
    except Exception as e:
        return f"Error: {e}"


# ─── SQL Tools (created per user) ────────────────────────────────────────────

def create_sql_tools(user_id: str, include_shared: bool = True):
    """Create user-bound SQL tools (including shared tables if enabled)."""

    @tool
    async def get_data_schema() -> str:
        """
        Get the schema of all CSV data tables for this user.
        Shows table names, column names, types, row counts, and sample rows.
        ALWAYS call this before writing SQL queries.
        """
        tables = await get_user_tables(user_id, include_shared=include_shared)
        if not tables:
            return "No CSV data tables found."

        output = []
        for table in tables:
            cols = ", ".join(f'"{c["name"]}" ({c["type"]})' for c in table["columns"])
            lines = [f'Table: "{table["table_name"]}" ({table["row_count"]} rows)']
            lines.append(f"  Columns: {cols}")
            if table.get("sample_rows"):
                lines.append(f"  Sample: {table['sample_rows'][0]}")
            output.append("\n".join(lines))
        return "\n\n".join(output)

    @tool
    async def run_sql_query(sql: str) -> str:
        """
        Execute a read-only SQL SELECT query against the user's CSV data.
        IMPORTANT: Use double quotes around table and column names.
        Example: SELECT "flavor_cost", "os_name" FROM "csv_user_table" WHERE "flavor_name" = 'Standard_B2ms'
        Call get_data_schema first to know exact table/column names.
        """
        result = await execute_sql_query(sql)
        if "error" in result:
            return f"Error: {result['error']}"
        if not result["rows"]:
            return "Query returned no results."

        columns = result["columns"]
        lines = [f"Returned {result['row_count']} rows:"]
        lines.append("| " + " | ".join(str(c) for c in columns) + " |")
        lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
        for row in result["rows"]:
            cells = [str(row.get(c, "")) for c in columns]
            lines.append("| " + " | ".join(cells) + " |")
        return "\n".join(lines)

    return [get_data_schema, run_sql_query]


# ─── RAG Tools (created per user) ────────────────────────────────────────────

def create_rag_tools(user_id: str, api_key: str = "", include_shared: bool = True):
    """Create user-bound RAG tools (searching user and shared collections)."""

    _search_call_count = {"count": 0}

    @tool
    async def list_uploaded_documents() -> str:
        """
        List all files and documents uploaded by the user or available in the knowledge base.
        Use this tool whenever the user asks to list documents, view files, or check what documents are available.
        """
        from src.database.repository import DocumentRegistryRepo
        user_docs = await DocumentRegistryRepo.get_all_documents(user_id)
        shared_docs = await DocumentRegistryRepo.get_shared_documents() if include_shared else []
        all_docs = user_docs + shared_docs

        if not all_docs:
            return "No documents uploaded yet. You can upload PDF, DOCX, CSV, TXT, or MD files in the sidebar."

        lines = ["Available Documents:"]
        for d in all_docs:
            scope = "🌐 Shared Demo" if d.get("is_shared") else "📄 Private"
            lines.append(f"- **{d['filename']}** ({d.get('doc_type', 'unknown').upper()}) [{scope}]")
        return "\n".join(lines)

    @tool
    async def search_documents(query: str) -> str:
        """
        Search uploaded text documents (TXT, DOCX, MD, PDF) for relevant info.
        Uses hybrid search (vector + keyword) with parent-child retrieval.
        Returns the most relevant text chunks with source filenames.
        NOT for CSV data — use get_data_schema and run_sql_query for CSV.
        IMPORTANT: Call this tool ONCE per user question. Do NOT retry with different queries.
        """
        _search_call_count["count"] += 1

        if _search_call_count["count"] > 2:
            return (
                "⚠️ Search limit reached. Use the results from previous searches to answer. "
                "Do NOT call this tool again."
            )

        try:
            results = await vectorstore.query(
                user_id,
                query,
                n_results=5,
                api_key=api_key,
                include_shared=include_shared,
            )
        except Exception as e:
            return f"No document results found or vector store offline: {e}"

        if not results:
            return "No relevant information found in uploaded documents."

        output_parts = []
        for i, r in enumerate(results, 1):
            output_parts.append(f"[{i}] (File: {r['filename']}, Relevance: {r['score']:.0%})\n{r['content']}")
        return "\n\n---\n\n".join(output_parts)

    return [list_uploaded_documents, search_documents]


def get_all_tools(user_id: str, api_key: str = "", include_shared: bool = True) -> list:
    """Get all tools for a user (local + MCP-backed)."""
    from src.mcp.client import get_mcp_tools
    return (
        [calculator]
        + create_sql_tools(user_id, include_shared=include_shared)
        + create_rag_tools(user_id, api_key=api_key, include_shared=include_shared)
        + get_mcp_tools()
    )

