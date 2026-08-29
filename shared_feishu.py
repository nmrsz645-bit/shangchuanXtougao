from dataclasses import asdict, dataclass
import json
from pathlib import Path


@dataclass
class SharedFeishuSettings:
    app_id: str = ""
    secret: str = ""
    task_sheet_url: str = ""
    copy_sheet_url: str = ""
    start_with_windows: bool = False
    start_tasks_automatically: bool = False
    daily_restart_enabled: bool = True
    last_daily_restart_check: str = ""


def load(path: Path) -> SharedFeishuSettings:
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return SharedFeishuSettings()
    return SharedFeishuSettings(**{key: values.get(key, field.default) for key, field in SharedFeishuSettings.__dataclass_fields__.items()})


def save(path: Path, settings: SharedFeishuSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
