from center_startup import is_enabled, set_enabled


def test_startup_script_can_be_created_and_removed(tmp_path):
    path = tmp_path / "UploadPostingCenter.vbs"

    set_enabled(True, "C:/Python/python.exe", tmp_path / "start_center.py", path)

    assert is_enabled(path)
    assert "start_center.py" in path.read_text(encoding="utf-8-sig")
    set_enabled(False, "", tmp_path / "start_center.py", path)
    assert not is_enabled(path)
