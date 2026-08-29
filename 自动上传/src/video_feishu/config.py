from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import sys


@dataclass(frozen=True)
class Settings:
    app_id: str = ""
    copy_url: str = ""
    paste_url: str = ""
    source_dir: str = ""
    destination_dir: str = ""
    auto_start: bool = False
    auto_execute: bool = False
    write_upload_success_to_feishu: bool = False
    material_url: str = "https://ad.oceanengine.com/material_center/management/video?aadvid=1869328457013324#source=ad_navigator"
    batch_size: int = 10
    check_interval_minutes: int = 30
    upload_retry_seconds: int = 60
    max_batch_attempts: int = 3
    upload_timeout_seconds: int = 21600
    upload_stall_timeout_minutes: int = 45
    upload_confirmation_timeout_minutes: int = 6
    recovery_grace_seconds: int = 1800


def app_data_dir() -> Path:
    override = os.environ.get("AUTO_UPLOAD_DATA_DIR")
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "个人数据"
    return Path(__file__).resolve().parents[3] / "个人数据"


def chrome_profile_dir() -> Path:
    return app_data_dir() / "Chrome"


class JsonSettingsStore:
    def __init__(self, path: Path | None = None):
        self.path = path or app_data_dir() / "settings.json"

    def load(self) -> Settings:
        if not self.path.exists():
            return Settings()
        values = json.loads(self.path.read_text("utf-8"))
        allowed = Settings.__dataclass_fields__
        return Settings(**{key: value for key, value in values.items() if key in allowed})

    def save(self, settings: Settings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), "utf-8")
        temp.replace(self.path)


class RetryStore:
    def __init__(self, path: Path | None = None):
        self.path = path or app_data_dir() / "retry.json"

    def load(self) -> list[list[object]]:
        return json.loads(self.path.read_text("utf-8")) if self.path.exists() else []

    def save(self, rows: list[list[object]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
        temp.replace(self.path)

    def append(self, rows: list[list[object]]) -> None:
        self.save([*self.load(), *rows])

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)


class SecretStore:
    SERVICE = "video-feishu-tool"

    def get(self, app_id: str) -> str:
        import keyring
        return keyring.get_password(self.SERVICE, app_id) or ""

    def set(self, app_id: str, secret: str) -> None:
        import keyring
        keyring.set_password(self.SERVICE, app_id, secret)
