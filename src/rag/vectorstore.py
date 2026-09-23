"""Qdrant vector store with hybrid search (vector + full-text) and parent-child retrieval."""

import uuid
import hashlib
import structlog
from dataclasses import dataclass
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchText,
    PayloadSchemaType,
    TextIndexParams,
    TokenizerType,
)

from src.config.settings import settings
from src.rag.embeddings import embedder, EMBEDDING_DIM

logger = structlog.get_logger(__name__)


def _content_hash(text: str) -> str:
    """Generate a short hash of chunk content for deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass
class UpdateStats:
    """Statistics from an incremental update."""
    total_chunks: int
    new_chunks: int
    unchanged_chunks: int
    removed_chunks: int
    embeddings_saved: int  # How many embedding API calls were avoided

    @property
    def embedding_calls_made(self) -> int:
        return self.new_chunks

    def to_log(self) -> str:
        return (
            f"📊 Update stats:\n"
            f"  Total chunks in new version: {self.total_chunks}\n"
            f"  New/changed (re-embedded): {self.new_chunks}\n"
            f"  Unchanged (skipped): {self.unchanged_chunks}\n"
            f"  Removed (deleted): {self.removed_chunks}\n"
            f"  Embedding API calls saved: {self.embeddings_saved}"
        )


class VectorStoreService:
    """
    Single Qdrant collection per user. Content-hash based incremental embedding.
    On re-upload: only embeds chunks whose content actually changed.
    """

    def __init__(self):
        self._client: QdrantClient | None = None

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            if settings.qdrant_url:
                self._client = QdrantClient(
                    url=settings.qdrant_url,
                    api_key=settings.qdrant_api_key or None,
                )
                logger.info("qdrant_connected_cloud", url=settings.qdrant_url)
            else:
                self._client = QdrantClient(
                    host=settings.qdrant_host,
                    port=settings.qdrant_port,
                    api_key=settings.qdrant_api_key or None,
                )
                logger.info("qdrant_connected_local", host=settings.qdrant_host, port=settings.qdrant_port)
        return self._client

    def _collection_name(self, user_id: str) -> str:
        safe_id = user_id.replace(" ", "_").replace("@", "_at_").replace(".", "_")[:50]
        return f"user_{safe_id}"

    def _ensure_collection(self, user_id: str) -> str:
        """Create collection with payload indexes if it doesn't exist."""
        name = self._collection_name(user_id)
        collections = [c.name for c in self.client.get_collections().collections]
        if name not in collections:
            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
            )
            self.client.create_payload_index(name, "filename", PayloadSchemaType.KEYWORD)
            self.client.create_payload_index(name, "content_hash", PayloadSchemaType.KEYWORD)
            # Full-text index on content for native keyword search (replaces BM25 scroll)
            self.client.create_payload_index(
                collection_name=name,
                field_name="content",
                field_schema=TextIndexParams(
                    type="text",
                    tokenizer=TokenizerType.WORD,
                    min_token_len=2,
                    max_token_len=40,
                    lowercase=True,
                ),
            )
            logger.info("collection_created", name=name)
        return name

    def _get_existing_hashes(self, collection_name: str, filename: str) -> dict[str, str]:
        """
        Get all content hashes for existing chunks of a file.
        Returns: {content_hash: point_id}
        """
        existing = {}
        offset = None
        while True:
            results, offset = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(
                    must=[FieldCondition(key="filename", match=MatchValue(value=filename))]
                ),
                limit=100,
                offset=offset,
                with_payload=["content_hash"],
                with_vectors=False,
            )
            for point in results:
                h = point.payload.get("content_hash")
                if h:
                    existing[h] = point.id
            if offset is None:
                break
        return existing

    async def store_chunks(
        self,
        user_id: str,
        chunks: list[str],
        filename: str,
        document_id: str | None = None,
        api_key: str = "",
    ) -> int:
        """
        Store chunks with full replacement (first upload or force re-upload).
        """
        collection_name = self._ensure_collection(user_id)
        await self.delete_document(user_id, filename)

        if document_id is None:
            document_id = str(uuid.uuid4())

        embeddings = embedder.embed(chunks, api_key=api_key)

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "content": chunk,
                    "filename": filename,
                    "document_id": document_id,
                    "chunk_index": i,
                    "content_hash": _content_hash(chunk),
                },
            )
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]

        BATCH_SIZE = 64
        for start in range(0, len(points), BATCH_SIZE):
            self.client.upsert(collection_name=collection_name, points=points[start:start + BATCH_SIZE])

        logger.info("chunks_stored", user_id=user_id, filename=filename, count=len(chunks))
        return len(chunks)

    async def store_hierarchical(
        self,
        user_id: str,
        hierarchical_chunks: list[dict],
        filename: str,
        api_key: str = "",
    ) -> tuple[int, list[dict]]:
        """
        Store parent-child chunks with stream embed + upsert.
        - Children → Qdrant (embedded, with parent_id in payload)
        - Returns parent data to be stored in PostgreSQL separately

        Uses streaming: upserts each embedding batch to Qdrant as it completes,
        rather than waiting for all embeddings first.

        Args:
            hierarchical_chunks: output of chunk_document_hierarchical()

        Returns:
            (child_count, parents_for_db)
        """
        from src.database.repository import ParentChunkRepo
        import uuid as _uuid

        collection_name = self._ensure_collection(user_id)
        await self.delete_document(user_id, filename)

        # Delete existing parents from PostgreSQL
        await ParentChunkRepo.delete_parents(user_id, filename)

        document_id = str(_uuid.uuid4())

        # Collect unique parents for PostgreSQL storage
        parents_map: dict[str, dict] = {}
        for chunk in hierarchical_chunks:
            pid = chunk["parent_id"]
            if pid not in parents_map:
                parents_map[pid] = {
                    "id": pid,
                    "content": chunk["parent_content"],
                    "chunk_index": chunk["parent_index"],
                }

        # Stream embed + upsert: upsert each batch as embeddings arrive
        child_texts = [c["child_content"] for c in hierarchical_chunks]
        total_upserted = 0

        for batch_indices, batch_embeddings in embedder.embed_streaming(child_texts, api_key=api_key):
            batch_points = [
                PointStruct(
                    id=str(_uuid.uuid4()),
                    vector=emb,
                    payload={
                        "content": hierarchical_chunks[idx]["child_content"],
                        "parent_id": hierarchical_chunks[idx]["parent_id"],
                        "filename": filename,
                        "document_id": document_id,
                        "chunk_index": idx,
                        "content_hash": _content_hash(hierarchical_chunks[idx]["child_content"]),
                    },
                )
                for idx, emb in zip(batch_indices, batch_embeddings)
            ]

            BATCH_SIZE = 64
            for start in range(0, len(batch_points), BATCH_SIZE):
                self.client.upsert(collection_name=collection_name, points=batch_points[start:start + BATCH_SIZE])

            total_upserted += len(batch_points)

        # Store parents in PostgreSQL
        parents_list = list(parents_map.values())
        await ParentChunkRepo.store_parents(user_id, filename, parents_list)

        logger.info(
            "hierarchical_stored",
            user_id=user_id,
            filename=filename,
            children=total_upserted,
            parents=len(parents_list),
        )
        return total_upserted, parents_list

    async def store_chunks_incremental(
        self,
        user_id: str,
        chunks: list[str],
        filename: str,
        api_key: str = "",
    ) -> UpdateStats:
        """
        Incremental update: only embed chunks whose content hash doesn't exist yet.
        Removes chunks that no longer exist in the new version.
        """
        collection_name = self._ensure_collection(user_id)

        # Get existing content hashes for this file
        existing_hashes = self._get_existing_hashes(collection_name, filename)

        # Compute hashes for new chunks
        new_hashes = {_content_hash(chunk): chunk for chunk in chunks}

        # Determine what changed
        existing_set = set(existing_hashes.keys())
        new_set = set(new_hashes.keys())

        unchanged = existing_set & new_set      # Same content, keep as-is
        to_add = new_set - existing_set          # New content, needs embedding
        to_remove = existing_set - new_set       # Removed content, delete

        # Delete removed chunks
        if to_remove:
            ids_to_delete = [existing_hashes[h] for h in to_remove]
            self.client.delete(
                collection_name=collection_name,
                points_selector=ids_to_delete,
            )

        # Embed and store new chunks only
        if to_add:
            new_texts = [new_hashes[h] for h in to_add]
            embeddings = embedder.embed(new_texts, api_key=api_key)

            document_id = str(uuid.uuid4())
            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "content": text,
                        "filename": filename,
                        "document_id": document_id,
                        "chunk_index": i,
                        "content_hash": _content_hash(text),
                    },
                )
                for i, (text, embedding) in enumerate(zip(new_texts, embeddings))
            ]

            BATCH_SIZE = 64
            for start in range(0, len(points), BATCH_SIZE):
                self.client.upsert(collection_name=collection_name, points=points[start:start + BATCH_SIZE])

        stats = UpdateStats(
            total_chunks=len(chunks),
            new_chunks=len(to_add),
            unchanged_chunks=len(unchanged),
            removed_chunks=len(to_remove),
            embeddings_saved=len(unchanged),
        )

        logger.info(
            "incremental_update",
            user_id=user_id,
            filename=filename,
            new=stats.new_chunks,
            unchanged=stats.unchanged_chunks,
            removed=stats.removed_chunks,
            saved=stats.embeddings_saved,
        )
        return stats

    async def query(
        self,
        user_id: str,
        query_text: str,
        n_results: int = 5,
        filename_filter: str | None = None,
        api_key: str = "",
        include_shared: bool = True,
    ) -> list[dict]:
        """
        Hybrid search: top vector + keyword across user (and optionally shared) collections
        → merge & deduplicate → return parent content.
        """
        try:
            all_collections = [c.name for c in self.client.get_collections().collections]
        except Exception as e:
            logger.warning("qdrant_unreachable", error=str(e))
            return []

        target_collections = []

        user_col = self._collection_name(user_id)
        if user_col in all_collections:
            target_collections.append(user_col)

        shared_col = self._collection_name(settings.shared_user_id)
        if include_shared and user_id != settings.shared_user_id and shared_col in all_collections:
            target_collections.append(shared_col)

        if not target_collections:
            return []

        query_filter = None
        if filename_filter:
            query_filter = Filter(
                must=[FieldCondition(key="filename", match=MatchValue(value=filename_filter))]
            )

        query_vector = embedder.embed_query(query_text, api_key=api_key)
        candidates: dict[str, dict] = {}
        total_vector_hits = 0
        total_keyword_hits = 0

        for col_name in target_collections:
            try:
                info = self.client.get_collection(col_name)
                if info.points_count == 0:
                    continue

                # Stage 1: Vector similarity search (top 3 per collection)
                vector_results = self.client.query_points(
                    collection_name=col_name,
                    query=query_vector,
                    query_filter=query_filter,
                    limit=3,
                    with_payload=True,
                )
                total_vector_hits += len(vector_results.points)

                for point in vector_results.points:
                    content = point.payload.get("content", "")
                    h = point.payload.get("content_hash") or _content_hash(content)
                    candidates[h] = {
                        "content": content,
                        "parent_id": point.payload.get("parent_id"),
                        "filename": point.payload.get("filename", "unknown"),
                        "document_id": point.payload.get("document_id", ""),
                        "score": round(point.score, 4),
                        "source": "vector",
                    }

                # Stage 2: Keyword search (top 3 per collection)
                keyword_results = self._text_search(
                    collection_name=col_name,
                    query_text=query_text,
                    query_filter=query_filter,
                    top_k=3,
                )
                total_keyword_hits += len(keyword_results)

                for doc in keyword_results:
                    h = doc.get("content_hash") or _content_hash(doc["content"])
                    if h not in candidates:
                        candidates[h] = {
                            "content": doc["content"],
                            "parent_id": doc.get("parent_id"),
                            "filename": doc["filename"],
                            "document_id": doc.get("document_id", ""),
                            "score": doc["bm25_score"],
                            "source": "keyword",
                        }
            except Exception as e:
                logger.warning("collection_search_error", collection=col_name, error=str(e))

        if not candidates:
            return []

        # Stage 3: Sort by score and take top n_results
        merged = sorted(candidates.values(), key=lambda d: d["score"], reverse=True)

        logger.info(
            "hybrid_search",
            user_id=user_id,
            collections=target_collections,
            query=query_text[:50],
            vector_hits=total_vector_hits,
            keyword_hits=total_keyword_hits,
            merged=len(merged),
        )

        # Stage 4: Fetch parent content from PostgreSQL
        from src.database.repository import ParentChunkRepo

        top_docs = merged[:n_results]
        parent_ids = list(set(
            doc.get("parent_id") for doc in top_docs if doc.get("parent_id")
        ))
        parent_map = {}
        if parent_ids:
            parent_map = await ParentChunkRepo.get_parents_by_ids(parent_ids)

        # Stage 5: Return parent content (or child as fallback)
        retrieved = []
        for doc in top_docs:
            parent_id = doc.get("parent_id")
            content = parent_map.get(parent_id, doc["content"]) if parent_id else doc["content"]

            retrieved.append({
                "content": content,
                "filename": doc["filename"],
                "document_id": doc["document_id"],
                "score": doc["score"],
            })

        return retrieved


    def _text_search(
        self,
        collection_name: str,
        query_text: str,
        query_filter: Filter | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """
        Full-text keyword search using Qdrant's native text index.
        Prioritizes exact phrase matches over individual token matches.
        Filters out TOC/index noise.
        """
        import re

        # Use the full query as a phrase match first
        # Qdrant MatchText does substring matching on tokenized content
        query_clean = query_text.strip()

        # Build filter: match the full query phrase
        text_filter_conditions = [
            FieldCondition(key="content", match=MatchText(text=query_clean))
        ]

        # Combine with optional filename filter
        must_conditions = list(text_filter_conditions)
        if query_filter and query_filter.must:
            must_conditions.extend(query_filter.must)

        search_filter = Filter(must=must_conditions)

        # Scroll with the text filter to get matching documents
        results_list: list[dict] = []
        offset = None
        while len(results_list) < top_k:
            results, offset = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=search_filter,
                limit=min(top_k * 3, 50),  # Fetch extra to filter noise
                offset=offset,
                with_payload=["content", "filename", "document_id", "content_hash", "parent_id"],
                with_vectors=False,
            )
            for point in results:
                content = point.payload.get("content", "")

                # Skip TOC/index noise (chunks with lots of dots)
                if content.count('. .') > 3 or content.count('...') > 5:
                    continue

                # Score: exact phrase match gets highest, then partial
                content_lower = content.lower()
                query_lower = query_clean.lower()

                if query_lower in content_lower:
                    # Exact phrase found
                    score = 1.0
                else:
                    # Count individual keyword matches
                    words = re.findall(r'\w+', query_lower)
                    keywords = [w for w in words if len(w) >= 2]
                    if keywords:
                        score = sum(1 for kw in keywords if kw in content_lower) / len(keywords)
                    else:
                        score = 0.0

                if score > 0:
                    results_list.append({
                        "content": content,
                        "parent_id": point.payload.get("parent_id"),
                        "filename": point.payload.get("filename", "unknown"),
                        "document_id": point.payload.get("document_id", ""),
                        "content_hash": point.payload.get("content_hash", ""),
                        "bm25_score": score,
                    })

            if offset is None:
                break

        # Sort by score descending
        results_list.sort(key=lambda d: d["bm25_score"], reverse=True)
        return results_list[:top_k]

    async def list_documents(self, user_id: str) -> list[str]:
        """List unique filenames."""
        collection_name = self._collection_name(user_id)
        collections = [c.name for c in self.client.get_collections().collections]
        if collection_name not in collections:
            return []

        info = self.client.get_collection(collection_name)
        if info.points_count == 0:
            return []

        filenames = set()
        offset = None
        while True:
            results, offset = self.client.scroll(
                collection_name=collection_name,
                limit=100,
                offset=offset,
                with_payload=["filename"],
                with_vectors=False,
            )
            for point in results:
                fn = point.payload.get("filename")
                if fn:
                    filenames.add(fn)
            if offset is None:
                break
        return sorted(filenames)

    async def delete_document(self, user_id: str, filename: str) -> bool:
        """Delete all chunks for a file."""
        collection_name = self._collection_name(user_id)
        collections = [c.name for c in self.client.get_collections().collections]
        if collection_name not in collections:
            return False

        self.client.delete(
            collection_name=collection_name,
            points_selector=Filter(
                must=[FieldCondition(key="filename", match=MatchValue(value=filename))]
            ),
        )
        logger.info("document_deleted", user_id=user_id, filename=filename)
        return True

    async def check_chunk_overlap(self, user_id: str, chunks: list[str], exclude_filename: str | None = None) -> dict:
        """
        Check how many of the given chunks already exist across ALL user files.
        Returns overlap info: {overlapping_count, total, overlap_pct, matching_files}
        """
        collection_name = self._collection_name(user_id)
        collections = [c.name for c in self.client.get_collections().collections]
        if collection_name not in collections:
            return {"overlapping_count": 0, "total": len(chunks), "overlap_pct": 0, "matching_files": []}

        # Get ALL existing content hashes for this user
        existing_hashes: dict[str, str] = {}  # hash → filename
        offset = None
        while True:
            results, offset = self.client.scroll(
                collection_name=collection_name,
                limit=200,
                offset=offset,
                with_payload=["content_hash", "filename"],
                with_vectors=False,
            )
            for point in results:
                h = point.payload.get("content_hash")
                fn = point.payload.get("filename")
                if h and fn:
                    if exclude_filename is None or fn != exclude_filename:
                        existing_hashes[h] = fn
            if offset is None:
                break

        # Compute hashes for new chunks and check overlap
        new_hashes = [_content_hash(chunk) for chunk in chunks]
        overlapping = []
        matching_files = set()

        for h in new_hashes:
            if h in existing_hashes:
                overlapping.append(h)
                matching_files.add(existing_hashes[h])

        overlap_pct = round(len(overlapping) / len(chunks) * 100) if chunks else 0

        return {
            "overlapping_count": len(overlapping),
            "total": len(chunks),
            "overlap_pct": overlap_pct,
            "matching_files": sorted(matching_files),
        }


# Singleton
vectorstore = VectorStoreService()
