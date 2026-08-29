import threading
import time
from pathlib import Path
from .run_once import run_once
from .runtime_log import cleanup_logs, get_logger
from .storage import StateStore


class PostingWorker:
    def __init__(self, base_dir, on_event=None):
        self.base_dir = Path(base_dir); self.on_event = on_event or (lambda _: None); self.stop_event = threading.Event(); self.thread = None; self.logger = get_logger(self.base_dir)

    def start(self):
        if self.thread and self.thread.is_alive(): return
        self.stop_event.clear(); self.thread = threading.Thread(target=self._run, daemon=True); self.thread.start()

    def stop(self): self.stop_event.set()

    def _run(self):
        self.logger.info("worker_started")
        store = StateStore(self.base_dir)
        store.initialize()
        while not self.stop_event.is_set():
            cleanup_logs(self.base_dir)
            try:
                result = run_once(self.base_dir)
                self.logger.info("worker_result=%s", result)
            except Exception as exc:
                result = "worker_error:" + str(exc)
                self.logger.exception("worker_error")
            self.on_event(result)
            if result in ("no_task", "all_projects_full", "no_active_plan"):
                delay = 30
                speed = "idle"
            else:
                plan_id = int(store.get_state("active_plan_id", "0") or 0)
                speed = store.plan_speed(plan_id) if plan_id else "fast"
                delay = 60 if speed == "slow" else 3
            store.set_states({
                "runtime_posting_speed": speed,
                "runtime_next_task_at": str(int(time.time()) + delay),
            })
            self.stop_event.wait(delay)
        self.logger.info("worker_stopped")
