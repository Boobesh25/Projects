"""Seed evaluation database and vector store with sample documents and tables."""

import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.database import init_db
from src.database.csv_tables import load_csv_to_postgres
from src.rag.chunker import chunk_document, extract_text
from src.rag.vectorstore import vectorstore


async def seed_eval_environment(user_id: str = "ci_eval_test_user"):
    """Initialize DB and seed sample documents and CSV data for evaluation."""
    print(f"🌱 Initializing database and seeding data for user '{user_id}'...")

    # 1. Initialize Postgres tables
    try:
        await init_db()
        print("✅ Database initialized successfully.")
    except Exception as e:
        print(f"⚠️ Database initialization warning: {e}")

    # 2. Seed sample CSV sales table for SQL Analyst
    try:
        sample_csv = b"""id,product,category,revenue,sales_count\n1,Pro Subscription,SaaS,12000,10\n2,Enterprise License,SaaS,45000,5\n3,Consulting Pack,Services,8000,4\n4,Starter Plan,SaaS,3000,20\n"""
        table_name, count = await load_csv_to_postgres(user_id, "sales_dataset.csv", sample_csv)
        print(f"✅ Seeded SQL table '{table_name}' with {count} records.")
    except Exception as e:
        print(f"⚠️ CSV table seeding warning: {e}")

    # 3. Seed sample document (AI_ML_RAG_Study_Guide.md) into Qdrant vectorstore
    try:
        doc_path = Path(__file__).parent.parent / "docs" / "AI_ML_RAG_Study_Guide.md"
        if doc_path.exists():
            content = doc_path.read_text(encoding="utf-8")
            chunks = chunk_document(content, filename="AI_ML_RAG_Study_Guide.md", chunk_size=500, chunk_overlap=100)
            indexed_count = await vectorstore.index_chunks(user_id, chunks)
            print(f"✅ Seeded {indexed_count} document chunks into Qdrant for '{user_id}'.")
        else:
            print("⚠️ Sample document docs/AI_ML_RAG_Study_Guide.md not found.")
    except Exception as e:
        print(f"⚠️ Vectorstore seeding warning: {e}")

    print("🎉 Seeding complete!\n")


if __name__ == "__main__":
    user_id = sys.argv[1] if len(sys.argv) > 1 else "ci_eval_test_user"
    asyncio.run(seed_eval_environment(user_id))
