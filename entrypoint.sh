#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "Starting JobRadar Enterprise Platform Container"
echo "=========================================================="

# Export default ports
export PORT_API=${PORT_API:-8000}
export PORT_UI=${PORT_UI:-8501}
export HOST=${HOST:-0.0.0.0}

# Run the Python process supervisor
exec python run_services.py
