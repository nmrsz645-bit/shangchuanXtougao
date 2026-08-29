from video_feishu.config import JsonSettingsStore, RetryStore, Settings, app_data_dir
from video_feishu.startup import cleanup_old_versions, is_auto_start_enabled, set_auto_start, startup_file


def test_cleanup_old_versions_removes_only_update_backups(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    executable = app / "tool.exe"
    executable.write_bytes(b"new")
    previous = tmp_path / "app.previous"
    archived = tmp_path / "app.previous.archived-1"
    personal = app / "personal-data"
    previous.mkdir()
    archived.mkdir()
    personal.mkdir()

    cleanup_old_versions(executable)

    assert not previous.exists()
    assert not archived.exists()
    assert personal.exists()


def test_settings_json_never_contains_secret(tmp_path):
    store = JsonSettingsStore(tmp_path / "settings.json")
    settings = Settings("app-id", "copy", "paste", "src", "dst", True, True)
    store.save(settings)
    assert store.load() == settings
    assert "secret" not in (tmp_path / "settings.json").read_text("utf-8").lower()


def test_stall_timeout_is_saved_with_settings(tmp_path):
    store = JsonSettingsStore(tmp_path / "settings.json")
    store.save(Settings(upload_stall_timeout_minutes=45))

    assert store.load().upload_stall_timeout_minutes == 45


def test_confirmation_timeout_is_saved_with_settings(tmp_path):
    store = JsonSettingsStore(tmp_path / "settings.json")
    store.save(Settings(upload_confirmation_timeout_minutes=6))

    assert store.load().upload_confirmation_timeout_minutes == 6


def test_retry_store_round_trip(tmp_path):
    store = RetryStore(tmp_path / "retry.json")
    rows = [["书A", "标签", "启动", "程序"]]
    store.save(rows)
    assert store.load() == rows
    store.clear()
    assert store.load() == []


def test_auto_start_writes_startup_command(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    target = tmp_path / "VideoFeishuTool.exe"
    set_auto_start(True, target)
    assert is_auto_start_enabled()
    command = startup_file().read_text("utf-8")
    assert str(target) in command
    assert "start /wait" in command
    assert "goto restart" in command
    set_auto_start(False, target)
    assert not is_auto_start_enabled()


def test_personal_data_directory_can_be_kept_outside_program(tmp_path, monkeypatch):
    personal = tmp_path / "个人数据"
    monkeypatch.setenv("AUTO_UPLOAD_DATA_DIR", str(personal))
    assert app_data_dir() == personal
