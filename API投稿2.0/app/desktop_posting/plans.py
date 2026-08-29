from .models import PlanEntry, ProjectRef


AUTO_PROXY_LOW_LIMIT = 40
AUTO_PROXY_HIGH_LIMIT = 83


def _auto_proxy_key(plan_id, field):
    return f"plan_auto_proxy_{field}_{int(plan_id)}"


def auto_proxy_enabled(store, plan_id):
    return store.get_state(_auto_proxy_key(plan_id, "enabled"), "0") == "1"


def set_auto_proxy_enabled(store, plan_id, enabled, today):
    store.set_state(_auto_proxy_key(plan_id, "enabled"), "1" if enabled else "0")
    if not enabled:
        return None, False
    store.set_states({
        _auto_proxy_key(plan_id, "date"): today,
        _auto_proxy_key(plan_id, "limit"): AUTO_PROXY_LOW_LIMIT,
    })
    return sync_auto_proxy_plan(store, plan_id, today)


def sync_auto_proxy_plan(store, plan_id, today):
    if not auto_proxy_enabled(store, plan_id):
        return None, False
    saved_date = store.get_state(_auto_proxy_key(plan_id, "date"), "")
    saved_limit = store.get_state(_auto_proxy_key(plan_id, "limit"), str(AUTO_PROXY_LOW_LIMIT))
    phase_limit = int(saved_limit) if saved_limit in (str(AUTO_PROXY_LOW_LIMIT), str(AUTO_PROXY_HIGH_LIMIT)) else AUTO_PROXY_LOW_LIMIT
    if saved_date and saved_date > today:
        return phase_limit, False
    if saved_date != today:
        phase_limit = AUTO_PROXY_LOW_LIMIT
    entries = store.list_plan_entries(plan_id)
    if phase_limit == AUTO_PROXY_LOW_LIMIT and entries and all(
        store.project_count(plan_id, row[4], today) >= AUTO_PROXY_LOW_LIMIT for row in entries
    ):
        phase_limit = AUTO_PROXY_HIGH_LIMIT
    state_changes = {}
    if saved_date != today:
        state_changes[_auto_proxy_key(plan_id, "date")] = today
    if saved_limit != str(phase_limit):
        state_changes[_auto_proxy_key(plan_id, "limit")] = phase_limit
    if state_changes:
        store.set_states(state_changes)
    limits_changed = any(int(row[7]) != phase_limit for row in entries)
    if limits_changed:
        store.update_plan_limits(plan_id, phase_limit)
    return phase_limit, limits_changed


def sync_auto_proxy_plans(store, today):
    changed_plan_ids = set()
    for plan_id, _ in store.list_plans():
        _, limits_changed = sync_auto_proxy_plan(store, plan_id, today)
        if limits_changed:
            changed_plan_ids.add(int(plan_id))
    return changed_plan_ids


def create_plan(store, name):
    name = name.strip()
    if not name:
        raise ValueError("方案名称不能为空")
    return store.create_plan(name)


def add_plan_entry(store, plan_id, project, daily_limit):
    if int(daily_limit) <= 0:
        raise ValueError("项目投稿数量必须大于 0")
    store.add_plan_entry(plan_id, project, int(daily_limit))


def choose_active_entry(store, plan_id, today):
    entries = available_entries(store, plan_id, today)
    return entries[0] if entries else None


def available_entries(store, plan_id, today):
    entries = []
    for row in store.list_plan_entries(plan_id):
        entry = PlanEntry(row[0], row[1], ProjectRef(row[2], row[3], row[4], row[5]), row[6], row[7], bool(row[8]))
        if entry.enabled and store.project_count(plan_id, entry.project.project_id, today) < entry.daily_limit:
            entries.append(entry)
    return entries


def move_entry(store, plan_id, entry_id, delta):
    rows = store.list_plan_entries(plan_id)
    ids = [row[0] for row in rows]
    current = ids.index(entry_id); target = max(0, min(len(ids) - 1, current + delta))
    ids[current], ids[target] = ids[target], ids[current]
    store.set_entry_order(plan_id, ids)


def project_picker_label(project):
    return f"{project.advertiser_name} | {project.project_name}"


def valid_daily_limit(value):
    limit = int(value)
    if limit <= 0:
        raise ValueError("每日投稿数量必须大于 0")
    return limit
