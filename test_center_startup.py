from pathlib import Path

from center_startup import is_enabled, set_enabled


ROOT = Path(__file__).resolve().parent


def test_startup_script_can_be_created_and_removed(tmp_path):
    path = tmp_path / "UploadPostingCenter.vbs"

    set_enabled(True, "C:/Python/python.exe", tmp_path / "start_center.py", path)

    assert is_enabled(path)
    assert "start_center.py" in path.read_text(encoding="utf-8-sig")
    set_enabled(False, "", tmp_path / "start_center.py", path)
    assert not is_enabled(path)


def test_source_launcher_prefers_the_project_virtual_environment():
    launcher = (ROOT / "启动投稿中心.vbs").read_text(encoding="utf-8")

    assert ".venv\\Scripts\\pythonw.exe" in launcher
