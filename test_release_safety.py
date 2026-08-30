import json
import tempfile
import zipfile
from pathlib import Path

import pytest

from release_safety import REQUIRED_APP_FILES, validate_manifest, validate_release_archive, validate_update_entrypoint


HASH = "a" * 64


def write_release_zip(path: Path, *, protected=False, omit=()):
    with zipfile.ZipFile(path, "w") as archive:
        for name in REQUIRED_APP_FILES:
            if name not in omit:
                content = json.dumps({"version": "1.0.2"}) if name == "version.json" else "program"
                archive.writestr(name, content)
        if protected:
            archive.writestr("个人数据/keep.txt", "must never be published")


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
                content = json.dumps({"version": "1.0.2"}) if name == "version.json" else "program"
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
        write_release_zip(archive, protected=True)
        with pytest.raises(ValueError, match="protected user data"):
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
            '@echo off\r\n"updater\\UpdateAgent.exe" --check "updater-config.json"\r\ncall "app\\Start-App.cmd"\r\n',
            encoding="utf-8",
        )
        validate_update_entrypoint(start)
