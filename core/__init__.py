"""
JobRadar Platform Core Domain Services & Data Models
"""

import os
import sys

# Ensure parent directory (jobradar_platform root) is in sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_current_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)
