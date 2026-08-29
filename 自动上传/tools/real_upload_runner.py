from dataclasses import replace
from logging.handlers import RotatingFileHandler
import argparse
import logging
from pathlib import Path
import threading
import time

from video_feishu.automation import AutoUploadCoordinator
from video_feishu.config import JsonSettingsStore, app_data_dir
from video_feishu.uploader import OceanEngineUploader


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--recover-only", action="store_true")
    args = parser.parse_args()
    directory = args.directory.resolve()
    if not directory.is_dir():
        raise SystemExit(f"目录不存在：{directory}")

    log_path = app_data_dir() / "logs" / "real-upload.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[handler, logging.StreamHandler()])

    # This controlled rerun follows a closed upload dialog. Recheck cloud IDs
    # immediately: confirmed files are recovered, the rest are safe to resubmit.
    settings = replace(
        JsonSettingsStore().load(),
        destination_dir=str(directory),
        batch_size=10,
        recovery_grace_seconds=10**9 if args.recover_only else 0,
        max_batch_attempts=1 if args.recover_only else 3,
    )
    uploader = OceanEngineUploader(settings)
    coordinator = AutoUploadCoordinator(settings, lambda: None, uploader, logging.info)
    stop = threading.Event()
    try:
        if args.recover_only:
            pending = coordinator._pending()[: settings.batch_size]
            coordinator._upload_with_retries(pending, stop)
            logging.info("恢复核对完成：本次检查=%s，剩余=%s", len(pending), len(coordinator._pending()))
            return 0
        while coordinator._pending():
            before = len(coordinator._pending())
            logging.info("真实上传循环开始：待处理=%s", before)
            coordinator.run_cycle(stop)
            after = len(coordinator._pending())
            logging.info("真实上传循环结束：剩余=%s", after)
            if after >= before:
                time.sleep(settings.upload_retry_seconds)
        logging.info("真实上传完成：目录中已无待上传视频")
        return 0
    finally:
        uploader.close()


if __name__ == "__main__":
    raise SystemExit(main())
