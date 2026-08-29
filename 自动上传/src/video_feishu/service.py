from dataclasses import dataclass
import hashlib
from itertools import groupby
from pathlib import Path
import secrets

from .config import RetryStore, Settings
from .feishu import FeishuClient, FeishuError, source_rows_by_last_book
from .models import ExecutionItem, MoveStatus, PreviewItem, PreviewStatus, SourceRow, WriteStatus
from .video_ops import move_video, remove_empty_descendants, scan_video_batches, validate_roots


@dataclass(frozen=True)
class PreviewResult:
    items: list[PreviewItem]
    token: str
    settings_hash: str
    source_root: Path
    destination_token: str
    destination_sheet: str


def _settings_hash(settings: Settings) -> str:
    return hashlib.sha256(repr(settings).encode("utf-8")).hexdigest()


class OfficialFeishuGateway:
    def __init__(self, client: FeishuClient | None = None):
        self.client = client or FeishuClient()
        self.start_column = "A"
        self.end_column = "D"

    @staticmethod
    def _column(index: int) -> str:
        result = ""
        index += 1
        while index:
            index, remainder = divmod(index - 1, 26)
            result = chr(65 + remainder) + result
        return result

    def connect(self, settings: Settings, secret: str) -> tuple[dict[str, SourceRow], str, str]:
        self.client.authenticate(settings.app_id, secret)
        source_token, _ = self.client.resolve_spreadsheet(settings.copy_url)
        destination_token, destination_hint = self.client.resolve_spreadsheet(settings.paste_url)
        source_sheets = self.client.list_sheets(source_token)
        if len(source_sheets) != 1:
            raise FeishuError("复制表必须只有一个子表")
        destination_sheets = [s for s in self.client.list_sheets(destination_token) if s.get("title") == "Sheet1"]
        if len(destination_sheets) != 1:
            raise FeishuError("粘贴表必须包含唯一的 Sheet1")
        source_id = source_sheets[0].get("sheet_id")
        destination_id = destination_sheets[0].get("sheet_id") or destination_hint
        rows = source_rows_by_last_book(self.client.read_values(source_token, source_id))
        target_values = self.client.read_values(destination_token, destination_id)
        if not target_values:
            raise FeishuError("粘贴表缺少表头")
        headers = [str(v).strip() for v in target_values[0]]
        required = ["书名", "标签", "启动页", "程序链接"]
        if any(name not in headers for name in required):
            missing = [name for name in required if name not in headers]
            raise FeishuError(f"粘贴表缺少表头：{', '.join(missing)}")
        indexes = [headers.index(name) for name in required]
        if indexes != list(range(min(indexes), min(indexes) + 4)):
            raise FeishuError("粘贴表四个目标列必须连续且顺序为书名、标签、启动页、程序链接")
        self.start_column, self.end_column = self._column(indexes[0]), self._column(indexes[-1])
        return rows, destination_token, destination_id

    def append(self, token: str, sheet: str, rows: list[list[object]]) -> None:
        self.client.append_values(token, sheet, rows, self.start_column, self.end_column)


def mark_uploaded_names(settings: Settings, secret: str, names: list[str], client: FeishuClient | None = None) -> set[str]:
    client = client or FeishuClient()
    client.authenticate(settings.app_id, secret)
    token, sheet_hint = client.resolve_spreadsheet(settings.paste_url)
    sheets = [sheet for sheet in client.list_sheets(token) if sheet.get("title") == "Sheet1"]
    if len(sheets) != 1:
        raise FeishuError("粘贴表必须包含唯一的 Sheet1")
    sheet_id = sheets[0].get("sheet_id") or sheet_hint
    values = client.read_values(token, sheet_id)
    last_rows: dict[str, tuple[int, object, object]] = {}
    for row_number, row in enumerate(values, start=1):
        if not row:
            continue
        name = str(row[0]).strip()
        if name:
            existing = row[4] if len(row) > 4 else ""
            last_rows[name] = (row_number, row[0], existing)
    completed: set[str] = set()
    for name in names:
        match = last_rows.get(name)
        if not match:
            continue
        row_number, value, existing = match
        if str(existing).strip() != str(value).strip():
            client.write_values(token, f"{sheet_id}!E{row_number}:E{row_number}", [[value]])
        completed.add(name)
    return completed


class TaskService:
    def __init__(self, feishu=None, retries: RetryStore | None = None):
        self.feishu = feishu or OfficialFeishuGateway()
        self.retries = retries or RetryStore()

    def preview(self, settings: Settings, secret: str) -> PreviewResult:
        source, destination = validate_roots(Path(settings.source_dir), Path(settings.destination_dir))
        rows, destination_token, destination_sheet = self.feishu.connect(settings, secret)
        items = []
        for outer_folder, videos in scan_video_batches(source):
            for video in videos:
                target = destination / video.name
                match = rows.get(video.stem)
                status = PreviewStatus.COLLISION if target.exists() else (PreviewStatus.READY if match else PreviewStatus.UNMATCHED)
                items.append(PreviewItem(video, target, outer_folder, video.stem, status, match))
        return PreviewResult(items, secrets.token_urlsafe(24), _settings_hash(settings), source, destination_token, destination_sheet)

    def execute(self, preview: PreviewResult, confirmation_token: str) -> list[ExecutionItem]:
        if confirmation_token != preview.token:
            raise ValueError("预览确认已失效，请重新扫描")
        results: list[ExecutionItem] = []
        for _, batch in groupby(preview.items, key=lambda item: item.outer_folder):
            batch_items = list(batch)
            batch_results: list[ExecutionItem] = []
            write_rows: list[list[object]] = []
            for item in batch_items:
                if item.status == PreviewStatus.COLLISION:
                    batch_results.append(ExecutionItem(item, MoveStatus.SKIPPED, WriteStatus.NOT_REQUIRED))
                    continue
                try:
                    moved = move_video(item.source, item.destination)
                    if not moved:
                        batch_results.append(ExecutionItem(item, MoveStatus.SKIPPED, WriteStatus.NOT_REQUIRED, "目标同名"))
                    elif item.source_row:
                        row = item.source_row
                        write_rows.append([row.book, row.tag, row.activity_page, row.program_link])
                        batch_results.append(ExecutionItem(item, MoveStatus.MOVED, WriteStatus.PENDING))
                    else:
                        batch_results.append(ExecutionItem(item, MoveStatus.MOVED, WriteStatus.NOT_REQUIRED))
                except OSError as exc:
                    batch_results.append(ExecutionItem(item, MoveStatus.FAILED, WriteStatus.NOT_REQUIRED, str(exc)))
            if write_rows:
                try:
                    self.feishu.append(preview.destination_token, preview.destination_sheet, write_rows)
                except Exception:
                    self.retries.append(write_rows)
                    batch_results = [ExecutionItem(r.preview, r.move_status, WriteStatus.FAILED if r.write_status == WriteStatus.PENDING else r.write_status, r.error) for r in batch_results]
                else:
                    batch_results = [ExecutionItem(r.preview, r.move_status, WriteStatus.WRITTEN if r.write_status == WriteStatus.PENDING else r.write_status, r.error) for r in batch_results]
            results.extend(batch_results)
        remove_empty_descendants(preview.source_root)
        return results

    def retry_failed_writes(self, destination_token: str, destination_sheet: str) -> None:
        rows = self.retries.load()
        if rows:
            self.feishu.append(destination_token, destination_sheet, rows)
            self.retries.clear()
