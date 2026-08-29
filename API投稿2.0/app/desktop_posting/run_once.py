from datetime import date, datetime, timedelta
from pathlib import Path
import time

from .feishu_client import mark_row_green, update_row
from .microapp_link import generate
from .plans import available_entries, sync_auto_proxy_plan
from .posting_service import cover_id, parse_program_fields, posted_time, select_material
from .qianchuan_client import build_promotion_body, choose_compatible_template, create_promotion, list_projects, list_promotions, project_base_name, refresh_if_needed, resolve_latest_project, search_materials
from .queue_service import claim_next_task, release_task
from .settings import load_settings
from .storage import StateStore


def should_unlock_target_for_capacity_limit(error):
    message = str(error or "")
    return "count exceeds 100" in message.lower() or "单个项目下单元数量超过限制" in message


def is_duplicate_promotion_name_error(error):
    message = str(error or "")
    lowered = message.lower()
    # This function is only used around the create-promotion request.  The
    # platform has returned several Chinese and English wordings over time,
    # so accept every explicit duplicate-name response instead of depending
    # on one exact error sentence.
    return (
        "名称重复" in message
        or "名称已存在" in message
        or "name duplicate" in lowered
        or "duplicate name" in lowered
        or ("promotion" in lowered and "name" in lowered and "duplicate" in lowered)
    )


def promotion_name(base_name, suffix):
    return str(base_name) if int(suffix) <= 0 else f"{base_name}{int(suffix)}"


def create_with_unique_name(access_token, base_body, base_name, start_suffix, on_duplicate, create_func=create_promotion, sleep_func=time.sleep, max_attempts=50):
    next_suffix = int(start_suffix)
    for attempt in range(max_attempts):
        suffix = int(start_suffix) + attempt
        body = dict(base_body)
        body["name"] = promotion_name(base_name, suffix)
        try:
            return create_func(access_token, body), suffix
        except Exception as exc:
            if not is_duplicate_promotion_name_error(exc):
                raise
            next_suffix = suffix + 1
            on_duplicate(next_suffix)
            if attempt + 1 < max_attempts:
                sleep_func(2)
    return None, next_suffix


def newer_suffix_project(projects, current_project):
    latest = resolve_latest_project(projects, project_base_name(current_project.get("name")))
    if latest and str(latest.get("project_id") or latest.get("id")) != str(current_project.get("project_id") or current_project.get("id")):
        return latest
    return None


