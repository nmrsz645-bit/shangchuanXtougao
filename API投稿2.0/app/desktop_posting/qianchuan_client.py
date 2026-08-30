import json
import time
import urllib.parse
import urllib.request
import re
from datetime import datetime
from copy import deepcopy
from pathlib import Path

from .settings import callback_auth_code
from .microapp_link import choose_app_id


API = "https://api.oceanengine.com"


def merged_advertiser_ids(configured_text, token_ids):
    values = str(configured_text or "").replace("，", "\n").replace(",", "\n").splitlines() + [str(item) for item in (token_ids or [])]
    result = []
    for value in values:
        value = value.strip()
        if value and value not in result:
            result.append(value)
    return result


def selected_advertiser_ids(configured_text, token_ids):
    configured = merged_advertiser_ids(configured_text, [])
    return configured or [str(item) for item in (token_ids or [])]


def latest_projects_by_name(items):
    selected = {}
    order = []
    for item in items:
        name = str(item.get("name") or "")
        match = re.match(r"^(.*?)(?:_(\d+))?$", name)
        base = match.group(1) if match else name
        suffix = int(match.group(2) or 0) if match else 0
        if base not in selected:
            selected[base] = (suffix, item); order.append(base)
        elif suffix > selected[base][0]:
            selected[base] = (suffix, item)
    return [selected[base][1] for base in order]


def project_base_name(name):
    return re.sub(r"_\d+$", "", str(name or ""))


def resolve_latest_project(items, base_name):
    for item in latest_projects_by_name(items):
        if project_base_name(item.get("name")) == base_name:
            return item
    return None


def template_supports_link(template, start_param, configured_app_id=""):
    mini_program = (template.get("promotion_materials") or {}).get("mini_program_info") or {}
    template_app_id = str(mini_program.get("app_id") or "").strip()
    return not template_app_id or template_app_id == choose_app_id(start_param, configured_app_id)


def choose_compatible_template(promotions, start_param, configured_app_id=""):
    usable = [
        item for item in promotions
        if item.get("promotion_materials")
        and not str(item.get("promotion_name") or item.get("name") or "").startswith("API_TEST")
        and template_supports_link(item, start_param, configured_app_id)
    ]
    enabled = [item for item in usable if item.get("opt_status") != "DISABLE"]
    if enabled:
        return enabled[0]
    if usable:
        return usable[0]
    return None


def import_callback(base_dir, settings, url):
    body = {"app_id": settings.qianchuan_app_id, "secret": settings.qianchuan_secret, "grant_type": "auth_code", "auth_code": callback_auth_code(url)}
    data = _post("/open_api/oauth2/access_token/", body, {})
    saved = {"access_token": data["access_token"], "refresh_token": data["refresh_token"], "expires_at": int(time.time()) + int(data["expires_in"]), "refresh_expires_at": int(time.time()) + int(data["refresh_token_expires_in"]), "advertiser_ids": [str(x) for x in data.get("advertiser_ids", [])]}
    path = Path(base_dir) / "config" / "tokens.json"; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
    return saved


def load_token(base_dir):
    return json.loads((Path(base_dir) / "config" / "tokens.json").read_text(encoding="utf-8"))


def is_access_token_expired_error(error):
    message = str(error or "").lower()
    return "access_token" in message and any(marker in message for marker in ("\u8fc7\u671f", "expired", "expire"))


def refresh_if_needed(base_dir, settings, force=False):
    token = load_token(base_dir)
    if not force and int(token.get("expires_at", 0)) - time.time() > 300:
        return token
    data = _post("/open_api/oauth2/refresh_token/", {"app_id": settings.qianchuan_app_id, "secret": settings.qianchuan_secret, "grant_type": "refresh_token", "refresh_token": token["refresh_token"]}, {})
    token.update({"access_token": data["access_token"], "refresh_token": data["refresh_token"], "expires_at": int(time.time()) + int(data["expires_in"]), "refresh_expires_at": int(time.time()) + int(data["refresh_token_expires_in"]), "advertiser_ids": [str(x) for x in data.get("advertiser_ids", token.get("advertiser_ids", []))]})
    (Path(base_dir) / "config" / "tokens.json").write_text(json.dumps(token, ensure_ascii=False, indent=2), encoding="utf-8")
    return token


def list_projects(access_token, advertiser_id):
    return _get("/open_api/v3.0/project/list/", access_token, {"advertiser_id": advertiser_id, "page": 1, "page_size": 100}).get("list", [])


