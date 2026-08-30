import tempfile
import unittest
from datetime import date
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
