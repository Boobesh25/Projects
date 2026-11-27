#!/bin/bash
set -e

# Kill any existing worker processes
pkill -f cloud_sync_worker.py || true
sleep 1

# Start worker in background writing to sync.log with unbuffered output
echo "Starting cloud_sync_worker.py..."
nohup python3 -u /home/sboobesh/scripts/cloud_sync_worker.py > /home/sboobesh/scripts/sync.log 2>&1 &
WORKER_PID=$!
echo "Started cloud_sync_worker with PID: $WORKER_PID"

sleep 3

# Check if process is running
if ps -p $WORKER_PID > /dev/null; then
    echo "Worker process $WORKER_PID is RUNNING successfully."
else
    echo "Worker process $WORKER_PID terminated immediately. Checking log:"
    cat /home/sboobesh/scripts/sync.log
    exit 1
fi

echo "--- Recent sync.log output ---"
head -n 30 /home/sboobesh/scripts/sync.log || true
