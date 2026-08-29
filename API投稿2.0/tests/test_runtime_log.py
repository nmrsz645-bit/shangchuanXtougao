import os
import tempfile
import time
import unittest
from pathlib import Path


class RuntimeLogTests(unittest.TestCase):
    def test_cleanup_removes_only_logs_older_than_72_hours(self):
        from desktop_posting.runtime_log import cleanup_logs

        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir) / "logs"
            logs_dir.mkdir()
            expired = logs_dir / "expired.log"
            retained = logs_dir / "retained.log"
            expired.write_text("old", encoding="utf-8")
            retained.write_text("new", encoding="utf-8")
            now = time.time()
            os.utime(expired, (now - 72 * 3600 - 1, now - 72 * 3600 - 1))
            os.utime(retained, (now - 72 * 3600 + 1, now - 72 * 3600 + 1))

            cleanup_logs(Path(temp_dir), now=now)

            self.assertFalse(expired.exists())
            self.assertTrue(retained.exists())

    def test_runtime_logger_writes_to_local_log_file(self):
        from desktop_posting.runtime_log import get_logger

        with tempfile.TemporaryDirectory() as temp_dir:
            logger = get_logger(Path(temp_dir), now=0)
            logger.info("worker_result=posted")
            for handler in logger.handlers:
                handler.flush()
            files = list((Path(temp_dir) / "logs").glob("*.log"))
            self.assertEqual(1, len(files))
            self.assertIn("worker_result=posted", files[0].read_text(encoding="utf-8"))
            for handler in list(logger.handlers):
                logger.removeHandler(handler)
                handler.close()


if __name__ == "__main__":
    unittest.main()
