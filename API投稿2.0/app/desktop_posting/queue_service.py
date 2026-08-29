from .feishu_client import read_sheet1, update_row
from .feishu_queue import claim_values, find_claimable_row, validate_headers


def claim_next_task(settings, book_name=None, can_claim=None):
    sheet_id, rows = read_sheet1(settings)
    if not rows:
        return None
    headers = [str(value or "") for value in rows[0]]
    missing = validate_headers(headers)
    if missing:
        raise RuntimeError("投稿表格缺少表头：" + "、".join(missing))
    task = find_claimable_row(headers, rows[1:], book_name, can_claim)
    if not task:
        return None
    updates = claim_values()
    update_row(settings, sheet_id, headers, task["row_number"], updates)
    _, reread_rows = read_sheet1(settings)
    reread = find_claimed_row(headers, reread_rows[1:], task["row_number"])
    if not reread or reread["values"].get("领取批次号") != updates["领取批次号"]:
        return None
    reread["claim"] = updates; reread["sheet_id"] = sheet_id; reread["headers"] = headers
    return reread


def find_claimed_row(headers, rows, row_number):
    index = row_number - 2
    if index < 0 or index >= len(rows):
        return None
    values = {name: str(rows[index][position]).strip() if position < len(rows[index]) and rows[index][position] is not None else "" for position, name in enumerate(headers)}
    return {"row_number": row_number, "values": values}


def release_task(settings, task, reason, terminal=False, retry_time=""):
    status = "彻底失败" if terminal else "等待重试"
    update_row(settings, task["sheet_id"], task["headers"], task["row_number"], {"领取状态": status, "领取电脑": "", "领取时间": "", "领取批次号": "", "领取过期时间": retry_time, "失败原因": reason})
