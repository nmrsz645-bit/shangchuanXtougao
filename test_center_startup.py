from pathlib import Path

from center_startup import is_enabled, set_enabled
from 投稿中心 import app_version


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


def test_center_title_reads_the_local_version_file():
    assert app_version(ROOT) == "1.0.17"


def test_center_title_reads_the_packaged_version_file(tmp_path):
    (tmp_path / "version.json").write_text('{"version":"1.2.3"}', encoding="utf-8")

    assert app_version(tmp_path) == "1.2.3"


def test_packaged_version_takes_precedence_over_a_preserved_old_source_version(tmp_path):
    (tmp_path / "version.json").write_text('{"version":"1.2.3"}', encoding="utf-8")
    source_root = tmp_path / "API投稿2.0"
    source_root.mkdir()
    (source_root / "version.json").write_text('{"version":"0.9.0"}', encoding="utf-8")

    assert app_version(tmp_path) == "1.2.3"
