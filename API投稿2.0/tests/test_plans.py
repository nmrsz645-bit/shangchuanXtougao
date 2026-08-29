import tempfile
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

    def test_auto_proxy_switches_40_to_83_and_resets_next_day(self):
        from desktop_posting.models import ProjectRef
        from desktop_posting.plans import add_plan_entry, create_plan, set_auto_proxy_enabled, sync_auto_proxy_plan
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder)); store.initialize()
            plan_id = create_plan(store, "Auto")
            add_plan_entry(store, plan_id, ProjectRef("a", "A", "p1", "P1"), 80)
            add_plan_entry(store, plan_id, ProjectRef("a", "A", "p2", "P2"), 80)

            self.assertEqual((None, False), sync_auto_proxy_plan(store, plan_id, "2026-08-19"))
            self.assertEqual([80, 80], [row[7] for row in store.list_plan_entries(plan_id)])
            set_auto_proxy_enabled(store, plan_id, True, "2026-08-19")
            self.assertEqual([40, 40], [row[7] for row in store.list_plan_entries(plan_id)])
            for _ in range(40):
                store.increment_project_count(plan_id, "p1", "2026-08-19")
            for _ in range(39):
                store.increment_project_count(plan_id, "p2", "2026-08-19")

            self.assertEqual((40, False), sync_auto_proxy_plan(store, plan_id, "2026-08-19"))
            store.increment_project_count(plan_id, "p2", "2026-08-19")

            self.assertEqual((83, True), sync_auto_proxy_plan(store, plan_id, "2026-08-19"))
            self.assertEqual([83, 83], [row[7] for row in store.list_plan_entries(plan_id)])
            add_plan_entry(store, plan_id, ProjectRef("a", "A", "p3", "P3"), 1)
            sync_auto_proxy_plan(store, plan_id, "2026-08-19")
            self.assertEqual([83, 83, 83], [row[7] for row in store.list_plan_entries(plan_id)])

            self.assertEqual((40, True), sync_auto_proxy_plan(store, plan_id, "2026-08-20"))
            self.assertEqual([40, 40, 40], [row[7] for row in store.list_plan_entries(plan_id)])

    def test_auto_proxy_startup_catchup_and_plans_are_independent(self):
        from desktop_posting.models import ProjectRef
        from desktop_posting.plans import add_plan_entry, create_plan, set_auto_proxy_enabled, sync_auto_proxy_plans
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder)); store.initialize()
            first = create_plan(store, "First")
            second = create_plan(store, "Second")
            for plan_id in (first, second):
                add_plan_entry(store, plan_id, ProjectRef("a", "A", f"p{plan_id}", "P"), 80)
            for _ in range(40):
                store.increment_project_count(first, f"p{first}", "2026-08-19")

            set_auto_proxy_enabled(store, first, True, "2026-08-19")
            set_auto_proxy_enabled(store, second, True, "2026-08-19")
            sync_auto_proxy_plans(store, "2026-08-19")

            self.assertEqual(83, store.list_plan_entries(first)[0][7])
            self.assertEqual(40, store.list_plan_entries(second)[0][7])

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
            self.assertEqual(83, store.list_plan_entries(plan_id)[0][7])

    def test_empty_auto_proxy_plan_does_not_switch_to_83(self):
        from desktop_posting.plans import create_plan, set_auto_proxy_enabled, sync_auto_proxy_plan
        from desktop_posting.storage import StateStore

        with tempfile.TemporaryDirectory() as folder:
            store = StateStore(Path(folder)); store.initialize()
            plan_id = create_plan(store, "Empty")

            set_auto_proxy_enabled(store, plan_id, True, "2026-08-19")

            self.assertEqual((40, False), sync_auto_proxy_plan(store, plan_id, "2026-08-19"))

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

            self.assertEqual((40, False), sync_auto_proxy_plan(store, plan_id, "2026-08-19"))
            self.assertEqual(40, store.list_plan_entries(plan_id)[0][7])


if __name__ == "__main__":
    unittest.main()
