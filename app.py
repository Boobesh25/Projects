"""
Unified entry point for Hugging Face Spaces (Streamlit SDK).
Launches FastAPI backend on 127.0.0.1:8000 in background and serves Streamlit UI on 0.0.0.0:7860.
"""

import os
import sys
import time
import socket
import threading
import structlog
import uvicorn
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger(__name__)


def _is_port_open(port: int = 8000) -> bool:
    """Check if the backend FastAPI server is listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _start_fastapi_server():
    """Start the FastAPI backend server on 127.0.0.1:8000."""
    from src.api.app import app as fastapi_app
    logger.info("starting_fastapi_background_server", port=8000)
    uvicorn.run(fastapi_app, host="127.0.0.1", port=8000, log_level="warning")


# Ensure backend is running before Streamlit connects
if not _is_port_open(8000):
    backend_thread = threading.Thread(target=_start_fastapi_server, daemon=True)
    backend_thread.start()
    
    # Wait for backend to be ready
    for _ in range(30):
        if _is_port_open(8000):
            logger.info("fastapi_backend_ready_on_8000")
            break
        time.sleep(0.5)

# Set backend URL for frontend requests
os.environ["API_BASE_URL"] = "http://127.0.0.1:8000"

# Run Streamlit frontend UI
from src.frontend.app import main

if __name__ == "__main__":
    main()
