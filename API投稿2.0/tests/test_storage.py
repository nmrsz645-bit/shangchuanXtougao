import tempfile
import unittest
from pathlib import Path
import sqlite3


class StateStoreTests(unittest.TestCase):
    def test_clear_task_target_keeps_retry_metadata_but_removes_project_lock(self):
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(directory)
            store.initialize()
            store.reserve_task_target(7, "Book", 1, "quota-project", "2026-07-14", "account", "project", "Project_4", "template")
            store.record_failure(7, "Book", "capacity limit", 123)

            store.clear_task_target(7)

            self.assertIsNone(store.task_target(7))
            connection = store._connect()
            try:
                row = connection.execute("SELECT attempts, last_error FROM task_attempts WHERE row_number=7").fetchone()
            finally:
                connection.close()
            self.assertEqual(1, row[0])
            self.assertEqual("capacity limit", row[1])
    def test_initialize_creates_only_local_database(self):
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = StateStore(root)
            store.initialize()
            self.assertTrue((root / "data" / "state.db").exists())
            self.assertEqual([], store.list_plans())

    def test_first_target_reservation_uses_one_quota_and_persists_exact_project(self):
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder))
            store.initialize()
            reserved = store.reserve_task_target(
                row_number=12, book_name="Book", plan_id=7, quota_project_id="logical-project",
                counter_date="2026-07-11", advertiser_id="account-a", project_id="exact-project-6",
                project_name="项目【1】_6", template_id="template-9",
            )
            reserved_again = store.reserve_task_target(
                row_number=12, book_name="Book", plan_id=7, quota_project_id="logical-project",
                counter_date="2026-07-11", advertiser_id="account-a", project_id="other-project",
                project_name="项目【1】_7", template_id="template-10",
            )

            self.assertTrue(reserved)
            self.assertFalse(reserved_again)
            self.assertEqual(1, store.project_count(7, "logical-project", "2026-07-11"))
            self.assertEqual(
                {"plan_id": 7, "quota_project_id": "logical-project", "advertiser_id": "account-a", "project_id": "exact-project-6", "project_name": "项目【1】_6", "template_id": "template-9"},
                store.task_target(12),
            )

    def test_initialize_migrates_existing_task_attempts_table(self):
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data").mkdir()
            connection = sqlite3.connect(root / "data" / "state.db")
            try:
                connection.execute("CREATE TABLE task_attempts (row_number INTEGER PRIMARY KEY, book_name TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, next_retry_at INTEGER NOT NULL DEFAULT 0, terminal INTEGER NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '')")
                connection.commit()
            finally:
                connection.close()
            store = StateStore(root)
            store.initialize()

            self.assertTrue(store.reserve_task_target(2, "Book", 1, "logical", "2026-07-11", "a", "exact", "项目_6", "template"))
            self.assertEqual("exact", store.task_target(2)["project_id"])

    def test_initialize_assigns_legacy_retry_to_its_unique_plan(self):
        from desktop_posting.models import ProjectRef
        from desktop_posting.plans import add_plan_entry, create_plan
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder)); store.initialize()
            plan_id = create_plan(store, "Plan A")
            add_plan_entry(store, plan_id, ProjectRef("account", "Account", "logical-5", "Project_5"), 10)
            connection = store._connect()
            try:
                connection.execute(
                    "INSERT INTO task_attempts(row_number,book_name,advertiser_id,project_id,project_name,template_id) VALUES(?,?,?,?,?,?)",
                    (12, "Book", "account", "exact-6", "Project_6", "template"),
                )
                connection.commit()
            finally:
                connection.close()

            store.initialize()

            self.assertEqual(plan_id, store.task_target(12, "Book")["plan_id"])
            self.assertEqual("logical-5", store.task_target(12, "Book")["quota_project_id"])

    def test_retry_task_is_only_allowed_for_its_original_plan(self):
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder)); store.initialize()
            store.reserve_task_target(12, "Book", 7, "logical", "2026-07-11", "account", "project", "Project_1", "template")

            self.assertTrue(store.task_allowed_for_plan(12, "Book", 7))
            self.assertFalse(store.task_allowed_for_plan(12, "Book", 8))
            self.assertTrue(store.task_allowed_for_plan(12, "Different Book", 8))

            store.clear_task_target(12)
            self.assertTrue(store.task_allowed_for_plan(12, "Book", 7))
            self.assertFalse(store.task_allowed_for_plan(12, "Book", 8))

    def test_new_book_on_reused_row_does_not_inherit_old_failure_state(self):
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder)); store.initialize()
            store.reserve_task_target(12, "Old Book", 7, "logical", "2026-07-11", "account", "project", "Project_1", "template")
            store.record_failure(12, "Old Book", "old failure", 123)

            attempts, terminal = store.record_failure(12, "New Book", "new failure", 456)

            self.assertEqual(1, attempts)
            self.assertFalse(terminal)
            self.assertIsNone(store.task_target(12, "New Book"))

    def test_reassigning_same_task_does_not_consume_quota_twice(self):
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder)); store.initialize()
            store.reserve_task_target(12, "Book", 7, "logical", "2026-07-11", "account", "project-1", "Project_1", "template")
            store.clear_task_target(12)
            store.reserve_task_target(12, "Book", 7, "logical", "2026-07-11", "account", "project-2", "Project_2", "template")

            self.assertEqual(1, store.project_count(7, "logical", "2026-07-11"))

    def test_duplicate_name_suffix_is_persisted_for_the_same_book(self):
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder)); store.initialize()
            store.reserve_task_target(12, "Book", 7, "logical", "2026-07-11", "account", "project", "Project_1", "template")
            store.set_promotion_name_suffix(12, "Book", 51)

            self.assertEqual(51, store.promotion_name_suffix(12, "Book"))
            self.assertEqual(0, store.promotion_name_suffix(12, "Different Book"))
    def test_plan_status_reports_used_and_remaining_quota_in_order(self):
        from desktop_posting.models import ProjectRef
        from desktop_posting.plans import add_plan_entry, create_plan
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder)); store.initialize()
            plan_id = create_plan(store, "Plan A")
            add_plan_entry(store, plan_id, ProjectRef("account-1", "Account 1", "project-1", "Project 1"), 3)
            add_plan_entry(store, plan_id, ProjectRef("account-2", "Account 2", "project-2", "Project 2"), 2)
            store.increment_project_count(plan_id, "project-1", "2026-07-15")
            store.increment_project_count(plan_id, "project-1", "2026-07-15")

            self.assertEqual(
                [
                    {"entry_id": 1, "advertiser_id": "account-1", "project_id": "project-1", "project_name": "Project 1", "daily_limit": 3, "used": 2, "remaining": 1, "status": "available"},
                    {"entry_id": 2, "advertiser_id": "account-2", "project_id": "project-2", "project_name": "Project 2", "daily_limit": 2, "used": 0, "remaining": 2, "status": "available"},
                ],
                store.plan_status(plan_id, "2026-07-15"),
            )


if __name__ == "__main__":
    unittest.main()
