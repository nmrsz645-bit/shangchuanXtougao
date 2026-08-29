import unittest
from unittest.mock import patch


class PostingServiceTests(unittest.TestCase):
    def test_latest_exact_material_wins(self):
        from desktop_posting.posting_service import select_material

        items = [{"filename": "书A.mp4", "create_time": 1}, {"filename": "书A", "create_time": 2}, {"filename": "书AB", "create_time": 9}]
        self.assertEqual(2, select_material(items, "书A")["create_time"])

    def test_material_search_checks_later_pages_until_it_finds_an_exact_name(self):
        from desktop_posting.qianchuan_client import search_materials

        pages = {
            1: {"list": [{"filename": "other-book.mp4"}], "page_info": {"total_page": 2}},
            2: {"list": [{"filename": "target-book.mp4", "create_time": 2}], "page_info": {"total_page": 2}},
        }
        calls = []

        def fake_get(path, token, params):
            calls.append(params["page"])
            return pages[params["page"]]

        with patch("desktop_posting.qianchuan_client._get", side_effect=fake_get):
            items = search_materials("token", "advertiser", "target-book")

        self.assertEqual([1, 2], calls)
        self.assertEqual("target-book.mp4", items[0]["filename"])

    def test_material_search_accepts_filename_containing_book_name(self):
        from desktop_posting.qianchuan_client import search_materials
        from desktop_posting.posting_service import select_material

        response = {"list": [{"filename": "target-book-account-1.mp4", "create_time": 2}], "page_info": {"total_page": 1}}
        with patch("desktop_posting.qianchuan_client._get", return_value=response):
            items = search_materials("token", "advertiser", "target-book")

        self.assertEqual("target-book-account-1.mp4", select_material(items, "target-book")["filename"])

    def test_material_search_stops_after_two_minutes_without_a_match(self):
        from desktop_posting.qianchuan_client import search_materials

        calls = []

        def fake_get(path, token, params):
            calls.append(params["page"])
            return {"list": [{"filename": "other-book.mp4"}], "page_info": {"total_page": 99}}

        with patch("desktop_posting.qianchuan_client._get", side_effect=fake_get), patch(
            "desktop_posting.qianchuan_client.time.monotonic", side_effect=[0.0, 120.1]
        ) as monotonic:
            items = search_materials("token", "advertiser", "target-book")

        self.assertEqual([], items)
        self.assertEqual([1], calls)
        self.assertEqual(2, monotonic.call_count)

    def test_program_link_splits_path_and_parameters(self):
        from desktop_posting.posting_service import parse_program_fields

        self.assertEqual(("pages/novel_plugin/index", "bookId=1"), parse_program_fields("pages/novel_plugin/index\tbookId=1", ""))

    def test_program_link_accepts_all_legacy_sheet_formats(self):
        from desktop_posting.posting_service import parse_program_fields

        expected = ("pages/novel_plugin/index", "book_id=r1&chapter_id=1")
        cases = [
            ("pages/novel_plugin/index\nbook_id=r1&chapter_id=1", ""),
            ("pages/novel_plugin/index?book_id=r1&chapter_id=1", ""),
            ("pages/novel_plugin/index", "book_id=r1&chapter_id=1"),
            ("book_id=r1&chapter_id=1", ""),
        ]
        for program_link, start_page in cases:
            self.assertEqual(expected, parse_program_fields(program_link, start_page))

    def test_book_id_style_uses_default_mini_app(self):
        from desktop_posting.microapp_link import choose_app_id

        self.assertEqual("tt8a56fceb1563152001", choose_app_id("book_id=r1&chapter_id=1"))

    def test_book_id_style_with_micro_panel_uses_default_mini_app(self):
        from desktop_posting.microapp_link import choose_app_id

        self.assertEqual(
            "tt8a56fceb1563152001",
            choose_app_id(
                "book_id=r7660808341706508579&chapter_id=1&id=704806&cnum=1&"
                "channel=rd-fx84512724adf0af2792f3d8df0a41180d&micro_pannel_id=21202"
            ),
        )

    def test_book_id_camel_style_uses_book_id_mini_app(self):
        from desktop_posting.microapp_link import choose_app_id

        self.assertEqual("tte3a3951e7c939c7701", choose_app_id("bookId=1&channelId=2&micro_pannel_id=x"))

    def test_template_must_match_link_mini_app(self):
        from desktop_posting.qianchuan_client import template_supports_link

        default_template = {"promotion_materials": {"mini_program_info": {"app_id": "tt8a56fceb1563152001"}}}
        book_id_template = {"promotion_materials": {"mini_program_info": {"app_id": "tte3a3951e7c939c7701"}}}
        self.assertTrue(template_supports_link(default_template, "book_id=r1&chapter_id=1"))
        self.assertFalse(template_supports_link(book_id_template, "book_id=r1&chapter_id=1"))

    def test_create_body_uses_link_app_id_not_template_app_id(self):
        from desktop_posting.qianchuan_client import build_promotion_body

        template = {
            "promotion_materials": {
                "mini_program_info": {"app_id": "tte3a3951e7c939c7701"},
                "video_material_list": [{"image_mode": "CREATIVE_IMAGE_MODE_VIDEO_VERTICAL"}],
            }
        }
        material = {"video_id": "v1", "video_cover_id": "cover1"}
        body = build_promotion_body(
            template, "1", "2", "Book", "Tag", material,
            "pages/novel_plugin/index", "book_id=r1&chapter_id=1", "sslocal://microapp?x", "tte3a3951e7c939c7701",
        )
        self.assertEqual("tt8a56fceb1563152001", body["promotion_materials"]["mini_program_info"]["app_id"])

    def test_material_sort_accepts_api_datetime(self):
        from desktop_posting.qianchuan_client import material_created_key

        self.assertGreater(material_created_key({"create_time": "2026-07-10 14:35:20"}), 0)

    def test_posted_time_has_seconds(self):
        from datetime import datetime
        from desktop_posting.posting_service import posted_time

        self.assertEqual("2026-07-10 15:20:30", posted_time(datetime(2026, 7, 10, 15, 20, 30)))


if __name__ == "__main__":
    unittest.main()
