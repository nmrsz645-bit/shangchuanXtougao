import logging
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


RETENTION_SECONDS = 72 * 60 * 60


def cleanup_logs(base_dir, now=None):
    now = time.time() if now is None else now
    logs_dir = Path(base_dir) / "logs"
    if not logs_dir.exists():
        return
    for path in logs_dir.glob("*.log*"):
        if path.is_file() and now - path.stat().st_mtime > RETENTION_SECONDS:
            path.unlink()


def get_logger(base_dir, now=None):
    base_dir = Path(base_dir)
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    cleanup_logs(base_dir, now=now)
    log_path = logs_dir / "worker.log"
    logger = logging.getLogger(f"desktop_posting.{base_dir.resolve()}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if any(isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == log_path for handler in logger.handlers):
        return logger
    handler = TimedRotatingFileHandler(log_path, when="midnight", interval=1, backupCount=0, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger
