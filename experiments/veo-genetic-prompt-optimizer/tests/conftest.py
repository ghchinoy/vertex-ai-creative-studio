# -*- coding: utf-8 -*-
import sys
from pathlib import Path

# Ensure experiment root is in sys.path when running pytest from any directory
EXPERIMENT_ROOT = Path(__file__).resolve().parent.parent
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))
