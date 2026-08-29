import socket
import uuid
from datetime import datetime, timedelta

REQUIRED_HEADERS = ("书名", "标签", "启动页", "程序链接", "领取状态", "领取电脑", "领取时间", "领取批次号", "领取过期时间", "投稿状态")


def validate_headers(headers):
    return [name for name in REQUIRED_HEADERS if name not in headers]


def find_claimable_row(headers, rows, book_name=None, can_claim=None):
    columns = {name: index for index, name in enumerate(headers)}
    for index, row in enumerate(rows, start=2):
        values = {name: str(row[position]).strip() if position < len(row) and row[position] is not None else "" for name, position in columns.items()}
        if can_claim and not can_claim(index, values):
            continue
        if not values.get("书名") or (book_name and values.get("书名") != book_name) or values.get("投稿状态") == "已投稿" or values.get("领取状态") == "彻底失败":
            continue
        if not values.get("领取状态") or _claim_expired(values.get("领取过期时间", "")):
            return {"row_number": index, "values": values}
    return None


def _claim_expired(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S") <= datetime.now()
    except ValueError:
        return False


def claim_values(lock_minutes=30, now=None):
    now = now or datetime.now()
    return {"领取状态": "已领取", "领取电脑": socket.gethostname(), "领取时间": now.strftime("%Y-%m-%d %H:%M:%S"), "领取批次号": uuid.uuid4().hex, "领取过期时间": (now + timedelta(minutes=lock_minutes)).strftime("%Y-%m-%d %H:%M:%S")}
