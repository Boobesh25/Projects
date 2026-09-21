"""
Setup evaluation data by copying a user's Qdrant collection to eval_test_user.
This isolates eval data from production user data.

Usage:
    python -m eval.setup_eval_data --source_user 109146667799926584191
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from src.config.settings import settings
from src.rag.embeddings import EMBEDDING_DIM


EVAL_USER_ID = "eval_test_user"


def copy_collection(source_user_id: str):
    """Copy all points from source user's collection to eval_test_user collection."""
    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

    # Source collection name
    safe_id = source_user_id.replace(" ", "_").replace("@", "_at_").replace(".", "_")[:50]
    source_collection = f"user_{safe_id}"

    # Eval collection name
    eval_collection = f"user_{EVAL_USER_ID}"

    # Check source exists
    collections = [c.name for c in client.get_collections().collections]
    if source_collection not in collections:
        print(f"❌ Source collection '{source_collection}' not found!")
        print(f"   Available: {collections}")
        return False

    # Delete eval collection if it exists (fresh copy)
    if eval_collection in collections:
        client.delete_collection(eval_collection)
        print(f"🗑️  Deleted existing eval collection")

    # Create eval collection
    client.create_collection(
        collection_name=eval_collection,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )
    print(f"✅ Created eval collection: {eval_collection}")

    # Copy all points from source to eval
    total_copied = 0
    offset = None
    while True:
        results, offset = client.scroll(
            collection_name=source_collection,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )

        if not results:
            break

        points = [
            PointStruct(
                id=point.id,
                vector=point.vector,
                payload=point.payload,
            )
            for point in results
        ]

        client.upsert(collection_name=eval_collection, points=points)
        total_copied += len(points)
        print(f"   Copied {total_copied} points...", end="\r")

        if offset is None:
            break

    print(f"\n✅ Copied {total_copied} points to '{eval_collection}'")

    # Parent chunks don't need copying — they're looked up by parent_id (UUID)
    # which is the same in both collections. The eval collection's chunks
    # reference the same parent_ids that exist in the parent_chunks table.
    print(f"✅ Parent chunks shared (same parent_ids reference source data)")

    return True


def _copy_parent_chunks(source_user_id: str):
    """Copy parent chunks from source user to eval_test_user in PostgreSQL."""
    import asyncio

    async def _do_copy():
        from src.database.engine import async_session
        from src.database.models import ParentChunk
        from sqlalchemy import select, delete

        async with async_session() as session:
            # Delete existing eval parents
            await session.execute(
                delete(ParentChunk).where(ParentChunk.user_id == EVAL_USER_ID)
            )

            # Fetch source parents
            result = await session.execute(
                select(ParentChunk).where(ParentChunk.user_id == source_user_id)
            )
            source_parents = result.scalars().all()

            # Copy with eval user_id (keep same parent_id so Qdrant references still work)
            for parent in source_parents:
                new_parent = ParentChunk(
                    id=parent.id,  # Keep same ID so Qdrant parent_id references match
                    user_id=EVAL_USER_ID,
                    filename=parent.filename,
                    content=parent.content,
                    chunk_index=parent.chunk_index,
                )
                session.add(new_parent)

            await session.commit()
            print(f"✅ Copied {len(source_parents)} parent chunks to PostgreSQL")

    try:
        asyncio.run(_do_copy())
    except Exception as e:
        print(f"⚠️  Parent chunk copy failed (eval will use child content as fallback): {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup eval data")
    parser.add_argument("--source_user", required=True, help="Source user ID to copy from")
    args = parser.parse_args()

    print("=" * 50)
    print("  EVAL DATA SETUP")
    print("=" * 50)
    print(f"\n  Source: user_{args.source_user}")
    print(f"  Target: user_{EVAL_USER_ID}")
    print()

    success = copy_collection(args.source_user)
    if success:
        print(f"\n✅ Done! Run eval with:")
        print(f"   python -m eval.run_eval")
    else:
        print(f"\n❌ Setup failed.")
