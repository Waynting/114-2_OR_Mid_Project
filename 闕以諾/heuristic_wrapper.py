"""
Thin wrapper that lets us call 林子宸's heuristic_algorithm without modifying
any file outside this folder.

The teammate's algorithm imports `from MTP_lib import *`, so we need MTP_lib.py
on the Python path. We add the teammate's folder to sys.path.

We then evaluate feasibility/profit with their find_obj_value too, since that
is the function the TA will use.
"""
from __future__ import annotations

import os
import sys
import importlib

_TEAMMATE = os.path.join(os.path.dirname(__file__), os.pardir, "林子宸")
_TEAMMATE = os.path.abspath(_TEAMMATE)
if _TEAMMATE not in sys.path:
    sys.path.insert(0, _TEAMMATE)

# import after sys.path is set
import algorithm_module  # noqa: E402
import find_obj_value as fov_mod  # noqa: E402

# refresh in case of multiple instances per session
importlib.reload(algorithm_module)
importlib.reload(fov_mod)

heuristic_algorithm = algorithm_module.heuristic_algorithm
find_obj_value = fov_mod.find_obj_value
