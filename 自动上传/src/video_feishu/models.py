from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class PreviewStatus(StrEnum):
    READY = "可执行"
    COLLISION = "目标同名跳过"
    UNMATCHED = "未匹配"


class MoveStatus(StrEnum):
    PENDING = "待移动"
    MOVED = "已移动"
    SKIPPED = "已跳过"
    FAILED = "移动失败"


class WriteStatus(StrEnum):
    NOT_REQUIRED = "无需写表"
    PENDING = "待写表"
    WRITTEN = "写表成功"
    FAILED = "写表失败"


@dataclass(frozen=True)
class SourceRow:
    book: str
    tag: object
    activity_page: object
    program_link: object


@dataclass(frozen=True)
class PreviewItem:
    source: Path
    destination: Path
    outer_folder: str
    match_name: str
    status: PreviewStatus
    source_row: SourceRow | None


@dataclass(frozen=True)
class ExecutionItem:
    preview: PreviewItem
    move_status: MoveStatus
    write_status: WriteStatus
    error: str = ""
