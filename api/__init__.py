"""
JobRadar Platform Backend API Module (FastAPI)
"""

import os
import sys

_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _base_dir not in sys.path:
    sys.path.insert(0, _base_dir)

_core_dir = os.path.join(_base_dir, "core")
if _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)
