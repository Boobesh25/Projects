"""
JobRadar Platform - Unified Concurrent Service Runner
=====================================================
Starts both the FastAPI Backend API (port 8000) and the Streamlit UI Portal (port 8501)
concurrently within a single process supervisor.
Supports graceful shutdown on SIGINT / SIGTERM.
"""

import os
import sys
import time
import signal
import subprocess
import urllib.request

# Ensure current directory is root
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

API_PORT = int(os.getenv("PORT_API", "8000"))
UI_PORT = int(os.getenv("PORT_UI", "8501"))
HOST = os.getenv("HOST", "0.0.0.0")

processes = []

def signal_handler(sig, frame):
    print("\nShutting down JobRadar Platform services...")
    for p in processes:
        try:
            p.terminate()
            p.wait(timeout=3)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def wait_for_api(url, timeout=20):
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def main():
    print("=" * 60)
    print("JobRadar Enterprise Career Intelligence Platform")
    print(f"API Port: {API_PORT} | UI Port: {UI_PORT}")
    print("=" * 60)

    # 1. Start FastAPI Backend API
    api_cmd = [
        sys.executable, "-m", "uvicorn",
        "api.main:app",
        "--host", HOST,
        "--port", str(API_PORT)
    ]
    print(f"Starting Backend API: {' '.join(api_cmd)}")
    api_proc = subprocess.Popen(api_cmd, cwd=BASE_DIR)
    processes.append(api_proc)

    # Wait for API to become ready
    health_url = f"http://localhost:{API_PORT}/api/health"
    print(f"Waiting for API service at {health_url}...")
    if wait_for_api(health_url, timeout=25):
        print("Backend API is ready.")
    else:
        print("API healthcheck timed out, proceeding to start UI...")

    # 2. Start Streamlit UI Portal
    ui_cmd = [
        sys.executable, "-m", "streamlit", "run",
        os.path.join(BASE_DIR, "ui", "app.py"),
        f"--server.port={UI_PORT}",
        f"--server.address={HOST}",
        "--server.headless=true"
    ]
    print(f"Starting Streamlit Portal: {' '.join(ui_cmd)}")
    ui_proc = subprocess.Popen(ui_cmd, cwd=BASE_DIR)
    processes.append(ui_proc)

    print("\nAll JobRadar services running:")
    print(f"  - UI Portal: http://localhost:{UI_PORT}")
    print(f"  - API Docs:  http://localhost:{API_PORT}/docs")
    print("Press Ctrl+C to terminate all services.\n")

    try:
        while True:
            # Check if any process terminated unexpectedly
            for p in processes:
                code = p.poll()
                if code is not None:
                    print(f"Process PID {p.pid} exited with code {code}.")
                    signal_handler(None, None)
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()
