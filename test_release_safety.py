import json
import tempfile
import zipfile
from pathlib import Path

import pytest

from release_safety import REQUIRED_APP_FILES, sha256_file, validate_manifest, validate_release, validate_release_archive, validate_update_entrypoint


HASH = "a" * 64


def write_release_zip(path: Path, *, protected_path="", omit=(), launcher='@echo off\r\nfor %%F in ("%~dp0*.exe") do (\r\n  start "" "%%~fF"\r\n  exit /b 0\r\n)\r\nexit /b 1\r\n'):
    with zipfile.ZipFile(path, "w") as archive:
        for name in REQUIRED_APP_FILES:
            if name not in omit:
                if name == "version.json":
                    content = json.dumps({"version": "1.0.2"})
                elif name == "Start-App.cmd":
                    content = launcher
                else:
                    content = "program"
                archive.writestr(name, content)
        if protected_path:
            archive.writestr(protected_path, "must never be published")


def write_manifest(path: Path, *, omit=()):
    files = {name: HASH for name in REQUIRED_APP_FILES if name not in omit}
    path.write_text(json.dumps({"version": "1.0.2", "url": "https://example.test/app.zip", "sha256": HASH, "files": files}), encoding="utf-8")


def test_clean_release_archive_is_accepted():
    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / "app.zip"
        write_release_zip(archive)
        validate_release_archive(archive, "1.0.2")


def test_full_package_with_app_prefix_is_accepted():
    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / "full-package.zip"
        with zipfile.ZipFile(archive, "w") as package:
            for name in REQUIRED_APP_FILES:
                if name == "version.json":
                    content = json.dumps({"version": "1.0.2"})
                elif name == "Start-App.cmd":
                    content = '@echo off\r\nfor %%F in ("%~dp0*.exe") do (\r\n  start "" "%%~fF"\r\n  exit /b 0\r\n)\r\nexit /b 1\r\n'
                else:
                    content = "program"
                package.writestr(f"app/{name}", content)
        validate_release_archive(archive, "1.0.2")


def test_release_archive_rejects_missing_version_file():
    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / "app.zip"
        write_release_zip(archive, omit=("version.json",))
        with pytest.raises(ValueError, match="version.json"):
            validate_release_archive(archive)


def test_release_archive_rejects_user_data():
    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / "app.zip"
        write_release_zip(archive, protected_path="自动上传/个人数据/Chrome/Cookies")
        with pytest.raises(ValueError, match="protected user data"):
            validate_release_archive(archive)


def test_release_archive_rejects_legacy_api_launcher():
    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / "app.zip"
        write_release_zip(archive, launcher='@echo off\r\nstart "" "%~dp0API_Posting_2.exe"\r\n')
        with pytest.raises(ValueError, match="portable executable launcher"):
            validate_release_archive(archive)

def test_rejects_non_ascii_cmd_launcher():
    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / "app.zip"
        write_release_zip(archive, launcher='@echo off\r\nstart "" "%~dp0上传投稿中心.exe"\r\n')
        with pytest.raises(ValueError, match="ASCII only"):
            validate_release_archive(archive)


def test_manifest_rejects_missing_required_file_hash():
    with tempfile.TemporaryDirectory() as temp:
        manifest = Path(temp) / "latest.json"
        write_manifest(manifest, omit=("Start-App.cmd",))
        with pytest.raises(ValueError, match="Start-App.cmd"):
            validate_manifest(manifest)


def test_root_start_script_must_offer_the_update_entrypoint():
    with tempfile.TemporaryDirectory() as temp:
        start = Path(temp) / "Start.cmd"
        start.write_text('@echo off\r\ncall "app\\Start-App.cmd"\r\n', encoding="utf-8")
        with pytest.raises(ValueError, match="update entrypoint"):
            validate_update_entrypoint(start)

        start.write_text(
            '@echo off\r\nsetlocal\r\nset "ROOT=%~dp0"\r\npushd "%ROOT%" || exit /b 1\r\n'
            'if exist "updater\\UpdateAgent.exe" "updater\\UpdateAgent.exe" --silent --check "updater\\updater-config.json"\r\n'
            'if exist "app\\Start-App.cmd" call "app\\Start-App.cmd"\r\npopd\r\nendlocal\r\n',
            encoding="utf-8",
        )
        validate_update_entrypoint(start)

        start.write_text(
            '@echo off\r\nsetlocal\r\nset "ROOT=%~dp0"\r\npushd "%ROOT%"\r\n'
            'if exist "%ROOT%updater\\UpdateAgent.exe" "%ROOT%updater\\UpdateAgent.exe" --silent --check "%ROOT%updater\\updater-config.json"\r\n'
            'if exist "%ROOT%app\\Start-App.cmd" call "%ROOT%app\\Start-App.cmd"\r\npopd\r\nendlocal\r\n',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="safe update entrypoint"):
            validate_update_entrypoint(start)


def test_full_release_requires_manifest_hash_for_the_same_archive():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        archive = root / "app.zip"
        manifest = root / "latest.json"
        start = root / "Start.cmd"
        write_release_zip(archive)
        write_manifest(manifest)
        start.write_text(
            '@echo off\r\nsetlocal\r\nset "ROOT=%~dp0"\r\npushd "%ROOT%" || exit /b 1\r\n'
            'if exist "updater\\UpdateAgent.exe" "updater\\UpdateAgent.exe" --silent --check "updater\\updater-config.json"\r\n'
            'if exist "app\\Start-App.cmd" call "app\\Start-App.cmd"\r\npopd\r\nendlocal\r\n',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="does not match release archive"):
            validate_release(archive, manifest, start, "1.0.2")

        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["sha256"] = sha256_file(archive)
        manifest.write_text(json.dumps(data), encoding="utf-8")
        validate_release(archive, manifest, start, "1.0.2")
