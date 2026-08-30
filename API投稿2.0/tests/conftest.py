"""Make API posting tests runnable from any checkout without PYTHONPATH."""

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))
