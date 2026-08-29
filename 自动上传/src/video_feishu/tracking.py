from datetime import date
import json
from pathlib import Path
import threading
from typing import Callable

from .config import app_data_dir


class DailyStatsStore:
    def __init__(self, path: Path | None = None, today: Callable[[], str] | None = None):
        self.path = path or app_data_dir() / "daily_stats.json"
        self.today = today or (lambda: date.today().isoformat())
        self._lock = threading.Lock()

    def _load(self) -> dict:
        current = self.today()
        try:
            rows = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError):
            rows = {}
        if rows.get("date") != current:
            rows = {"date": current, "success": 0, "failure": 0, "events": {}}
            self._save(rows)
        return rows

    def _save(self, rows: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
        temp.replace(self.path)

    @staticmethod
    def _key(path: Path) -> str:
        size = path.stat().st_size if path.exists() else 0
        return f"{path.name}\0{size}"

    def record(self, kind: str, videos: list[Path]) -> None:
        if kind not in {"success", "failure"}:
            raise ValueError("统计类型必须是 success 或 failure")
        with self._lock:
            rows = self._load()
            events = rows["events"].setdefault(kind, [])
            known = set(events)
            for video in videos:
                key = self._key(video)
                if key not in known:
                    events.append(key)
                    known.add(key)
                    rows[kind] += 1
            self._save(rows)

    def snapshot(self) -> dict:
        with self._lock:
            rows = self._load()
            return {key: rows[key] for key in ("date", "success", "failure")}


class FeishuWriteQueue:
    def __init__(self, path: Path | None = None):
        self.path = path or app_data_dir() / "feishu_upload_queue.json"
        self._lock = threading.Lock()

    def _load(self) -> list[str]:
        try:
            return list(json.loads(self.path.read_text("utf-8")))
        except (OSError, ValueError, TypeError):
            return []

    def _save(self, names: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(names, ensure_ascii=False, indent=2), "utf-8")
        temp.replace(self.path)

    def add(self, names: list[str]) -> None:
        with self._lock:
            queued = self._load()
            known = set(queued)
            for name in names:
                if name and name not in known:
                    queued.append(name)
                    known.add(name)
            self._save(queued)

    def remove(self, names: set[str]) -> None:
        with self._lock:
            self._save([name for name in self._load() if name not in names])

    def load(self) -> list[str]:
        with self._lock:
            return self._load()

    def count(self) -> int:
        return len(self.load())
