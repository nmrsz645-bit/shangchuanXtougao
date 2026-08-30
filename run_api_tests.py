"""Run API posting tests without passing a Chinese path through a shell."""

import os
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree

import pytest


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "API投稿2.0" / "app"))


def _github_failure_summary(report: Path) -> None:
    if not report.exists():
        return
    details = []
    for case in ElementTree.parse(report).iterfind(".//testcase"):
        failure = case.find("failure")
        if failure is None:
            failure = case.find("error")
        if failure is not None:
            details.append(f"{case.get('classname')}.{case.get('name')}: {failure.get('message', 'failed')}")
    if details:
        message = "; ".join(details)[:1500].replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=API offline tests::{message}")


with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as stream:
    report = Path(stream.name)
try:
    result = pytest.main([str(ROOT / "API投稿2.0" / "tests"), "-q", f"--junitxml={report}"])
    if result:
        _github_failure_summary(report)
finally:
    report.unlink(missing_ok=True)
raise SystemExit(result)
