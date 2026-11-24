"""
Streamlit Community Cloud Root Entrypoint
=========================================
Forwards execution to ui/app.py while ensuring proper module resolution.
"""
import os
import sys
import runpy
from pathlib import Path

# Add project root and core to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
core_dir = root_dir / "core"
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))

# Execute UI portal
ui_script = root_dir / "ui" / "app.py"
runpy.run_path(str(ui_script), run_name="__main__")
