import hashlib
import json
from urllib.parse import parse_qsl, quote


DEFAULT_APP_ID = "tt8a56fceb1563152001"
BOOK_ID_STYLE_APP_ID = "tte3a3951e7c939c7701"
CHECKSUM_SALT = "bytetimordance"


def choose_app_id(start_param):
    query = dict(parse_qsl(str(start_param or ""), keep_blank_values=True))
    if "bookId" in query:
        return BOOK_ID_STYLE_APP_ID
    return DEFAULT_APP_ID


def generate(start_path, start_param, app_id=None):
    app_id = app_id or choose_app_id(start_param)
    query = dict(parse_qsl(str(start_param or ""), keep_blank_values=True))
    start_page = f"{start_path}?{_query(query)}"
    base = "sslocal://microapp?" + _query({
        "app_id": app_id,
        "bdp_log": json.dumps({"launch_from": "ad"}, separators=(",", ":")),
        "scene": "0",
        "start_page": start_page,
        "version": "v2",
        "version_type": "current",
    })
    rest = base.split("://", 1)[1]
    digest = hashlib.md5((rest[:10] + CHECKSUM_SALT + rest[10:]).encode("utf-8")).hexdigest()
    return base + "&bdpsum=" + digest[2:6] + digest[20:23]


def _query(values):
    return "&".join(
        f"{quote(str(key), safe='')}={quote(str(value), safe='')}"
        for key, value in sorted(values.items())
        if value is not None
    )