def search_materials(access_token, advertiser_id, book_name):
    target = str(book_name or "").strip()
    if not target:
        return []
    deadline = time.monotonic() + 120
    page = 1
    while True:
        result = _get("/open_api/2/file/video/get/", access_token, {"advertiser_id": advertiser_id, "filename": target, "page": page, "page_size": 100})
        items = result.get("list", [])
        matches = material_name_matches(items, target)
        if matches:
            return sorted(matches, key=material_created_key, reverse=True)
        if time.monotonic() >= deadline:
            return []
        page_info = result.get("page_info") or {}
        try:
            total_page = int(page_info.get("total_page") or 0)
        except (TypeError, ValueError):
            total_page = 0
        if not items or (total_page and page >= total_page):
            return []
        page += 1


def material_name_matches(items, book_name):
    target = str(book_name or "").strip()
    names = [(item, str(item.get("filename") or item.get("name") or "").rsplit(".", 1)[0].strip()) for item in items]
    exact = [item for item, name in names if name == target]
    return exact or [item for item, name in names if target in name]


def material_created_key(item):
    value = item.get("create_time") or 0
    try: return int(value)
    except (TypeError, ValueError):
        try: return int(datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").timestamp())
        except ValueError: return 0


def list_promotions(access_token, advertiser_id, project_id):
    promotions = []
    page = 1
    while True:
        result = _get(
            "/open_api/v3.0/promotion/list/",
            access_token,
            {
                "advertiser_id": advertiser_id,
                "filtering": json.dumps({"project_id": int(project_id)}, separators=(",", ":")),
                "page": page,
                "page_size": 20,
            },
        )
        items = result.get("list", [])
        promotions.extend(items)
        page_info = result.get("page_info") or {}
        total_page = int(page_info.get("total_page") or page)
        if not items or page >= total_page:
            return promotions
        page += 1


def create_promotion(access_token, body):
    return _post("/open_api/v3.0/promotion/create/", body, {"Access-Token": access_token})


def video_info(access_token, advertiser_id, video_id):
    items = _get("/open_api/2/file/video/ad/get/", access_token, {"advertiser_id": advertiser_id, "video_ids": json.dumps([str(video_id)], separators=(",", ":"))}).get("list", [])
    return items[0] if items else {}


def build_promotion_body(template, advertiser_id, project_id, book_name, tag, material, start_path, start_param, landing_url, app_id=None):
    materials = deepcopy(template.get("promotion_materials") or {}); native = deepcopy(template.get("native_setting") or {}); materials["title_material_list"] = [{"title": tag or book_name}]
    native["is_feed_and_fav_see"] = "ON"
    materials["video_material_list"] = [{"video_id": str(material.get("video_id") or material.get("id")), "video_cover_id": material.get("video_cover_id") or material.get("cover_id"), "image_mode": ((materials.get("video_material_list") or [{}])[0].get("image_mode") or "CREATIVE_IMAGE_MODE_VIDEO_VERTICAL"), "video_hp_visibility": "ALWAYS_VISIBLE"}]
    materials["mini_program_info"] = {"app_id": choose_app_id(start_param, app_id), "start_path": start_path, "params": start_param, "url": landing_url}
    body = {"advertiser_id": int(advertiser_id), "project_id": int(project_id), "name": book_name, "operation": "ENABLE", "promotion_materials": materials, "native_setting": native}
    for key in ("ad_download_status","auto_extend_traffic","bid","brand_info","budget","budget_mode","config_id","cpa_bid","creative_auto_generate_switch","deep_cpabid","first_roi_goal","is_comment_disable","materials_type","roi_goal","source","union_bid_ratio"):
        if template.get(key) is not None: body[key] = deepcopy(template[key])
    return body


def _get(path, token, params):
    url = API + path + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Access-Token": token})
    return _request(request).get("data") or {}


def _post(path, body, headers):
    request = urllib.request.Request(API + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}, method="POST")
    return _request(request).get("data") or {}


def _request(request):
    for attempt in range(2):
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode())
        if result.get("code") == 0: return result
        message = str(result.get("message") or "")
        if attempt == 0 and any(word in message for word in ("请重试", "服务错误", "频率")):
            time.sleep(3); continue
        raise RuntimeError(f"千川接口失败：{message} ({result.get('request_id')})")
