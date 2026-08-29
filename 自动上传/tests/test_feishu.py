from io import BytesIO
import json
from urllib.error import HTTPError

import pytest

from video_feishu.feishu import FeishuClient, FeishuError, parse_document_url, source_rows_by_last_book


def test_parse_wiki_and_sheet_urls():
    wiki = parse_document_url("https://my.feishu.cn/wiki/abc?x=1")
    sheet = parse_document_url("https://my.feishu.cn/sheets/xyz?sheet=9f356e")
    assert (wiki.kind, wiki.token) == ("wiki", "abc")
    assert (sheet.kind, sheet.token, sheet.sheet_id) == ("sheets", "xyz", "9f356e")


def test_duplicate_book_uses_last_row():
    values = [["书名", "标签", "活动页", "程序链接"], ["A", 1, 2, 3], ["A", 4, 5, 6]]
    rows = source_rows_by_last_book(values)
    assert rows["A"].tag == 4
    assert rows["A"].program_link == 6


def test_http_error_includes_api_message_and_request_stage():
    def opener(request, timeout):
        raise HTTPError(
            request.full_url,
            400,
            "Bad Request",
            {},
            BytesIO(b'{"code":10003,"msg":"app_id or app_secret is invalid"}'),
        )

    client = FeishuClient(opener)
    with pytest.raises(FeishuError) as caught:
        client.authenticate("bad-id", "bad-secret")
    message = str(caught.value)
    assert "获取飞书访问凭证" in message
    assert "10003" in message
    assert "app_id or app_secret is invalid" in message


def test_read_values_uses_whole_sheet_id_as_valid_range():
    seen = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self):
            return json.dumps({"code": 0, "data": {"valueRange": {"values": []}}}).encode()

    def opener(request, timeout):
        seen.append(request.full_url)
        return Response()

    FeishuClient(opener).read_values("spreadsheet", "sheet123")
    assert seen[0].endswith("/values/sheet123")


def test_write_values_updates_exact_range():
    seen = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b'{"code":0}'

    def opener(request, timeout):
        seen.append(request)
        return Response()

    FeishuClient(opener).write_values("spreadsheet", "sheet!E4:E4", [["A"]])

    assert seen[0].method == "PUT"
    assert seen[0].full_url.endswith("/spreadsheets/spreadsheet/values")
    assert json.loads(seen[0].data)["valueRange"] == {"range": "sheet!E4:E4", "values": [["A"]]}
