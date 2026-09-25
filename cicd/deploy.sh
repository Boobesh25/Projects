#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Production Deployment Script for GenAI Chat API
# Usage: ./deploy.sh [image_tag]
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

IMAGE_TAG="${1:-latest}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.server.yml}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
MAX_HEALTH_ATTEMPTS=12
SLEEP_INTERVAL=5

echo "=========================================================="
echo "🚀 Starting Deployment for GenAI Chat API (Tag: ${IMAGE_TAG})"
echo "=========================================================="

# 1. Verify .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️ Warning: .env file not found in current directory! Proceeding with environment defaults."
fi

# Auto-detect whether server uses 'docker compose' (v2 plugin) or 'docker-compose' (v1/v2 standalone)
if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
else
    echo "❌ Neither 'docker compose' nor 'docker-compose' was found on the server!"
    exit 1
fi
echo "Using Compose command: $DC"

# 2. Pull the latest image
echo "📦 Pulling latest container image..."
$DC -f "${COMPOSE_FILE}" pull api

# 3. Gracefully recreate the API container
echo "🔄 Updating API container..."
$DC -f "${COMPOSE_FILE}" up -d --no-deps api

# 4. Perform Health Check
echo "🩺 Waiting for service health check (${HEALTH_URL})..."
HEALTHY=false
for i in $(seq 1 $MAX_HEALTH_ATTEMPTS); do
    if curl -s -f "${HEALTH_URL}" > /dev/null 2>&1; then
        echo "✅ Health check passed on attempt $i!"
        HEALTHY=true
        break
    else
        echo "⏳ Attempt $i/$MAX_HEALTH_ATTEMPTS: Service not ready yet, retrying in ${SLEEP_INTERVAL}s..."
        sleep $SLEEP_INTERVAL
    fi
done

if [ "$HEALTHY" = false ]; then
    echo "❌ Health check failed after $MAX_HEALTH_ATTEMPTS attempts!"
    echo "📋 Fetching recent container logs:"
    docker compose -f "${COMPOSE_FILE}" logs --tail 50 api
    exit 1
fi

# 5. Clean up dangling images to save disk space
echo "🧹 Pruning old unused images..."
docker image prune -f

echo "=========================================================="
echo "🎉 Deployment successfully completed!"
echo "=========================================================="
