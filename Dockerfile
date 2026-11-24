# =============================================================================
# JobRadar Platform - Unified All-in-One Container Dockerfile
# Runs both FastAPI backend (port 8000) and Streamlit frontend (port 8501)
# =============================================================================
FROM python:3.11-slim AS base

# System build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application directories & assets
COPY api/ ./api/
COPY ui/ ./ui/
COPY core/ ./core/
COPY analyzer/ ./analyzer/
COPY data/ ./data/
COPY enterprise_company_directory.json* ./
COPY PROFILE.md* ./
COPY profile.yaml* ./
COPY run_services.py .
COPY entrypoint.sh .

# Ensure entrypoint is executable
RUN chmod +x entrypoint.sh

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PORT_API=8000 \
    PORT_UI=8501 \
    HOST=0.0.0.0 \
    API_BASE_URL=http://localhost:8000 \
    DATABASE_URL=sqlite+aiosqlite:////app/career_portal.db

# Expose both backend API and frontend Streamlit ports
EXPOSE 8000 8501

# Healthcheck checking backend API readiness
HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health && curl -f http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["./entrypoint.sh"]
