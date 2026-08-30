"""Run API posting tests without passing a Chinese path through a shell."""

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "API投稿2.0" / "app"))
raise SystemExit(pytest.main([str(ROOT / "API投稿2.0" / "tests"), "-q"]))
