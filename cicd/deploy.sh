#!/usr/bin/env bash
# =============================================================================
# Production Deployment Script for JobRadar Platform
# Usage: ./deploy.sh [image_tag]
# =============================================================================

set -euo pipefail

IMAGE_TAG="${1:-latest}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.server.yml}"
API_HEALTH_URL="${API_HEALTH_URL:-http://127.0.0.1:8000/api/health}"
UI_HEALTH_URL="${UI_HEALTH_URL:-http://127.0.0.1:8501/_stcore/health}"
MAX_HEALTH_ATTEMPTS=12
SLEEP_INTERVAL=5

echo "=========================================================="
echo "Starting Deployment for JobRadar Platform (Tag: ${IMAGE_TAG})"
echo "=========================================================="

# 1. Verify .env file exists
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found in current directory. Proceeding with environment defaults."
fi

# Auto-detect whether server uses 'docker compose' or 'docker-compose'
if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
else
    echo "Error: Neither 'docker compose' nor 'docker-compose' found on server."
    exit 1
fi
echo "Using Compose command: $DC"

# 2. Pull images from GHCR
REPO_NAME="${GITHUB_REPOSITORY:-boobesh25/projects}"
echo "Pulling latest images for ${REPO_NAME}..."
docker pull "ghcr.io/${REPO_NAME}/api:${IMAGE_TAG}" || true
docker pull "ghcr.io/${REPO_NAME}/ui:${IMAGE_TAG}" || true
docker tag "ghcr.io/${REPO_NAME}/api:${IMAGE_TAG}" jobradar_api:latest || true
docker tag "ghcr.io/${REPO_NAME}/ui:${IMAGE_TAG}" jobradar_ui:latest || true

# 3. Recreate services
echo "Updating containers..."
$DC -f "${COMPOSE_FILE}" up -d

# 4. Perform Health Check
echo "Checking service health..."
HEALTHY=false
for i in $(seq 1 $MAX_HEALTH_ATTEMPTS); do
    if curl -s -f "${API_HEALTH_URL}" > /dev/null 2>&1 && curl -s -f "${UI_HEALTH_URL}" > /dev/null 2>&1; then
        echo "Health check passed on attempt $i."
        HEALTHY=true
        break
    else
        echo "Attempt $i/$MAX_HEALTH_ATTEMPTS: Services not ready yet, retrying in ${SLEEP_INTERVAL}s..."
        sleep $SLEEP_INTERVAL
    fi
done

if [ "$HEALTHY" = false ]; then
    echo "Health check failed after $MAX_HEALTH_ATTEMPTS attempts."
    $DC -f "${COMPOSE_FILE}" logs --tail 50
    exit 1
fi

# 5. Clean up dangling images
echo "Pruning dangling images..."
docker image prune -f

echo "=========================================================="
echo "Deployment successfully completed."
echo "=========================================================="
