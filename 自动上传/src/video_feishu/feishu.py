from dataclasses import dataclass
import json
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import Request, urlopen

from .models import SourceRow


BASE_URL = "https://open.feishu.cn/open-apis"


class FeishuError(RuntimeError):
    pass


@dataclass(frozen=True)
class DocumentUrl:
    kind: str
    token: str
    sheet_id: str = ""


def parse_document_url(url: str) -> DocumentUrl:
    parsed = urlparse(url.strip())
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2 or parts[0] not in {"wiki", "sheets"}:
        raise ValueError("表格链接必须是飞书 wiki 或 sheets 链接")
    return DocumentUrl(parts[0], parts[1], parse_qs(parsed.query).get("sheet", [""])[0])


def source_rows_by_last_book(values: list[list[object]]) -> dict[str, SourceRow]:
    if not values:
        raise FeishuError("复制表为空")
    headers = [str(v).strip() for v in values[0]]
    required = ["书名", "标签", "活动页", "程序链接"]
    missing = [name for name in required if name not in headers]
    if missing:
        raise FeishuError(f"复制表缺少表头：{', '.join(missing)}")
    indexes = {name: headers.index(name) for name in required}
    result: dict[str, SourceRow] = {}
    for row in values[1:]:
        def cell(name: str) -> object:
            index = indexes[name]
            return row[index] if index < len(row) else ""
        book = str(cell("书名")).strip()
        if book:
            result[book] = SourceRow(book, cell("标签"), cell("活动页"), cell("程序链接"))
    return result


class FeishuClient:
    def __init__(self, opener: Callable = urlopen):
        self.opener = opener
        self.access_token = ""

    def _request(self, method: str, path: str, body: dict | None = None, stage: str = "调用飞书接口") -> dict:
        data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        request = Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
        for attempt in range(2):
            try:
                with self.opener(request, timeout=20) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if payload.get("code", 0) != 0:
                    raise FeishuError(f"飞书错误 {payload.get('code')}: {payload.get('msg', '未知错误')}")
                return payload
            except HTTPError as exc:
                if attempt == 0 and (exc.code == 429 or exc.code >= 500):
                    time.sleep(1)
                    continue
                try:
                    error_payload = json.loads(exc.read().decode("utf-8", errors="replace"))
                    detail = f"{error_payload.get('code', '')}: {error_payload.get('msg', '')}".strip(": ")
                except (json.JSONDecodeError, AttributeError):
                    detail = exc.reason or "未知错误"
                raise FeishuError(f"{stage}失败（HTTP {exc.code}）：{detail}") from exc
            except (URLError, TimeoutError) as exc:
                raise FeishuError(f"{stage}失败：无法连接飞书（{exc}）") from exc
        raise FeishuError("飞书请求失败")

    def authenticate(self, app_id: str, app_secret: str) -> None:
        payload = self._request("POST", "/auth/v3/tenant_access_token/internal/", {"app_id": app_id, "app_secret": app_secret}, "获取飞书访问凭证")
        self.access_token = payload["tenant_access_token"]

    def resolve_spreadsheet(self, url: str) -> tuple[str, str]:
        parsed = parse_document_url(url)
        if parsed.kind == "sheets":
            return parsed.token, parsed.sheet_id
        payload = self._request("GET", f"/wiki/v2/spaces/get_node?{urlencode({'token': parsed.token})}", stage="解析复制表 Wiki 链接")
        node = payload.get("data", {}).get("node", {})
        if node.get("obj_type") != "sheet":
            raise FeishuError("复制链接指向的不是电子表格")
        return node["obj_token"], ""

    def list_sheets(self, token: str) -> list[dict]:
        payload = self._request("GET", f"/sheets/v3/spreadsheets/{quote(token)}/sheets/query", stage="读取工作表列表")
        return payload.get("data", {}).get("sheets", [])

    def read_values(self, token: str, sheet_id: str) -> list[list[object]]:
        range_value = quote(sheet_id, safe="")
        payload = self._request("GET", f"/sheets/v2/spreadsheets/{quote(token)}/values/{range_value}", stage="读取表格数据")
        return payload.get("data", {}).get("valueRange", {}).get("values", [])

    def append_values(self, token: str, sheet_id: str, rows: list[list[object]], start_column: str = "A", end_column: str = "D") -> None:
        if not rows:
            return
        range_value = f"{sheet_id}!{start_column}:{end_column}"
        self._request(
            "POST",
            f"/sheets/v2/spreadsheets/{quote(token)}/values_append?insertDataOption=INSERT_ROWS",
            {"valueRange": {"range": range_value, "values": rows}},
            "追加粘贴表数据",
        )

    def write_values(self, token: str, range_value: str, values: list[list[object]]) -> None:
        self._request(
            "PUT",
            f"/sheets/v2/spreadsheets/{quote(token)}/values",
            {"valueRange": {"range": range_value, "values": values}},
            "更新粘贴表数据",
        )
