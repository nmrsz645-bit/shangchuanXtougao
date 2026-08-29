import unittest


class FeishuQueueTests(unittest.TestCase):
    def test_claimable_row_skips_posted_and_terminal_rows(self):
        from desktop_posting.feishu_queue import find_claimable_row

        headers = ["书名", "投稿状态", "领取状态"]
        rows = [["已完成", "已投稿", ""], ["失败", "", "彻底失败"], ["待投", "", ""]]
        self.assertEqual(4, find_claimable_row(headers, rows)["row_number"])

    def test_required_headers_are_reported(self):
        from desktop_posting.feishu_queue import validate_headers

        self.assertIn("书名", validate_headers(["标签"]))

    def test_tenant_token_accepts_top_level_feishu_response(self):
        from desktop_posting.feishu_client import tenant_token_from_response

        self.assertEqual("token", tenant_token_from_response({"code": 0, "tenant_access_token": "token"}))

    def test_expired_claim_is_available_again(self):
        from desktop_posting.feishu_queue import find_claimable_row

        headers = ["书名", "投稿状态", "领取状态", "领取过期时间"]
        rows = [["待投", "", "已领取", "2000-01-01 00:00:00"]]
        self.assertEqual(2, find_claimable_row(headers, rows)["row_number"])

    def test_none_cells_are_treated_as_empty(self):
        from desktop_posting.feishu_queue import find_claimable_row
        self.assertEqual(2, find_claimable_row(["书名", "领取状态"], [["书A", None]])["row_number"])

    def test_claim_filter_skips_task_owned_by_another_plan(self):
        from desktop_posting.feishu_queue import find_claimable_row

        headers = ["书名", "领取状态"]
        rows = [["旧方案任务", ""], ["当前方案任务", ""]]
        task = find_claimable_row(headers, rows, can_claim=lambda row, _: row != 2)

        self.assertEqual(3, task["row_number"])


if __name__ == "__main__":
    unittest.main()
