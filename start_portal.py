#!/usr/bin/env python3
"""
Career Portal Launcher
======================
Launches both the FastAPI REST Backend and the Streamlit UI Portal concurrently.
Usage:
  python start_portal.py
  python start_portal.py --api-only
  python start_portal.py --ui-only
"""

import os
import sys
import subprocess
import time
import argparse

def launch(api_only=False, ui_only=False):
    print("="*65)
    print("LAUNCHING JOBRADAR CAREER INTELLIGENCE PLATFORM")
    print("="*65)

    processes = []
    try:
        if not ui_only:
            print("Starting FastAPI Backend on http://localhost:8000 ...")
            api_target = "api.main:app" if os.path.exists(os.path.join("api", "main.py")) else "api_service:app"
            p_api = subprocess.Popen([
                sys.executable, "-m", "uvicorn", api_target, "--host", "0.0.0.0", "--port", "8000", "--reload"
            ])
            processes.append(p_api)
            time.sleep(2)

        if not api_only:
            print("Starting Streamlit UI Portal on http://localhost:8501 ...")
            ui_target = os.path.join("ui", "app.py") if os.path.exists(os.path.join("ui", "app.py")) else "ui_portal.py"
            p_ui = subprocess.Popen([
                sys.executable, "-m", "streamlit", "run", ui_target, "--server.port", "8501", "--server.headless", "true"
            ])
            processes.append(p_ui)

        print("\nPortal is LIVE!")
        print("   UI URL:  http://localhost:8501")
        print("   API URL: http://localhost:8000/docs")
        print("\nPress Ctrl+C to stop.\n")

        for p in processes:
            p.wait()

    except KeyboardInterrupt:
        print("\nStopping servers...")
        for p in processes:
            p.terminate()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-only", action="store_true", help="Launch FastAPI backend only")
    parser.add_argument("--ui-only", action="store_true", help="Launch Streamlit UI only")
    args = parser.parse_args()
    launch(api_only=args.api_only, ui_only=args.ui_only)

