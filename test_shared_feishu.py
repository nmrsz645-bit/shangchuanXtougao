from shared_feishu import SharedFeishuSettings, load, save


def test_shared_feishu_settings_round_trip(tmp_path):
    path = tmp_path / "shared.json"
    expected = SharedFeishuSettings("app", "secret", "task", "copy")

    save(path, expected)

    assert load(path) == expected


def test_missing_new_boolean_settings_default_to_false(tmp_path):
    path = tmp_path / "shared.json"
    path.write_text('{"app_id":"app"}', encoding="utf-8")

    assert not load(path).start_with_windows
    assert not load(path).start_tasks_automatically
