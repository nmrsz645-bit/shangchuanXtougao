import json
import re
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


def sheet_token(url):
    match = re.search(r"/(?:sheets|wiki)/([^/?#]+)", urlparse(url).path)
    if not match:
        raise ValueError("飞书表格链接无效")
    return match.group(1)


def tenant_token(settings):
    request = urllib.request.Request("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal", data=json.dumps({"app_id": settings.feishu_app_id, "app_secret": settings.feishu_secret}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return tenant_token_from_response(json.loads(response.read().decode()))


def tenant_token_from_response(result):
    if result.get("code") != 0 or not result.get("tenant_access_token"):
        raise RuntimeError(result.get("msg") or "飞书租户令牌获取失败")
    return result["tenant_access_token"]


def sheet1_id(settings):
    token = tenant_token(settings); spreadsheet = sheet_token(settings.submission_sheet_url)
    data = _request(f"https://open.feishu.cn/open-apis/sheets/v3/spreadsheets/{spreadsheet}/sheets/query", None, {"Authorization": f"Bearer {token}"})
    for item in data.get("sheets", []):
        if item.get("title") == "Sheet1": return item["sheet_id"]
    raise RuntimeError("投稿表格中未找到 Sheet1")


def read_sheet1(settings):
    token = tenant_token(settings); spreadsheet = sheet_token(settings.submission_sheet_url); sheet_id = sheet1_id(settings)
    data = _request(f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet}/values/{sheet_id}!A1:BZ5000", None, {"Authorization": f"Bearer {token}"})
    return sheet_id, data.get("valueRange", {}).get("values", [])


def update_row(settings, sheet_id, headers, row_number, updates):
    token = tenant_token(settings); spreadsheet = sheet_token(settings.submission_sheet_url)
    _, rows = read_sheet1(settings)
    row = list(rows[row_number - 1]) if len(rows) >= row_number else []
    row += [""] * (len(headers) - len(row))
    for name, value in updates.items(): row[headers.index(name)] = value
    last = column_name(len(headers))
    _request(f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet}/values", {"valueRange": {"range": f"{sheet_id}!A{row_number}:{last}{row_number}", "values": [row[:len(headers)]]}}, {"Authorization": f"Bearer {token}"}, "PUT")


def mark_row_green(settings, sheet_id, headers, row_number):
    token = tenant_token(settings); spreadsheet = sheet_token(settings.submission_sheet_url); last = column_name(len(headers))
    _request(f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet}/style", {"appendStyle": {"range": f"{sheet_id}!A{row_number}:{last}{row_number}", "style": {"backColor": "#D9EAD3"}}}, {"Authorization": f"Bearer {token}"}, "PUT")


def column_name(index):
    result = ""
    while index:
        index, rest = divmod(index - 1, 26); result = chr(65 + rest) + result
    return result


def _request(url, body=None, headers=None, method=None):
    headers = headers or {}; data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers}, method=method or ("POST" if body is not None else "GET"))
    last = None
    for delay in (0, 3, 10):
        if delay: time.sleep(delay)
        try:
            with urllib.request.urlopen(request, timeout=30) as response: result = json.loads(response.read().decode())
            if result.get("code") == 0: return result.get("data", {})
            raise RuntimeError(result.get("msg") or "飞书接口失败")
        except Exception as exc: last = exc
    raise last
