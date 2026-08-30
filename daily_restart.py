def needs_daily_check(last_checked: str, today: str) -> bool:
    return last_checked != today
