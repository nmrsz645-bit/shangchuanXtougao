def needs_daily_check(last_checked: str, today: str) -> bool:
    return bool(last_checked) and last_checked != today
