import re
import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at INTEGER NOT NULL DEFAULT (unixepoch())
);
CREATE TABLE IF NOT EXISTS plan_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL,
    advertiser_id TEXT NOT NULL,
    advertiser_name TEXT NOT NULL,
    project_id TEXT NOT NULL,
    project_name TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    daily_limit INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    UNIQUE(plan_id, project_id)
);
CREATE TABLE IF NOT EXISTS daily_project_counts (
    plan_id INTEGER NOT NULL,
    project_id TEXT NOT NULL,
    counter_date TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(plan_id, project_id, counter_date)
);
CREATE TABLE IF NOT EXISTS runtime_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS task_attempts (
    row_number INTEGER PRIMARY KEY,
    book_name TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_retry_at INTEGER NOT NULL DEFAULT 0,
    terminal INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '',
    name_suffix INTEGER NOT NULL DEFAULT 0,
    plan_id INTEGER,
    quota_project_id TEXT,
    advertiser_id TEXT,
    project_id TEXT,
    project_name TEXT,
    template_id TEXT
);
CREATE TABLE IF NOT EXISTS catalog_projects (
    advertiser_id TEXT NOT NULL,
    advertiser_name TEXT NOT NULL,
    project_id TEXT NOT NULL PRIMARY KEY,
    project_name TEXT NOT NULL,
    refreshed_at INTEGER NOT NULL
);
"""


class StateStore:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.db_path = self.base_dir / "data" / "state.db"

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._connect()
        try:
            connection.executescript(SCHEMA_SQL)
            existing = {row[1] for row in connection.execute("PRAGMA table_info(task_attempts)")}
            for name in ("quota_project_id", "advertiser_id", "project_id", "project_name", "template_id"):
                if name not in existing:
                    connection.execute(f"ALTER TABLE task_attempts ADD COLUMN {name} TEXT")
            if "plan_id" not in existing:
                connection.execute("ALTER TABLE task_attempts ADD COLUMN plan_id INTEGER")
            if "name_suffix" not in existing:
                connection.execute("ALTER TABLE task_attempts ADD COLUMN name_suffix INTEGER NOT NULL DEFAULT 0")
            self._assign_legacy_task_plans(connection)
            connection.commit()
        finally:
            connection.close()

    def list_plans(self):
        connection = self._connect()
        try:
            return connection.execute("SELECT id, name FROM plans ORDER BY name").fetchall()
        finally:
            connection.close()

    def create_plan(self, name):
        connection = self._connect()
        try:
            cursor = connection.execute("INSERT INTO plans(name) VALUES (?)", (name,))
            connection.commit()
            return cursor.lastrowid
        finally:
            connection.close()

    def add_plan_entry(self, plan_id, project, daily_limit):
        connection = self._connect()
        try:
            order = connection.execute("SELECT COUNT(*) FROM plan_entries WHERE plan_id=?", (plan_id,)).fetchone()[0]
            connection.execute(
                "INSERT INTO plan_entries(plan_id, advertiser_id, advertiser_name, project_id, project_name, sort_order, daily_limit) VALUES(?,?,?,?,?,?,?)",
                (plan_id, project.advertiser_id, project.advertiser_name, project.project_id, project.project_name, order, daily_limit),
            )
            connection.commit()
        finally:
            connection.close()

    def list_plan_entries(self, plan_id):
        connection = self._connect()
        try:
            return connection.execute("SELECT id, plan_id, advertiser_id, advertiser_name, project_id, project_name, sort_order, daily_limit, enabled FROM plan_entries WHERE plan_id=? ORDER BY sort_order", (plan_id,)).fetchall()
        finally:
            connection.close()

    def plan_name(self, plan_id):
        connection = self._connect()
        try:
            row = connection.execute("SELECT name FROM plans WHERE id=?", (plan_id,)).fetchone()
            return row[0] if row else ""
        finally:
            connection.close()

    def plan_speed(self, plan_id):
        """Return the saved posting speed for a plan; old plans stay fast."""
        value = self.get_state(f"plan_posting_speed_{int(plan_id)}", "fast")
        return "slow" if value == "slow" else "fast"

    def set_plan_speed(self, plan_id, speed):
        if speed not in ("fast", "slow"):
            raise ValueError("invalid posting speed")
        self.set_state(f"plan_posting_speed_{int(plan_id)}", speed)

    def plan_status(self, plan_id, counter_date):
        entries = self.list_plan_entries(plan_id)
        return [
            {
                "entry_id": row[0],
                "advertiser_id": row[2],
                "project_id": row[4],
                "project_name": row[5],
                "daily_limit": int(row[7]),
                "used": self.project_count(plan_id, row[4], counter_date),
                "remaining": max(0, int(row[7]) - self.project_count(plan_id, row[4], counter_date)),
                "status": "available" if bool(row[8]) and self.project_count(plan_id, row[4], counter_date) < int(row[7]) else "full",
            }
            for row in entries
        ]

    def increment_project_count(self, plan_id, project_id, counter_date):
        connection = self._connect()
        try:
            connection.execute("INSERT INTO daily_project_counts(plan_id, project_id, counter_date, count) VALUES(?,?,?,1) ON CONFLICT(plan_id,project_id,counter_date) DO UPDATE SET count=count+1", (plan_id, project_id, counter_date))
            connection.commit()
        finally:
            connection.close()

    def project_count(self, plan_id, project_id, counter_date):
        connection = self._connect()
        try:
            row = connection.execute("SELECT count FROM daily_project_counts WHERE plan_id=? AND project_id=? AND counter_date=?", (plan_id, project_id, counter_date)).fetchone()
            return int(row[0]) if row else 0
        finally:
            connection.close()

    def set_entry_order(self, plan_id, ordered_ids):
        connection = self._connect()
        try:
            for index, entry_id in enumerate(ordered_ids):
                connection.execute("UPDATE plan_entries SET sort_order=? WHERE id=? AND plan_id=?", (index, entry_id, plan_id))
            connection.commit()
        finally:
            connection.close()

    def update_entry_limit(self, entry_id, daily_limit):
        connection = self._connect()
        try:
            connection.execute("UPDATE plan_entries SET daily_limit=? WHERE id=?", (daily_limit, entry_id)); connection.commit()
        finally:
            connection.close()

    def update_plan_limits(self, plan_id, daily_limit):
        connection = self._connect()
        try:
            connection.execute(
                "UPDATE plan_entries SET daily_limit=? WHERE plan_id=? AND daily_limit<>?",
                (daily_limit, plan_id, daily_limit),
            )
            connection.commit()
        finally:
            connection.close()

    def delete_entry(self, entry_id):
        connection = self._connect()
        try:
            connection.execute("DELETE FROM plan_entries WHERE id=?", (entry_id,)); connection.commit()
        finally:
            connection.close()

    def delete_plan(self, plan_id):
        connection = self._connect()
        try:
            connection.execute("DELETE FROM plan_entries WHERE plan_id=?", (plan_id,)); connection.execute("DELETE FROM plans WHERE id=?", (plan_id,)); connection.commit()
        finally:
            connection.close()

    def set_state(self, key, value):
        connection = self._connect()
        try:
            connection.execute("INSERT INTO runtime_state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value))); connection.commit()
        finally:
            connection.close()

    def set_states(self, values):
        connection = self._connect()
        try:
            connection.executemany(
                "INSERT INTO runtime_state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                [(key, str(value)) for key, value in values.items()],
            )
            connection.commit()
        finally:
            connection.close()

    def get_state(self, key, default=""):
        connection = self._connect()
        try:
            row = connection.execute("SELECT value FROM runtime_state WHERE key=?", (key,)).fetchone(); return row[0] if row else default
        finally:
            connection.close()

    def record_failure(self, row_number, book_name, reason, next_retry_at):
        connection = self._connect()
        try:
            row = connection.execute("SELECT book_name,attempts FROM task_attempts WHERE row_number=?", (row_number,)).fetchone()
            attempts = (int(row[1]) if row and row[0] == book_name else 0) + 1
            terminal = int(attempts >= 3)
            if row and row[0] != book_name:
                connection.execute(
                    "UPDATE task_attempts SET book_name=?, attempts=?, next_retry_at=?, terminal=?, last_error=?, name_suffix=0, plan_id=NULL, quota_project_id=NULL, advertiser_id=NULL, project_id=NULL, project_name=NULL, template_id=NULL WHERE row_number=?",
                    (book_name, attempts, next_retry_at, terminal, reason, row_number),
                )
            else:
                connection.execute("INSERT INTO task_attempts(row_number,book_name,attempts,next_retry_at,terminal,last_error) VALUES(?,?,?,?,?,?) ON CONFLICT(row_number) DO UPDATE SET attempts=excluded.attempts,next_retry_at=excluded.next_retry_at,terminal=excluded.terminal,last_error=excluded.last_error", (row_number, book_name, attempts, next_retry_at, terminal, reason))
            connection.commit()
            return attempts, bool(terminal)
        finally:
            connection.close()

    def reserve_task_target(self, row_number, book_name, plan_id, quota_project_id, counter_date, advertiser_id, project_id, project_name, template_id):
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT book_name,project_id,plan_id FROM task_attempts WHERE row_number=?", (row_number,)).fetchone()
            if current and current[0] == book_name and current[1]:
                connection.commit()
                return False
            already_reserved = bool(current and current[0] == book_name and current[2])
            if current and current[0] == book_name:
                connection.execute(
                    "UPDATE task_attempts SET plan_id=?, quota_project_id=?, advertiser_id=?, project_id=?, project_name=?, template_id=? WHERE row_number=?",
                    (plan_id, quota_project_id, advertiser_id, project_id, project_name, template_id, row_number),
                )
            elif current:
                connection.execute(
                    "UPDATE task_attempts SET book_name=?, attempts=0, next_retry_at=0, terminal=0, last_error='', name_suffix=0, plan_id=?, quota_project_id=?, advertiser_id=?, project_id=?, project_name=?, template_id=? WHERE row_number=?",
                    (book_name, plan_id, quota_project_id, advertiser_id, project_id, project_name, template_id, row_number),
                )
            else:
                connection.execute(
                    "INSERT INTO task_attempts(row_number,book_name,plan_id,quota_project_id,advertiser_id,project_id,project_name,template_id) VALUES(?,?,?,?,?,?,?,?)",
                    (row_number, book_name, plan_id, quota_project_id, advertiser_id, project_id, project_name, template_id),
                )
            if not already_reserved:
                connection.execute(
                    "INSERT INTO daily_project_counts(plan_id,project_id,counter_date,count) VALUES(?,?,?,1) ON CONFLICT(plan_id,project_id,counter_date) DO UPDATE SET count=count+1",
                    (plan_id, quota_project_id, counter_date),
                )
            connection.commit()
            return True
        finally:
            connection.close()

    def task_target(self, row_number, book_name=None):
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT book_name,plan_id,quota_project_id,advertiser_id,project_id,project_name,template_id FROM task_attempts WHERE row_number=?",
                (row_number,),
            ).fetchone()
            if not row or (book_name is not None and row[0] != book_name) or not row[4]:
                return None
            return {"plan_id": row[1], "quota_project_id": row[2], "advertiser_id": row[3], "project_id": row[4], "project_name": row[5], "template_id": row[6]}
        finally:
            connection.close()

    def task_allowed_for_plan(self, row_number, book_name, plan_id):
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT book_name,plan_id,project_id FROM task_attempts WHERE row_number=?",
                (row_number,),
            ).fetchone()
            if not row or row[0] != book_name:
                return True
            if row[1] is not None:
                return int(row[1]) == int(plan_id)
            return not row[2]
        finally:
            connection.close()

    def promotion_name_suffix(self, row_number, book_name):
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT book_name,name_suffix FROM task_attempts WHERE row_number=?",
                (row_number,),
            ).fetchone()
            return int(row[1]) if row and row[0] == book_name else 0
        finally:
            connection.close()

    def set_promotion_name_suffix(self, row_number, book_name, suffix):
        connection = self._connect()
        try:
            connection.execute(
                "UPDATE task_attempts SET name_suffix=? WHERE row_number=? AND book_name=?",
                (int(suffix), row_number, book_name),
            )
            connection.commit()
        finally:
            connection.close()

    def clear_task_target(self, row_number):
        connection = self._connect()
        try:
            connection.execute(
                "UPDATE task_attempts SET advertiser_id=NULL, project_id=NULL, project_name=NULL, template_id=NULL WHERE row_number=?",
                (row_number,),
            )
            connection.commit()
        finally:
            connection.close()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _assign_legacy_task_plans(self, connection):
        entries = connection.execute(
            "SELECT plan_id,advertiser_id,project_id,project_name FROM plan_entries"
        ).fetchall()
        tasks = connection.execute(
            "SELECT row_number,advertiser_id,project_id,project_name FROM task_attempts WHERE plan_id IS NULL AND project_id IS NOT NULL"
        ).fetchall()
        for row_number, advertiser_id, project_id, project_name in tasks:
            matches = [
                entry for entry in entries
                if entry[1] == advertiser_id and (
                    entry[2] == project_id or self._project_base(entry[3]) == self._project_base(project_name)
                )
            ]
            plan_ids = {int(entry[0]) for entry in matches}
            if len(plan_ids) == 1:
                match = matches[0]
                connection.execute(
                    "UPDATE task_attempts SET plan_id=?, quota_project_id=? WHERE row_number=?",
                    (match[0], match[2], row_number),
                )

    @staticmethod
    def _project_base(name):
        return re.sub(r"_\d+$", "", str(name or ""))
