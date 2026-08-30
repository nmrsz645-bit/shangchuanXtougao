import unittest


class CompatibleTargetTests(unittest.TestCase):
    def test_duplicate_promotion_names_increment_until_success(self):
        from desktop_posting.run_once import create_with_unique_name

        names = []
        saved_suffixes = []

        def create(_, body):
            names.append(body["name"])
            if len(names) < 3:
                raise RuntimeError("千川接口失败：与单元ID=123的名称重复")
            return {"promotion_id": "ok"}

        created, suffix = create_with_unique_name(
            "token", {"name": "Book"}, "Book", 0, saved_suffixes.append,
            create_func=create, sleep_func=lambda _: None,
        )

        self.assertEqual(["Book", "Book1", "Book2"], names)
        self.assertEqual([1, 2], saved_suffixes)
        self.assertEqual("ok", created["promotion_id"])
        self.assertEqual(2, suffix)

    def test_exact_platform_duplicate_name_error_is_retried(self):
        from desktop_posting.run_once import create_with_unique_name

        names = []

        def create(_, body):
            names.append(body["name"])
            if len(names) == 1:
                raise RuntimeError("千川接口失败：与单元ID=7665633938384388139的名称重复")
            return {"promotion_id": "ok"}

        created, suffix = create_with_unique_name(
            "token", {}, "测试书", 0, lambda _: None,
            create_func=create, sleep_func=lambda _: None,
        )

        self.assertEqual(["测试书", "测试书1"], names)
        self.assertEqual("ok", created["promotion_id"])
        self.assertEqual(1, suffix)

    def test_duplicate_name_limit_returns_next_persisted_suffix(self):
        from desktop_posting.run_once import create_with_unique_name

        names = []
        saved_suffixes = []

        def create(_, body):
            names.append(body["name"])
            raise RuntimeError("千川接口失败：与单元ID=123的名称重复")

        created, suffix = create_with_unique_name(
            "token", {"name": "Book"}, "Book", 50, saved_suffixes.append,
            create_func=create, sleep_func=lambda _: None, max_attempts=3,
        )

        self.assertIsNone(created)
        self.assertEqual(["Book50", "Book51", "Book52"], names)
        self.assertEqual([51, 52, 53], saved_suffixes)
        self.assertEqual(53, suffix)

    def test_non_duplicate_create_error_is_not_renamed(self):
        from desktop_posting.run_once import create_with_unique_name

        with self.assertRaisesRegex(RuntimeError, "No permission"):
            create_with_unique_name(
                "token", {"name": "Book"}, "Book", 0, lambda _: None,
                create_func=lambda *_: (_ for _ in ()).throw(RuntimeError("No permission")),
                sleep_func=lambda _: None,
            )

    def test_capacity_limit_error_unlocks_the_original_project(self):
        from desktop_posting.run_once import should_unlock_target_for_capacity_limit

        self.assertTrue(
            should_unlock_target_for_capacity_limit(
                RuntimeError("qianchuan api failed: project promotion count exceeds 100")
            )
        )

    def test_other_failures_keep_the_original_project_lock(self):
        from desktop_posting.run_once import should_unlock_target_for_capacity_limit

        self.assertFalse(should_unlock_target_for_capacity_limit(RuntimeError("HTTP Error 504: Gateway Time-out")))

    def test_newer_project_is_detected_from_the_same_project_family(self):
        from desktop_posting.run_once import newer_suffix_project

        current = {"project_id": "project-4", "name": "Project【2】_4"}
        projects = [current, {"project_id": "project-5", "name": "Project【2】_5"}]

        self.assertEqual("project-5", newer_suffix_project(projects, current)["project_id"])

    def test_locked_retry_uses_latest_project_suffix(self):
        from desktop_posting.run_once import choose_locked_target

        locked = {"advertiser_id": "a", "project_id": "project-6", "project_name": "项目_6", "template_id": "old-template"}
        projects = [
            {"project_id": "project-6", "name": "项目_6"},
            {"project_id": "project-7", "name": "项目_7"},
        ]
        target = choose_locked_target(
            locked, "token", "book_id=r1&chapter_id=1",
            list_projects_func=lambda *_: projects,
            list_promotions_func=lambda _, __, project_id: [{
                "promotion_id": "new-template" if project_id == "project-7" else "old-project-template",
                "promotion_materials": {"mini_program_info": {"app_id": "tt8a56fceb1563152001"}},
            }],
        )

        self.assertEqual("project-7", target[0]["project_id"])
        self.assertEqual("new-template", target[1]["promotion_id"])

    def test_skips_project_with_incompatible_template_and_uses_next_entry(self):
        from desktop_posting.models import PlanEntry, ProjectRef
        from desktop_posting.run_once import choose_compatible_target

        first = PlanEntry(1, 1, ProjectRef("a", "A", "old", "项目【1】_1"), 0, 10)
        second = PlanEntry(2, 1, ProjectRef("a", "A", "new", "项目【2】_1"), 1, 10)
        projects = [
            {"project_id": "old", "name": "项目【1】_1"},
            {"project_id": "new", "name": "项目【2】_1"},
        ]
        promotions = {
            "old": [{"promotion_materials": {"mini_program_info": {"app_id": "tte3a3951e7c939c7701"}}}],
            "new": [{"promotion_materials": {"mini_program_info": {"app_id": "tt8a56fceb1563152001"}}}],
        }

        target = choose_compatible_target(
            [first, second], "token", "book_id=r1&chapter_id=1",
            list_projects_func=lambda *_: projects,
            list_promotions_func=lambda _, __, project_id: promotions[project_id],
        )

        self.assertEqual(second, target[0])
        self.assertEqual("new", target[1]["project_id"])

    def test_returns_none_when_no_project_template_supports_link(self):
        from desktop_posting.models import PlanEntry, ProjectRef
        from desktop_posting.run_once import choose_compatible_target

        entry = PlanEntry(1, 1, ProjectRef("a", "A", "p1", "项目_1"), 0, 10)
        target = choose_compatible_target(
            [entry], "token", "book_id=r1&chapter_id=1",
            list_projects_func=lambda *_: [{"project_id": "p1", "name": "项目_1"}],
            list_promotions_func=lambda *_: [{"promotion_materials": {"mini_program_info": {"app_id": "tte3a3951e7c939c7701"}}}],
        )

        self.assertIsNone(target)

    def test_configured_mini_app_selects_its_template(self):
        from desktop_posting.models import PlanEntry, ProjectRef
        from desktop_posting.run_once import choose_compatible_target

        entry = PlanEntry(1, 1, ProjectRef("a", "A", "p1", "项目_1"), 0, 10)
        target = choose_compatible_target(
            [entry], "token", "book_id=r1&chapter_id=1",
            list_projects_func=lambda *_: [{"project_id": "p1", "name": "项目_1"}],
            list_promotions_func=lambda *_: [{"promotion_materials": {"mini_program_info": {"app_id": "tt23a45519bc945c7401"}}}],
            configured_app_id="tt23a45519bc945c7401",
        )

        self.assertEqual(entry, target[0])


if __name__ == "__main__":
    unittest.main()
