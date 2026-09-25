import os
import sys

os.environ["FX_DISABLE_NETWORK"] = "1"   # tests are deterministic/offline-safe

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)