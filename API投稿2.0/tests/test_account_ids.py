import unittest
from unittest.mock import patch
import json
import tempfile
from pathlib import Path


class AccountIdTests(unittest.TestCase):
    def test_configured_ids_are_kept_before_token_ids(self):
        from desktop_posting.qianchuan_client import merged_advertiser_ids

        self.assertEqual(
            ["100", "200", "300"],
            merged_advertiser_ids("100\n200", ["200", "300"]),
        )

    def test_full_width_commas_split_configured_ids(self):
        from desktop_posting.qianchuan_client import merged_advertiser_ids

        self.assertEqual(
            ["100", "200", "300"],
            merged_advertiser_ids("100，200，300", []),
        )

    def test_configured_ids_do_not_append_unrequested_token_ids(self):
        from desktop_posting.qianchuan_client import selected_advertiser_ids

        self.assertEqual(["100", "200"], selected_advertiser_ids("100，200", ["300"]))

    def test_only_largest_numeric_project_suffix_is_shown(self):
        from desktop_posting.qianchuan_client import latest_projects_by_name

        items = [
            {"project_id": "4", "name": "娱行肿昂商贸【2】_4"},
            {"project_id": "5", "name": "娱行肿昂商贸【2】_5"},
            {"project_id": "9", "name": "其他项目"},
        ]
        self.assertEqual(["娱行肿昂商贸【2】_5", "其他项目"], [item["name"] for item in latest_projects_by_name(items)])

    def test_resolve_latest_project_uses_selected_base_name(self):
        from desktop_posting.qianchuan_client import resolve_latest_project

        projects = [{"project_id": "4", "name": "娱行肿昂商贸【2】_4"}, {"project_id": "5", "name": "娱行肿昂商贸【2】_5"}]
        self.assertEqual("5", resolve_latest_project(projects, "娱行肿昂商贸【2】")["project_id"])
    def test_list_promotions_reads_every_api_page(self):
        from desktop_posting.qianchuan_client import list_promotions

        with patch("desktop_posting.qianchuan_client._get", side_effect=[
            {"list": [{"promotion_id": "p1"}], "page_info": {"page": 1, "total_page": 2}},
            {"list": [{"promotion_id": "p2"}], "page_info": {"page": 2, "total_page": 2}},
        ]) as request:
            promotions = list_promotions("token", "account", "123")

        self.assertEqual(["p1", "p2"], [item["promotion_id"] for item in promotions])
        self.assertEqual(2, request.call_count)
        self.assertEqual(1, request.call_args_list[0].args[2]["page"])
        self.assertEqual(2, request.call_args_list[1].args[2]["page"])

    def test_expired_token_error_is_detected(self):
        from desktop_posting.qianchuan_client import is_access_token_expired_error

        self.assertTrue(is_access_token_expired_error("qianchuan api failed: access_token\u5df2\u8fc7\u671f"))
        self.assertTrue(is_access_token_expired_error("access_token expired"))
        self.assertFalse(is_access_token_expired_error("No permission to operate account"))

    def test_forced_refresh_replaces_saved_token(self):
        from desktop_posting.qianchuan_client import refresh_if_needed

        class Settings:
            qianchuan_app_id = "app"
            qianchuan_secret = "secret"

        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config"; config.mkdir()
            (config / "tokens.json").write_text(json.dumps({"access_token": "old", "refresh_token": "refresh", "expires_at": 9999999999}), encoding="utf-8")
            with patch("desktop_posting.qianchuan_client._post", return_value={"access_token": "new", "refresh_token": "new-refresh", "expires_in": 86400, "refresh_token_expires_in": 2592000, "advertiser_ids": ["1"]}) as request:
                token = refresh_if_needed(folder, Settings(), force=True)

            self.assertEqual("new", token["access_token"])
            self.assertEqual(1, request.call_count)
            self.assertEqual("new", json.loads((config / "tokens.json").read_text(encoding="utf-8"))["access_token"])


if __name__ == "__main__":
    unittest.main()
