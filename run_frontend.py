"""Entry point for the Streamlit frontend."""

import subprocess
import sys

if __name__ == "__main__":
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "src/frontend/app.py", "--server.port=8501"],
        check=True,
    )
