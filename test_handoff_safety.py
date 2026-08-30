import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def test_private_runtime_paths_stay_ignored_by_git():
    paths = [
        "共享飞书设置.json",
        "个人数据/example.txt",
        "API投稿2.0/config/settings.json",
        "API投稿2.0/data/state.db",
        "API投稿2.0/logs/worker.log",
        "自动上传/个人数据/Chrome/Default/Cookies",
        "候选发布-test/上传投稿中心/上传投稿中心.exe",
        "发布版/上传投稿中心/个人数据/example.txt",
    ]
    for path in paths:
        result = subprocess.run(["git", "check-ignore", "-q", "--", path], cwd=ROOT, check=False)
        assert result.returncode == 0, path


def test_api_publish_exclude_keeps_runtime_data_out_of_update_packages():
    excluded = set((ROOT / "API投稿2.0" / ".publish-exclude.txt").read_text(encoding="utf-8").splitlines())
    assert {"config", "data", "logs"}.issubset(excluded)


def test_handoff_documents_include_reproducible_local_test_setup():
    requirements = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "pytest" in requirements
    assert "-e ./自动上传[dev]" in requirements
    assert "git clone https://github.com/nmrsz645-bit/shangchuanXtougao.git" in readme
    assert "requirements-dev.txt" in readme
    assert "Google Chrome" in readme
    assert "playwright install chromium" not in readme