def set_runtime_activity(store, status, book="", advertiser_id="", project_name="", project_id="", result=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    values = {
        "runtime_current_status": status,
        "runtime_current_book": book,
        "runtime_current_advertiser_id": advertiser_id,
        "runtime_current_project": project_name,
        "runtime_current_project_id": project_id,
        "runtime_updated_at": now,
    }
    if result:
        values.update({
            "runtime_last_result": result,
            "runtime_last_book": book,
            "runtime_last_advertiser_id": advertiser_id,
            "runtime_last_project": project_name,
            "runtime_last_project_id": project_id,
            "runtime_last_updated_at": now,
        })
    store.set_states(values)


def finish_runtime_activity(store, book, advertiser_id, project, result):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    store.set_states({
        "runtime_current_status": "idle",
        "runtime_current_book": "",
        "runtime_current_advertiser_id": "",
        "runtime_current_project": "",
        "runtime_current_project_id": "",
        "runtime_updated_at": now,
        "runtime_last_result": result,
        "runtime_last_book": book,
        "runtime_last_advertiser_id": advertiser_id,
        "runtime_last_project": str(project.get("name") or project.get("project_id") or "") if project else "",
        "runtime_last_project_id": str(project.get("project_id") or "") if project else "",
        "runtime_last_updated_at": now,
    })


def choose_compatible_target(entries, access_token, start_param, list_projects_func=list_projects, list_promotions_func=list_promotions):
    project_cache = {}
    for entry in entries:
        advertiser_id = entry.project.advertiser_id
        projects = project_cache.get(advertiser_id)
        if projects is None:
            projects = list_projects_func(access_token, advertiser_id)
            project_cache[advertiser_id] = projects
        project = resolve_latest_project(projects, project_base_name(entry.project.project_name))
        if not project:
            continue
        templates = list_promotions_func(access_token, advertiser_id, project["project_id"])
        template = choose_compatible_template(templates, start_param)
        if template:
            return entry, project, template
    return None


def choose_locked_target(locked_target, access_token, start_param, list_projects_func=list_projects, list_promotions_func=list_promotions):
    advertiser_id = locked_target["advertiser_id"]
    projects = list_projects_func(access_token, advertiser_id)
    project = resolve_latest_project(projects, project_base_name(locked_target.get("project_name") or ""))
    if not project:
        return None
    project_id = str(project.get("project_id") or project.get("id") or "")
    template = choose_compatible_template(list_promotions_func(access_token, advertiser_id, project_id), start_param)
    return (project, template) if template else None


def run_once(base_dir, book_name=None):
    base_dir = Path(base_dir); settings = load_settings(base_dir); store = StateStore(base_dir); store.initialize()
    plan_id = int(store.get_state("active_plan_id", "0") or 0)
    if not plan_id: return "no_active_plan"
    token = refresh_if_needed(base_dir, settings)
    task = claim_next_task(
        settings,
        book_name,
        lambda row_number, values: store.task_allowed_for_plan(row_number, values.get("书名", ""), plan_id),
    )
    if not task: return "no_task"
    values = task["values"]; book = values["书名"]
    target_label = ""
    locked_target = None
    advertiser_id = ""
    project = None
    set_runtime_activity(store, "selecting_target", book)
    try:
        path, params = parse_program_fields(values.get("程序链接"), values.get("启动页"))
        locked_target = store.task_target(task["row_number"], book)
        if locked_target:
            locked = choose_locked_target(locked_target, token["access_token"], params)
            if not locked: raise RuntimeError("原失败项目不存在、无权限或不再兼容该程序链接")
            project, template = locked
            advertiser_id = locked_target["advertiser_id"]
            quota_project_id = None
        else:
            counter_date = date.today().isoformat()
            sync_auto_proxy_plan(store, plan_id, counter_date)
            entries = available_entries(store, plan_id, counter_date)
            if not entries:
                retry_time = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
                release_task(settings, task, "所有项目今日额度已满", False, retry_time)
                finish_runtime_activity(store, book, "", None, "all_projects_full")
                return "all_projects_full"
            target = choose_compatible_target(entries, token["access_token"], params)
            if not target: raise RuntimeError("没有与该程序链接兼容的项目模板")
            entry, project, template = target
            advertiser_id = entry.project.advertiser_id
            quota_project_id = entry.project.project_id
            template_id = str(template.get("promotion_id") or template.get("id") or "")
            store.reserve_task_target(task["row_number"], book, plan_id, quota_project_id, counter_date, advertiser_id, str(project["project_id"]), str(project.get("name") or ""), template_id)
        set_runtime_activity(store, "searching_material", book, advertiser_id, str(project.get("name") or project["project_id"]), str(project["project_id"]))
        target_label = f"失败项目：账户 {advertiser_id} / 项目 {project.get('name') or project['project_id']}"
        material = select_material(search_materials(token["access_token"], advertiser_id, book), book)
        if not material: raise RuntimeError("素材库未找到同名视频")
        material["video_cover_id"] = cover_id(material)
        body = build_promotion_body(template, advertiser_id, project["project_id"], book, values.get("标签", ""), material, path, params, generate(path, params))
        set_runtime_activity(store, "creating_promotion", book, advertiser_id, str(project.get("name") or project["project_id"]), str(project["project_id"]))
        created, next_name_suffix = create_with_unique_name(
            token["access_token"],
            body,
            book,
            store.promotion_name_suffix(task["row_number"], book),
            lambda suffix: store.set_promotion_name_suffix(task["row_number"], book, suffix),
        )
        if created is None:
            retry_time = (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
            reason = f"{target_label} | 单元名称连续重复，稍后从数字 {next_name_suffix} 继续"
            result = "retry_name_duplicate:" + reason
            finish_runtime_activity(store, book, advertiser_id, project, result)
            release_task(settings, task, reason, False, retry_time)
            return result
        update_row(settings, task["sheet_id"], task["headers"], task["row_number"], {"投稿状态": "已投稿", "投稿成功数量": "1", "投稿时间": posted_time(datetime.now()), "失败原因": ""})
        try:
            mark_row_green(settings, task["sheet_id"], task["headers"], task["row_number"])
        except Exception:
            pass
        result = "posted:" + str(created.get("promotion_id") or "")
        finish_runtime_activity(store, book, advertiser_id, project, result)
        return result
    except Exception as exc:
        reason = f"{target_label} | {exc}" if target_label else str(exc)
        reassign_to_newer_suffix = False
        if locked_target and should_unlock_target_for_capacity_limit(exc):
            newer_project = newer_suffix_project(list_projects(token["access_token"], advertiser_id), project)
            if newer_project:
                store.clear_task_target(task["row_number"])
                reassign_to_newer_suffix = True
        retry_at = int(datetime.now().timestamp()) + (0 if reassign_to_newer_suffix else 3600)
        attempts, terminal = store.record_failure(task["row_number"], book, reason, retry_at)
        retry_time = "" if terminal else (datetime.now() + timedelta(seconds=0 if reassign_to_newer_suffix else 3600)).strftime("%Y-%m-%d %H:%M:%S")
        result = ("terminal:" if terminal else "retry:") + reason
        finish_runtime_activity(store, book, advertiser_id, project, result)
        release_task(settings, task, reason, terminal, retry_time)
        return result
