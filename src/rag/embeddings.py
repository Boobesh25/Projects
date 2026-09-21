"""Google Gemini Embedding client with Redis cache and rate limiting."""

import json
import hashlib
import time
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import redis
from google import genai
from google.genai.errors import ClientError

from src.config.settings import settings

logger = structlog.get_logger(__name__)

# Embedding dimension
EMBEDDING_DIM = 1024

# Cache TTL: 7 days (embeddings don't change for the same text)
CACHE_TTL = 60 * 60 * 24 * 7


def _cache_key(text: str) -> str:
    """Generate a Redis key from text content."""
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]
    return f"emb:{h}"


class GeminiEmbedder:
    """
    Generates embeddings using gemini-embedding-001 with Redis caching.
    - Cache hit: returns instantly from Redis (no API call)
    - Cache miss: calls Gemini API, stores result in Redis
    - Rate limited with exponential backoff retry
    """

    def __init__(self):
        self._clients: dict[str, genai.Client] = {}
        self._redis: redis.Redis | None = None
        self._last_request_time: float = 0

    def get_client(self, api_key: str | None = None) -> genai.Client:
        key = (api_key or settings.gemini_api_key).strip()
        if not key:
            raise ValueError("Google Gemini API key is required for embeddings.")
        if key not in self._clients:
            self._clients[key] = genai.Client(api_key=key)
            logger.info("gemini_embedder_initialized", model=settings.embedding_model)
        return self._clients[key]

    @property
    def client(self) -> genai.Client:
        return self.get_client()

    @property
    def cache(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(settings.redis_url, decode_responses=True)
            logger.info("redis_cache_connected", url=settings.redis_url)
        return self._redis

    def _get_cached(self, text: str) -> list[float] | None:
        """Try to get embedding from Redis cache."""
        try:
            key = _cache_key(text)
            cached = self.cache.get(key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass  # Cache miss or Redis unavailable
        return None

    def _set_cached(self, text: str, embedding: list[float]):
        """Store embedding in Redis cache."""
        try:
            key = _cache_key(text)
            self.cache.setex(key, CACHE_TTL, json.dumps(embedding))
        except Exception:
            pass  # Don't fail if Redis is down

    def _rate_limit(self):
        """Minimal delay to avoid burst rejections."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < 0.02:  # 20ms minimum between calls (paid tier)
            time.sleep(0.02 - elapsed)
        self._last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ClientError, ConnectionError, TimeoutError)),
        before_sleep=lambda retry_state: logger.warning(
            "embedding_retry", attempt=retry_state.attempt_number,
        ),
    )
    def _embed_batch_api(self, texts: list[str], api_key: str | None = None) -> list[list[float]]:
        """Call Gemini API for a batch (max 100)."""
        self._rate_limit()
        client = self.get_client(api_key)
        result = client.models.embed_content(
            model=settings.embedding_model,
            contents=texts,
            config={"output_dimensionality": EMBEDDING_DIM},
        )
        return [e.values for e in result.embeddings]

    def embed(self, texts: list[str], api_key: str | None = None) -> list[list[float]]:
        """
        Generate embeddings with Redis cache and parallel API calls.
        - Checks cache first for each text
        - Only calls API for cache misses
        - Uses concurrent threads for parallel batch processing
        """
        if not texts:
            return []

        results: list[list[float] | None] = [None] * len(texts)
        to_embed: list[tuple[int, str]] = []  # (index, text) for cache misses

        # Check cache for each text
        for i, text in enumerate(texts):
            cached = self._get_cached(text)
            if cached:
                results[i] = cached
            else:
                to_embed.append((i, text))

        cache_hits = len(texts) - len(to_embed)
        if cache_hits > 0:
            logger.debug("embedding_cache_hits", hits=cache_hits, misses=len(to_embed))

        # Embed cache misses in parallel batches
        if to_embed:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            BATCH_SIZE = 100
            MAX_PARALLEL = 5  # 5 concurrent API calls

            batches = []
            for batch_start in range(0, len(to_embed), BATCH_SIZE):
                batch = to_embed[batch_start:batch_start + BATCH_SIZE]
                batches.append(batch)

            logger.info("embedding_parallel", batches=len(batches), total_texts=len(to_embed), parallel=MAX_PARALLEL)

            def _process_batch(batch):
                batch_texts = [text for _, text in batch]
                embeddings = self._embed_batch_api(batch_texts, api_key=api_key)
                return list(zip(batch, embeddings))

            with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as executor:
                futures = {executor.submit(_process_batch, batch): batch for batch in batches}
                for future in as_completed(futures):
                    try:
                        batch_results = future.result()
                        for (idx, text), embedding in batch_results:
                            results[idx] = embedding
                            self._set_cached(text, embedding)
                    except Exception as e:
                        logger.error("embedding_batch_failed", error=str(e))
                        # Fill failed batch with zero vectors as fallback
                        batch = futures[future]
                        for idx, text in batch:
                            results[idx] = [0.0] * EMBEDDING_DIM

        return results  # type: ignore

    def embed_streaming(self, texts: list[str], batch_size: int = 100, api_key: str | None = None):
        """
        Generator that yields (batch_indices, batch_embeddings) as each batch completes.

        Instead of waiting for ALL embeddings, this yields results incrementally
        so the caller can start upserting to Qdrant while later batches are still embedding.

        Yields:
            tuple[list[int], list[list[float]]]: (original indices, embeddings) per batch
        """
        if not texts:
            return

        # Separate cache hits from misses
        cache_hits: list[tuple[int, list[float]]] = []
        to_embed: list[tuple[int, str]] = []

        for i, text in enumerate(texts):
            cached = self._get_cached(text)
            if cached:
                cache_hits.append((i, cached))
            else:
                to_embed.append((i, text))

        if cache_hits:
            logger.debug("streaming_cache_hits", hits=len(cache_hits), misses=len(to_embed))

        # Yield cache hits immediately in one batch
        if cache_hits:
            hit_indices = [idx for idx, _ in cache_hits]
            hit_embeddings = [emb for _, emb in cache_hits]
            yield hit_indices, hit_embeddings

        # Process API misses in batches, yielding each as it completes
        if to_embed:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            MAX_PARALLEL = 3  # Reduced to avoid rate limit congestion

            # Split into API batches
            batches: list[list[tuple[int, str]]] = []
            for batch_start in range(0, len(to_embed), batch_size):
                batches.append(to_embed[batch_start:batch_start + batch_size])

            logger.info(
                "embedding_streaming_start",
                batches=len(batches),
                total_texts=len(to_embed),
                parallel=MAX_PARALLEL,
            )

            def _process_batch(batch):
                batch_texts = [text for _, text in batch]
                embeddings = self._embed_batch_api(batch_texts, api_key=api_key)
                # Cache results
                for (_, text), emb in zip(batch, embeddings):
                    self._set_cached(text, emb)
                return batch, embeddings

            with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as executor:
                futures = {executor.submit(_process_batch, batch): batch for batch in batches}
                for future in as_completed(futures):
                    try:
                        batch, embeddings = future.result()
                        batch_indices = [idx for idx, _ in batch]
                        yield batch_indices, embeddings
                    except Exception as e:
                        logger.error("streaming_batch_failed", error=str(e))
                        batch = futures[future]
                        batch_indices = [idx for idx, _ in batch]
                        yield batch_indices, [[0.0] * EMBEDDING_DIM] * len(batch)

    def embed_query(self, query: str, api_key: str | None = None) -> list[float]:
        """Generate embedding for a single query (cached)."""
        return self.embed([query], api_key=api_key)[0]


# Singleton
embedder = GeminiEmbedder()
