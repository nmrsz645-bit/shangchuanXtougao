import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch


BOOK_HEADER = "\u4e66\u540d"
TAG_HEADER = "\u6807\u7b7e"
PROGRAM_LINK_HEADER = "\u7a0b\u5e8f\u94fe\u63a5"
START_PAGE_HEADER = "\u542f\u52a8\u9875"
POST_STATUS_HEADER = "\u6295\u7a3f\u72b6\u6001"
POSTED_STATUS = "\u5df2\u6295\u7a3f"
NO_TEMPLATE = "\u6ca1\u6709\u4e0e\u8be5\u7a0b\u5e8f\u94fe\u63a5\u517c\u5bb9\u7684\u9879\u76ee\u6a21\u677f"


class RunOnceIntegrationTests(unittest.TestCase):
    app_id = "tt23a45519bc945c7401"

    def make_base_dir(self, folder):
        from desktop_posting.models import ProjectRef
        from desktop_posting.plans import add_plan_entry, create_plan
        from desktop_posting.settings import AppSettings, save_settings
        from desktop_posting.storage import StateStore

        base_dir = Path(folder)
        save_settings(base_dir, AppSettings(mini_program_app_id=self.app_id))
        store = StateStore(base_dir)
        store.initialize()
        plan_id = create_plan(store, "test-plan")
        add_plan_entry(store, plan_id, ProjectRef("1001", "test-account", "2001", "test-project_1"), 40)
        store.set_state("active_plan_id", plan_id)
        return base_dir, store, plan_id

    @staticmethod
    def task():
        return {
            "sheet_id": "sheet-1",
            "headers": [BOOK_HEADER, TAG_HEADER, PROGRAM_LINK_HEADER, START_PAGE_HEADER],
            "row_number": 2,
            "values": {
                BOOK_HEADER: "test-book",
                TAG_HEADER: "test-tag",
                PROGRAM_LINK_HEADER: "pages/novel_plugin/index",
                START_PAGE_HEADER: "book_id=r1&chapter_id=1",
            },
        }

    def test_configured_app_id_posts_through_the_offline_flow(self):
        import desktop_posting.run_once as runner

        created_bodies = []
        row_updates = []
        template = {
            "promotion_id": "template-1",
            "promotion_materials": {
                "mini_program_info": {"app_id": self.app_id},
                "video_material_list": [{}],
            },
        }
        project = {"project_id": "2001", "name": "test-project_1"}

        def target(entries, _, params, configured_app_id=""):
            self.assertEqual("book_id=r1&chapter_id=1", params)
            self.assertEqual(self.app_id, configured_app_id)
            self.assertEqual(10, entries[0].daily_limit)
            return entries[0], project, template

        def create(_, body, __, suffix, ___):
            created_bodies.append(body)
            return {"promotion_id": "promotion-1"}, suffix

        with tempfile.TemporaryDirectory() as folder:
            base_dir, store, plan_id = self.make_base_dir(folder)
            with patch.object(runner, "refresh_if_needed", return_value={"access_token": "offline-token"}), \
                patch.object(runner, "claim_next_task", return_value=self.task()), \
                patch.object(runner, "choose_compatible_target", side_effect=target), \
                patch.object(runner, "search_materials", return_value=[{"filename": "test-book.mp4", "video_id": "video-1", "video_cover_id": "cover-1"}]), \
                patch.object(runner, "create_with_unique_name", side_effect=create), \
                patch.object(runner, "update_row", side_effect=lambda *args: row_updates.append(args[-1])), \
                patch.object(runner, "mark_row_green"), \
                patch.object(runner, "release_task"):
                result = runner.run_once(base_dir)

            self.assertEqual("posted:promotion-1", result)
            self.assertEqual(self.app_id, created_bodies[0]["promotion_materials"]["mini_program_info"]["app_id"])
            self.assertIn(self.app_id, created_bodies[0]["promotion_materials"]["mini_program_info"]["url"])
            self.assertEqual(POSTED_STATUS, row_updates[0][POST_STATUS_HEADER])
            self.assertEqual(1, store.project_count(plan_id, "2001", date.today().isoformat()))
            self.assertEqual("posted:promotion-1", store.get_state("runtime_last_result"))

    def test_crossing_midnight_selects_and_reserves_against_the_new_day(self):
        import desktop_posting.run_once as runner
        from desktop_posting.plans import available_entries, set_auto_proxy_enabled, sync_auto_proxy_plan

        old_day, new_day = date(2026, 11, 14), date(2026, 11, 15)
        project = {"project_id": "2001", "name": "test-project_1"}
        template = {
            "promotion_id": "template-1",
            "promotion_materials": {
                "mini_program_info": {"app_id": self.app_id},
                "video_material_list": [{}],
            },
        }

        for crossing in ("quota_read", "target_lookup"):
            with self.subTest(crossing=crossing), tempfile.TemporaryDirectory() as folder:
                base_dir, store, plan_id = self.make_base_dir(folder)
                set_auto_proxy_enabled(store, plan_id, True, old_day.isoformat())
                for _ in range(10):
                    store.increment_project_count(plan_id, "2001", old_day.isoformat())
                sync_auto_proxy_plan(store, plan_id, old_day.isoformat())

                def roll_over():
                    clock.today.return_value = new_day
                    sync_auto_proxy_plan(store, plan_id, new_day.isoformat())

                def read_entries(state, selected_plan, day):
                    if crossing == "quota_read" and day == old_day.isoformat():
                        roll_over()
                    return available_entries(state, selected_plan, day)

                def lookup_target(entries, *_args, **_kwargs):
                    if crossing == "target_lookup" and clock.today.return_value == old_day:
                        roll_over()
                    return entries[0], project, template

                with (
                    patch.object(runner, "date") as clock,
                    patch.object(runner, "available_entries", side_effect=read_entries),
                    patch.object(runner, "refresh_if_needed", return_value={"access_token": "offline-token"}),
                    patch.object(runner, "claim_next_task", return_value=self.task()),
                    patch.object(runner, "choose_compatible_target", side_effect=lookup_target),
                    patch.object(runner, "search_materials", return_value=[{"filename": "test-book.mp4", "video_id": "video-1", "video_cover_id": "cover-1"}]),
                    patch.object(runner, "create_with_unique_name", return_value=({"promotion_id": "promotion-1"}, 0)),
                    patch.object(runner, "update_row"),
                    patch.object(runner, "mark_row_green"),
                    patch.object(runner, "release_task"),
                ):
                    clock.today.return_value = old_day
                    result = runner.run_once(base_dir)

                self.assertEqual("posted:promotion-1", result)
                self.assertEqual(10, store.project_count(plan_id, "2001", old_day.isoformat()))
                self.assertEqual(1, store.project_count(plan_id, "2001", new_day.isoformat()))

    def test_full_quota_retries_at_midnight_following_the_quota_date(self):
        import desktop_posting.run_once as runner
        from desktop_posting.plans import set_auto_proxy_enabled

        quota_day = date(2026, 11, 14)
        with tempfile.TemporaryDirectory() as folder:
            base_dir, store, plan_id = self.make_base_dir(folder)
            set_auto_proxy_enabled(store, plan_id, False, quota_day.isoformat())
            store.update_entry_limit(store.list_plan_entries(plan_id)[0][0], 1)
            store.increment_project_count(plan_id, "2001", quota_day.isoformat())
            with (
                patch.object(runner, "date") as clock,
                patch.object(runner, "datetime") as wall_clock,
                patch.object(runner, "refresh_if_needed", return_value={"access_token": "offline-token"}),
                patch.object(runner, "claim_next_task", return_value=self.task()),
                patch.object(runner, "choose_compatible_target", side_effect=AssertionError("Full quota must skip target lookup")),
                patch.object(runner, "release_task") as release,
            ):
                clock.today.return_value = quota_day
                # The wall clock crosses midnight after quota selection.
                wall_clock.now.side_effect = [datetime(2026, 11, 14, 23, 59, 59), datetime(2026, 11, 15), datetime(2026, 11, 15)]
                result = runner.run_once(base_dir)

            self.assertEqual("all_projects_full", result)
            self.assertEqual("2026-11-15 00:00:00", release.call_args.args[4])

    def test_no_compatible_template_releases_task_for_retry(self):
        import desktop_posting.run_once as runner

        released = []
        with tempfile.TemporaryDirectory() as folder:
            base_dir, store, _ = self.make_base_dir(folder)
            with patch.object(runner, "refresh_if_needed", return_value={"access_token": "offline-token"}), \
                patch.object(runner, "claim_next_task", return_value=self.task()), \
                patch.object(runner, "choose_compatible_target", return_value=None), \
                patch.object(runner, "release_task", side_effect=lambda *args: released.append(args)):
                result = runner.run_once(base_dir)

            self.assertEqual("retry:" + NO_TEMPLATE, result)
            self.assertEqual(NO_TEMPLATE, released[0][2])
            self.assertFalse(released[0][3])
            self.assertEqual("retry:" + NO_TEMPLATE, store.get_state("runtime_last_result"))


if __name__ == "__main__":
    unittest.main()
