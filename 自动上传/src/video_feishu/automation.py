from dataclasses import dataclass
import logging
from pathlib import Path
import threading
import time
from typing import Callable, Protocol

from .config import Settings
from .video_ops import is_ready_video


@dataclass(frozen=True)
class UploadBatchResult:
    succeeded: tuple[Path, ...] = ()
    failed: tuple[Path, ...] = ()
    uncertain: tuple[Path, ...] = ()
    retry_now: tuple[Path, ...] = ()
    permanent: tuple[Path, ...] = ()


class BatchUploader(Protocol):
    def upload_batch(self, videos: list[Path]) -> UploadBatchResult: ...


class AutoUploadCoordinator:
    def __init__(
        self,
        settings: Settings,
        extract: Callable[[], None],
        uploader: BatchUploader,
        status: Callable[[str], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        on_succeeded: Callable[[list[Path]], None] | None = None,
        on_failed: Callable[[list[Path]], None] | None = None,
        maintenance: Callable[[], None] | None = None,
    ):
        self.settings = settings
        self.extract = extract
        self.uploader = uploader
        self.status = status or (lambda _: None)
        self.sleep = sleep
        self.on_succeeded = on_succeeded or (lambda _: None)
        self.on_failed = on_failed or (lambda _: None)
        self.maintenance = maintenance or (lambda: None)

    def _pending(self) -> list[Path]:
        destination = Path(self.settings.destination_dir)
        destination.mkdir(parents=True, exist_ok=True)
        return sorted(
            (path for path in destination.iterdir() if is_ready_video(path)),
            key=lambda path: path.name.lower(),
        )

    def _restore_deferred(self) -> None:
        destination = Path(self.settings.destination_dir)
        failed_dir = destination / "上传失败"
        if not failed_dir.is_dir():
            return
        cutoff = time.time() - self.settings.check_interval_minutes * 60
        for path in failed_dir.iterdir():
            if not is_ready_video(path) or path.stat().st_mtime > cutoff:
                continue
            target = destination / path.name
            if not target.exists():
                path.replace(target)
                self.status(f"重新尝试上传：{path.name}")

    def _skip_permanently(self, videos: list[Path]) -> None:
        if not videos:
            return
        skipped_dir = Path(self.settings.destination_dir) / "永久跳过"
        skipped_dir.mkdir(parents=True, exist_ok=True)
        for path in videos:
            if not path.exists():
                continue
            target = skipped_dir / path.name
            if target.exists():
                target = skipped_dir / f"{path.stem}-{int(time.time())}{path.suffix}"
            path.replace(target)
            self.status(f"连续失败 3 次，永久跳过：{target.name}")

    def _upload_with_retries(self, batch: list[Path], stop: threading.Event) -> list[Path]:
        remaining = batch
        attempts = 0
        while remaining and not stop.is_set() and attempts < self.settings.max_batch_attempts:
            attempts += 1
            self.status(f"正在上传 {len(remaining)} 条视频")
            result = self.uploader.upload_batch(remaining)
            expected = {path.resolve(): path for path in remaining}
            succeeded = {path.resolve() for path in result.succeeded}
            failed = {path.resolve() for path in result.failed}
            uncertain = {path.resolve() for path in result.uncertain}
            retry_now = {path.resolve() for path in result.retry_now}
            permanent = {path.resolve() for path in result.permanent}
            if not succeeded <= expected.keys() or not failed <= expected.keys() or not uncertain <= expected.keys() or not retry_now <= expected.keys() or not permanent <= expected.keys():
                raise ValueError("上传结果包含本批次之外的文件")
            succeeded_paths = [expected[resolved] for resolved in succeeded]
            self.on_succeeded(succeeded_paths)
            for resolved in succeeded:
                expected[resolved].unlink(missing_ok=True)
            acknowledge = getattr(self.uploader, "acknowledge", None)
            if acknowledge and succeeded:
                acknowledge([expected[resolved] for resolved in succeeded])
            remaining = [path for path in remaining if path.resolve() not in succeeded]
            permanently_skipped = [expected[resolved] for resolved in permanent]
            self.on_failed(permanently_skipped)
            self._skip_permanently(permanently_skipped)
            if permanently_skipped:
                acknowledge = getattr(self.uploader, "acknowledge", None)
                if acknowledge:
                    acknowledge(permanently_skipped)
            remaining = [path for path in remaining if path.resolve() not in permanent]
            if remaining and attempts < self.settings.max_batch_attempts:
                if retry_now:
                    self.status(f"{len(remaining)} 条上传后未确认，立即重试")
                    continue
                self.status(f"{len(remaining)} 条上传失败，稍后自动重试")
                if stop.wait(self.settings.upload_retry_seconds):
                    break
        if remaining and not stop.is_set():
            self.on_failed(remaining)
            self._skip_permanently(remaining)
            acknowledge = getattr(self.uploader, "acknowledge", None)
            if acknowledge:
                acknowledge(remaining)
        return remaining

    def run_cycle(self, stop: threading.Event) -> bool:
        self.maintenance()
        self._restore_deferred()
        pending = self._pending()
        if not pending:
            self.status("目标文件夹为空，正在提取视频")
            self.extract()
            pending = self._pending()
        if not pending:
            return False
        # Process the current queue once so a permanently bad file cannot block
        # all later batches. Remaining failures are picked up in the next cycle.
        for offset in range(0, len(pending), self.settings.batch_size):
            if stop.is_set():
                break
            self._upload_with_retries(pending[offset : offset + self.settings.batch_size], stop)
        return True

    def run_forever(self, stop: threading.Event, wake: threading.Event | None = None) -> None:
        wake = wake or threading.Event()
        while not stop.is_set():
            try:
                processed = self.run_cycle(stop)
            except Exception as exc:
                logging.exception("自动上传循环异常")
                self.status(f"自动上传异常：{exc}；稍后自动恢复")
                reset = getattr(self.uploader, "reset", None)
                if reset:
                    try:
                        reset()
                    except Exception:
                        pass
                if stop.wait(self.settings.upload_retry_seconds):
                    return
                continue
            if stop.is_set():
                return
            if not processed:
                minutes = self.settings.check_interval_minutes
                self.status(f"暂无视频，{minutes} 分钟后再次检查")
                wake.wait(minutes * 60)
                wake.clear()
