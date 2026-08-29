import json
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse


@dataclass
class AppSettings:
    qianchuan_app_id: str = ""
    qianchuan_secret: str = ""
    feishu_app_id: str = ""
    feishu_secret: str = ""
    submission_sheet_url: str = ""
    configured_advertiser_ids: str = ""


def _path(base_dir):
    return Path(base_dir) / "config" / "settings.json"


def save_settings(base_dir, settings):
    path = _path(base_dir); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")


def load_settings(base_dir):
    try:
        return AppSettings(**json.loads(_path(base_dir).read_text(encoding="utf-8")))
    except FileNotFoundError:
        return AppSettings()


def callback_auth_code(url):
    code = parse_qs(urlparse(url).query).get("auth_code", [""])[0].strip()
    if not code:
        raise ValueError("callback URL does not contain auth_code")
    return code
