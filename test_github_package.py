import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

import pytest

from release import build_github_package as builder


def test_unverified_updater_is_rejected_before_output_creation(tmp_path):
    updater = tmp_path / "UpdateAgent.exe"
    updater.write_bytes(b"unknown binary")
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="updater SHA-256"):
        builder.assemble(tmp_path / "dist", updater, output, "0" * 40)
    assert not output.exists()


def test_clean_package_has_launchers_docs_and_no_runtime_files(tmp_path, monkeypatch):
    verified = []
    monkeypatch.setattr(builder, "verify_frozen_source", lambda *args: verified.append(args), raising=False)
    app = tmp_path / "dist"
    (app / "_internal").mkdir(parents=True)
    (app / "上传投稿中心.exe").write_bytes(b"test executable")
    (app / "_internal" / "python313.dll").write_bytes(b"test runtime")
    updater = tmp_path / "UpdateAgent.exe"
    updater.write_bytes(b"audited test fixture")
    monkeypatch.setattr(builder, "UPDATER_SHA256", hashlib.sha256(updater.read_bytes()).hexdigest())
    output = tmp_path / "release"
    full = builder.assemble(app, updater, output, "0" * 40)
    assert verified == [(app, "0" * 40)]
    with zipfile.ZipFile(full) as z:
        names = set(z.namelist())
        assert {"Start.cmd", "README.md", "HANDOFF.md", "BUILD-INFO.json",
                "updater/UpdateAgent.exe", "updater/updater-config.json",
                "app/version.json", "app/Start-App.cmd"} <= names
        assert json.loads(z.read("app/version.json"))["version"] == "1.0.17"
        assert "TIMEOFF.md" not in names
        config = json.loads(z.read("updater/updater-config.json"))
        assert config["preservePaths"] == ["*"]
    with pytest.raises(FileExistsError):
        builder.assemble(app, updater, output, "0" * 40)


@pytest.mark.parametrize("private_path", ["个人数据/settings.json", "tokens.json", "_internal/API投稿2.0/config/settings.json"])
def test_runtime_data_in_dist_is_rejected(tmp_path, monkeypatch, private_path):
    app = tmp_path / "dist"
    private = app / private_path
    private.parent.mkdir(parents=True)
    private.write_text("{}")
    updater = tmp_path / "UpdateAgent.exe"
    updater.write_bytes(b"audited test fixture")
    monkeypatch.setattr(builder, "UPDATER_SHA256", hashlib.sha256(updater.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match="runtime"):
        builder.assemble(app, updater, tmp_path / "output", "0" * 40)


def test_placeholder_executable_cannot_claim_current_source(tmp_path):
    app = tmp_path / "dist"
    app.mkdir()
    (app / "上传投稿中心.exe").write_bytes(b"not a frozen executable")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=builder.ROOT, text=True).strip()
    with pytest.raises(ValueError, match="frozen"):
        builder.verify_frozen_source(app, commit)


def test_source_commit_must_be_current_head(tmp_path):
    with pytest.raises(ValueError, match="commit"):
        builder.verify_frozen_source(tmp_path, "0" * 40)
