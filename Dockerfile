# ─────────────────────────────────────────────────────────────────────────────
# Multi-stage Dockerfile for GenAI Project Chat API
# ─────────────────────────────────────────────────────────────────────────────

# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build-time system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python deps into a virtual env for clean copy
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir uv && \
    uvx --from mcp-server-fetch mcp-server-fetch --help || true


# Stage 2: Production runtime
FROM python:3.11-slim AS runtime

# Labels
LABEL maintainer="genai-project"
LABEL description="GenAI Project Chat API - Gemini Flash"

# Non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# Install runtime system deps (libpq for asyncpg, curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual env from builder (includes uv/uvx for MCP server)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY src/ ./src/
COPY run_api.py run_frontend.py run_mcp_server.py ./

# Ensure Python can find the src package
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default env vars (override via docker-compose or .env)
ENV API_HOST=0.0.0.0
ENV API_PORT=8000

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8000/health'); r.raise_for_status()" || exit 1

# Switch to non-root user
RUN mkdir -p /app/.cache && chown -R appuser:appuser /app/.cache
ENV UV_CACHE_DIR=/app/.cache/uv
ENV XDG_CACHE_HOME=/app/.cache
USER appuser

# Run with uvicorn (production settings)
CMD ["uvicorn", "src.api.app:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--access-log", \
     "--timeout-keep-alive", "65"]
