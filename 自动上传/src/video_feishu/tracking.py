from datetime import date
import json
from pathlib import Path
import threading
from typing import Callable

from .config import app_data_dir


class TrackingReadError(RuntimeError):
    pass


def _read_tracking_json(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        return default
    except OSError as exc:
        raise TrackingReadError(f"无法读取 {path.name}：{exc}") from exc
    except ValueError as exc:
        raise TrackingReadError(f"{path.name} 格式不正确") from exc


class DailyStatsStore:
    def __init__(self, path: Path | None = None, today: Callable[[], str] | None = None):
        self.path = path or app_data_dir() / "daily_stats.json"
        self.today = today or (lambda: date.today().isoformat())
        self._lock = threading.Lock()

    def _load(self) -> dict:
        current = self.today()
        empty = {"date": current, "success": 0, "failure": 0, "events": {}}
        rows = _read_tracking_json(self.path, empty)
        if (
            not isinstance(rows, dict)
            or not isinstance(rows.get("date"), str)
            or any(type(rows.get(kind)) is not int for kind in ("success", "failure"))
            or not isinstance(rows.get("events"), dict)
            or any(
                not isinstance(events, list) or any(not isinstance(event, str) for event in events)
                for events in rows["events"].values()
            )
        ):
            raise TrackingReadError(f"{self.path.name} 格式不正确")
        return rows if rows["date"] == current else empty

    def _save(self, rows: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
        temp.replace(self.path)

    @staticmethod
    def _key(path: Path) -> str:
        size = path.stat().st_size if path.exists() else 0
        return f"{path.name}\0{size}"

    def record(self, kind: str, videos: list[Path]) -> str:
        if kind not in {"success", "failure"}:
            raise ValueError("统计类型必须是 success 或 failure")
        with self._lock:
            if not videos:
                return self.today()
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
            return rows["date"]

    def snapshot(self) -> dict:
        with self._lock:
            rows = self._load()
            return {key: rows[key] for key in ("date", "success", "failure")}


class FeishuWriteQueue:
    def __init__(self, path: Path | None = None, today: Callable[[], str] | None = None):
        self.path = path or app_data_dir() / "feishu_upload_queue.json"
        self.today = today or (lambda: date.today().isoformat())
        self._lock = threading.Lock()

    def _load(self) -> dict[str, str | None]:
        queued = _read_tracking_json(self.path, {})
        if isinstance(queued, dict) and all(day is None or isinstance(day, str) for day in queued.values()):
            return queued
        if isinstance(queued, list) and all(isinstance(name, str) for name in queued):
            # Older queues have names only. Keep them pending with an unknown date.
            return dict.fromkeys(queued)
        raise TrackingReadError(f"{self.path.name} 格式不正确")

    def _save(self, queued: dict[str, str | None]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(queued, ensure_ascii=False, indent=2), "utf-8")
        temp.replace(self.path)

    def add(self, names: list[str], *, day: str | None = None) -> None:
        with self._lock:
            queued = self._load()
            current = self.today() if day is None else day
            for name in names:
                if name:
                    queued[name] = max(queued.get(name) or current, current)
            self._save(queued)

    def remove(self, names: set[str]) -> None:
        with self._lock:
            self._save({name: day for name, day in self._load().items() if name not in names})

    def load(self) -> list[str]:
        with self._lock:
            return list(self._load())

    def count(self, day: str | None = None) -> int:
        with self._lock:
            queued = self._load()
            return len(queued) if day is None else sum(added == day for added in queued.values())
