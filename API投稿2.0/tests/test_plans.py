from concurrent.futures import ThreadPoolExecutor
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path


class PlanTests(unittest.TestCase):
    def test_quota_switches_to_next_ordered_project(self):
        from desktop_posting.plans import add_plan_entry, choose_active_entry, create_plan
        from desktop_posting.models import ProjectRef
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder)); store.initialize()
            plan_id = create_plan(store, "测试")
            first = ProjectRef("a", "账户A", "p1", "项目1")
            second = ProjectRef("a", "账户A", "p2", "项目2")
            add_plan_entry(store, plan_id, first, 2)
            add_plan_entry(store, plan_id, second, 3)
            store.increment_project_count(plan_id, "p1", "2026-07-10")
            store.increment_project_count(plan_id, "p1", "2026-07-10")
            self.assertEqual("p2", choose_active_entry(store, plan_id, "2026-07-10").project.project_id)

    def test_move_entry_persists_project_order(self):
        from desktop_posting.plans import add_plan_entry, create_plan, move_entry
        from desktop_posting.models import ProjectRef
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder)); store.initialize(); plan_id = create_plan(store, "测试")
            add_plan_entry(store, plan_id, ProjectRef("a", "A", "p1", "项目1"), 1)
            add_plan_entry(store, plan_id, ProjectRef("a", "A", "p2", "项目2"), 1)
            second_id = store.list_plan_entries(plan_id)[1][0]
            move_entry(store, plan_id, second_id, -1)
            self.assertEqual(["p2", "p1"], [row[4] for row in store.list_plan_entries(plan_id)])

    def test_project_picker_label_contains_account_and_project(self):
        from desktop_posting.plans import project_picker_label
        from desktop_posting.models import ProjectRef

        self.assertEqual("账户 100 | 项目A", project_picker_label(ProjectRef("100", "账户 100", "p", "项目A")))

    def test_daily_limit_validation_rejects_zero(self):
        from desktop_posting.plans import valid_daily_limit

        self.assertEqual(12, valid_daily_limit("12"))
        with self.assertRaises(ValueError):
            valid_daily_limit("0")

    def test_plan_speed_defaults_to_fast_and_persists_slow(self):
        from desktop_posting.plans import create_plan
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder)); store.initialize()
            plan_id = create_plan(store, "Speed Plan")
            self.assertEqual("fast", store.plan_speed(plan_id))
            store.set_plan_speed(plan_id, "slow")
            self.assertEqual("slow", store.plan_speed(plan_id))

    def test_auto_proxy_raises_each_limit_only_after_all_projects_fill_it(self):
        from desktop_posting.models import ProjectRef
        from desktop_posting.plans import add_plan_entry, auto_proxy_enabled, create_plan, sync_auto_proxy_plan
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder)); store.initialize()
            plan_id = create_plan(store, "Auto")
            add_plan_entry(store, plan_id, ProjectRef("a", "A", "p1", "P1"), 80)
            add_plan_entry(store, plan_id, ProjectRef("a", "A", "p2", "P2"), 80)

            self.assertTrue(auto_proxy_enabled(store, plan_id))
            self.assertEqual((10, True), sync_auto_proxy_plan(store, plan_id, "2026-08-19"))
            self.assertEqual([10, 10], [row[7] for row in store.list_plan_entries(plan_id)])
            previous = 0
            for limit, next_limit in ((10, 20), (20, 30), (30, 40), (40, 50), (50, 60), (60, 70), (70, 83)):
                with self.subTest(limit=limit):
                    for _ in range(previous, limit):
                        store.increment_project_count(plan_id, "p1", "2026-08-19")
                    for _ in range(previous, limit - 1):
                        store.increment_project_count(plan_id, "p2", "2026-08-19")
                    self.assertEqual((limit, False), sync_auto_proxy_plan(store, plan_id, "2026-08-19"))
                    store.increment_project_count(plan_id, "p2", "2026-08-19")
                    self.assertEqual((next_limit, True), sync_auto_proxy_plan(store, plan_id, "2026-08-19"))
                    previous = limit

            self.assertEqual([83, 83], [row[7] for row in store.list_plan_entries(plan_id)])
            for project_id in ("p1", "p2"):
                for _ in range(70, 83):
                    store.increment_project_count(plan_id, project_id, "2026-08-19")
            self.assertEqual((83, False), sync_auto_proxy_plan(store, plan_id, "2026-08-19"))
            add_plan_entry(store, plan_id, ProjectRef("a", "A", "p3", "P3"), 1)
            sync_auto_proxy_plan(store, plan_id, "2026-08-19")
            self.assertEqual([83, 83, 83], [row[7] for row in store.list_plan_entries(plan_id)])

            self.assertEqual((10, True), sync_auto_proxy_plan(store, plan_id, "2026-08-20"))
            self.assertEqual([10, 10, 10], [row[7] for row in store.list_plan_entries(plan_id)])

    def test_auto_proxy_startup_catchup_and_plans_are_independent(self):
        from desktop_posting.models import ProjectRef
        from desktop_posting.plans import add_plan_entry, auto_proxy_enabled, create_plan, set_auto_proxy_enabled, sync_auto_proxy_plans
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder)); store.initialize()
            first = create_plan(store, "First")
            second = create_plan(store, "Second")
            manual = create_plan(store, "Manual")
            for plan_id in (first, second, manual):
                add_plan_entry(store, plan_id, ProjectRef("a", "A", f"p{plan_id}", "P"), 80)
            for _ in range(40):
                store.increment_project_count(first, f"p{first}", "2026-08-19")

            set_auto_proxy_enabled(store, manual, False, "2026-08-19")
            store = StateStore(Path(folder))
            sync_auto_proxy_plans(store, "2026-08-19")

            self.assertEqual(50, store.list_plan_entries(first)[0][7])
            self.assertEqual(10, store.list_plan_entries(second)[0][7])
            self.assertFalse(auto_proxy_enabled(store, manual))
            self.assertEqual(80, store.list_plan_entries(manual)[0][7])

    def test_existing_auto_proxy_keeps_same_day_stage_and_counts(self):
        from desktop_posting.models import ProjectRef
        from desktop_posting.plans import add_plan_entry, create_plan, sync_auto_proxy_plan
        from desktop_posting.storage import StateStore

        today = "2026-08-19"
        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder)); store.initialize()
            for old_limit, used, expected in ((40, 19, 40), (40, 40, 50), (83, 45, 83)):
                with self.subTest(old_limit=old_limit, used=used):
                    plan_id = create_plan(store, f"Legacy {old_limit} {used}")
                    add_plan_entry(store, plan_id, ProjectRef("a", "A", "p1", "P1"), old_limit)
                    store.set_states({
                        f"plan_auto_proxy_enabled_{plan_id}": "1",
                        f"plan_auto_proxy_date_{plan_id}": today,
                        f"plan_auto_proxy_limit_{plan_id}": old_limit,
                    })
                    for _ in range(used):
                        store.increment_project_count(plan_id, "p1", today)
                    self.assertEqual((expected, expected != old_limit), sync_auto_proxy_plan(store, plan_id, today))
                    self.assertEqual(expected, store.list_plan_entries(plan_id)[0][7])
                    self.assertEqual(used, store.project_count(plan_id, "p1", today))
                    self.assertEqual((10, True), sync_auto_proxy_plan(store, plan_id, "2026-08-20"))

    def test_disabling_auto_proxy_keeps_the_current_limit(self):
        from desktop_posting.models import ProjectRef
        from desktop_posting.plans import add_plan_entry, create_plan, set_auto_proxy_enabled, sync_auto_proxy_plan
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder)); store.initialize()
            plan_id = create_plan(store, "Auto")
            add_plan_entry(store, plan_id, ProjectRef("a", "A", "p1", "P1"), 80)
            for _ in range(40):
                store.increment_project_count(plan_id, "p1", "2026-08-19")
            set_auto_proxy_enabled(store, plan_id, True, "2026-08-19")
            set_auto_proxy_enabled(store, plan_id, False, "2026-08-19")

            self.assertEqual((None, False), sync_auto_proxy_plan(store, plan_id, "2026-08-20"))
            self.assertEqual(50, store.list_plan_entries(plan_id)[0][7])

    def test_empty_auto_proxy_plan_stays_at_first_limit(self):
        from desktop_posting.plans import create_plan, set_auto_proxy_enabled, sync_auto_proxy_plan
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder)); store.initialize()
            plan_id = create_plan(store, "Empty")

            set_auto_proxy_enabled(store, plan_id, True, "2026-08-19")

            self.assertEqual((10, False), sync_auto_proxy_plan(store, plan_id, "2026-08-19"))

    def test_stale_midnight_check_cannot_overwrite_the_new_day(self):
        from desktop_posting.models import ProjectRef
        from desktop_posting.plans import add_plan_entry, create_plan, set_auto_proxy_enabled, sync_auto_proxy_plan
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder)); store.initialize()
            plan_id = create_plan(store, "Midnight")
            add_plan_entry(store, plan_id, ProjectRef("a", "A", "p1", "P1"), 80)
            for _ in range(40):
                store.increment_project_count(plan_id, "p1", "2026-08-19")
            set_auto_proxy_enabled(store, plan_id, True, "2026-08-20")

            self.assertEqual((10, False), sync_auto_proxy_plan(store, plan_id, "2026-08-19"))
            self.assertEqual(10, store.list_plan_entries(plan_id)[0][7])

    def test_concurrent_auto_proxy_updates_keep_the_newer_stage(self):
        from desktop_posting.models import ProjectRef
        from desktop_posting.plans import add_plan_entry, create_plan, set_auto_proxy_enabled, sync_auto_proxy_plan
        from desktop_posting.storage import StateStore

        for crosses_midnight in (False, True):
            with self.subTest(crosses_midnight=crosses_midnight), tempfile.TemporaryDirectory() as folder:
                store = StateStore(Path(folder))
                store.initialize()
                plan_id = create_plan(store, "Concurrent")
                add_plan_entry(store, plan_id, ProjectRef("a", "A", "p1", "P1"), 80)
                today = "2026-08-19"
                set_auto_proxy_enabled(store, plan_id, True, today)
                prior_limit = 70 if crosses_midnight else 10
                for _ in range(prior_limit - 1):
                    store.increment_project_count(plan_id, "p1", today)
                sync_auto_proxy_plan(store, plan_id, today)
                store.increment_project_count(plan_id, "p1", today)

                saving_stage = threading.Event()
                resume = threading.Event()
                earlier_finished = threading.Event()

                class PausingConnection(sqlite3.Connection):
                    def executemany(self, sql, parameters):
                        if sql.startswith("INSERT INTO runtime_state"):
                            saving_stage.set()
                            if not resume.wait(5):
                                raise TimeoutError("stage update did not resume")
                        return super().executemany(sql, parameters)

                class PausingStore(StateStore):
                    def _connect(self):
                        return sqlite3.connect(self.db_path, factory=PausingConnection)

                class NonBlockingStore(StateStore):
                    def _connect(self):
                        return sqlite3.connect(self.db_path, timeout=0)

                newer_date = "2026-08-20" if crosses_midnight else today
                expected = 10 if crosses_midnight else 30

                def sync_earlier():
                    try:
                        sync_auto_proxy_plan(PausingStore(Path(folder)), plan_id, today)
                    finally:
                        earlier_finished.set()

                def advance(writer):
                    if not crosses_midnight:
                        sync_auto_proxy_plan(writer, plan_id, today)
                        for _ in range(10):
                            writer.increment_project_count(plan_id, "p1", today)
                    sync_auto_proxy_plan(writer, plan_id, newer_date)

                def sync_newer():
                    try:
                        advance(NonBlockingStore(Path(folder)))
                    except sqlite3.OperationalError as exc:
                        if exc.sqlite_errorcode != sqlite3.SQLITE_BUSY:
                            raise
                        resume.set()
                        if not earlier_finished.wait(5):
                            raise TimeoutError("earlier stage update did not finish")
                        advance(store)

                with ThreadPoolExecutor(max_workers=2) as pool:
                    earlier = pool.submit(sync_earlier)
                    try:
                        self.assertTrue(saving_stage.wait(5))
                        pool.submit(sync_newer).result(timeout=5)
                    finally:
                        resume.set()
                    earlier.result(timeout=5)

                self.assertEqual(newer_date, store.get_state(f"plan_auto_proxy_date_{plan_id}"))
                self.assertEqual(str(expected), store.get_state(f"plan_auto_proxy_limit_{plan_id}"))
                self.assertEqual(expected, store.list_plan_entries(plan_id)[0][7])

    def test_auto_proxy_rollover_and_same_day_reenable_keep_their_stage(self):
        from desktop_posting.models import ProjectRef
        from desktop_posting.plans import add_plan_entry, create_plan, set_auto_proxy_enabled, sync_auto_proxy_plan
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder))
            store.initialize()
            plan_id = create_plan(store, "New day")
            add_plan_entry(store, plan_id, ProjectRef("a", "A", "p1", "P1"), 80)
            previous_day = "2026-08-19"
            today = "2026-08-20"
            set_auto_proxy_enabled(store, plan_id, True, previous_day)
            for _ in range(70):
                store.increment_project_count(plan_id, "p1", previous_day)
            self.assertEqual((83, True), sync_auto_proxy_plan(store, plan_id, previous_day))

            for _ in range(10):
                store.increment_project_count(plan_id, "p1", today)
            self.assertEqual((10, True), sync_auto_proxy_plan(store, plan_id, today))
            self.assertEqual((20, True), sync_auto_proxy_plan(store, plan_id, today))
            add_plan_entry(store, plan_id, ProjectRef("a", "A", "p2", "P2"), 20)
            set_auto_proxy_enabled(store, plan_id, False, today)
            self.assertEqual((20, False), set_auto_proxy_enabled(store, plan_id, True, today))
            self.assertEqual([20, 20], [row[7] for row in store.list_plan_entries(plan_id)])
            self.assertEqual(70, store.project_count(plan_id, "p1", previous_day))

    def test_auto_proxy_rolls_back_stage_when_project_limit_cannot_be_updated(self):
        from desktop_posting.models import ProjectRef
        from desktop_posting.plans import add_plan_entry, create_plan, set_auto_proxy_enabled, sync_auto_proxy_plan
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder))
            store.initialize()
            plan_id = create_plan(store, "Rollback")
            add_plan_entry(store, plan_id, ProjectRef("a", "A", "p1", "P1"), 80)
            today = "2026-08-19"
            set_auto_proxy_enabled(store, plan_id, True, today)
            for _ in range(10):
                store.increment_project_count(plan_id, "p1", today)
            connection = sqlite3.connect(store.db_path)
            try:
                connection.execute("""
                    CREATE TRIGGER reject_limit_update BEFORE UPDATE OF daily_limit ON plan_entries
                    BEGIN SELECT RAISE(ABORT, 'limit update rejected'); END
                """)
            finally:
                connection.close()

            with self.assertRaises(sqlite3.IntegrityError):
                sync_auto_proxy_plan(store, plan_id, today)
            self.assertEqual("10", store.get_state(f"plan_auto_proxy_limit_{plan_id}", "10"))
            self.assertEqual(10, store.list_plan_entries(plan_id)[0][7])
            self.assertEqual(10, store.project_count(plan_id, "p1", today))


if __name__ == "__main__":
    unittest.main()
