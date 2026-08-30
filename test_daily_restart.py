from daily_restart import needs_daily_check


def test_daily_check_is_due_on_first_start_and_after_the_date_changes():
    assert needs_daily_check("", "2026-08-19")
    assert not needs_daily_check("2026-08-19", "2026-08-19")
    assert needs_daily_check("2026-08-18", "2026-08-19")
