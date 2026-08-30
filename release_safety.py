"""Offline release-package checks for 上传 + 投稿中心.

The checks are deliberately limited to files produced for release.  They do
not inspect an installed program directory, where the same paths may contain
the user's credentials and runtime data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath


SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
REQUIRED_APP_FILES = (
    "version.json",
    "上传投稿中心.exe",
    "Start-App.cmd",
    "_internal/python313.dll",
)
PROTECTED_PATHS = (
    "共享飞书设置.json",
    "个人数据/",
    "API投稿2.0/config/",
    "API投稿2.0/data/",
    "API投稿2.0/logs/",
    "tokens/",
    "Chrome/",
    "queue/",
    "logs/",
    "state.db",
    "state.db-wal",
    "state.db-shm",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _normalise_archive_name(name: str) -> str:
    path = PurePosixPath(name.replace("\\", "/"))
    parts = path.parts
    if parts and parts[0] == "app":
        parts = parts[1:]
    return "/".join(parts)


def _is_protected(name: str) -> bool:
    normalised = _normalise_archive_name(name).lower()
    return any(
        normalised == protected.rstrip("/").lower()
        or normalised.startswith(protected.lower())
        for protected in PROTECTED_PATHS
    )


def validate_release_archive(archive_path: Path, expected_version: str | None = None) -> None:
    """Reject incomplete archives and archives containing user runtime data."""
    with zipfile.ZipFile(archive_path) as archive:
        entries = {
            _normalise_archive_name(info.filename): info.filename
            for info in archive.infolist()
            if not info.is_dir()
        }
        missing = sorted(set(REQUIRED_APP_FILES) - set(entries))
        if missing:
            raise ValueError(f"release archive is missing required files: {', '.join(missing)}")

        protected = sorted(name for name in entries if _is_protected(name))
        if protected:
            raise ValueError(f"release archive contains protected user data: {', '.join(protected)}")

        version_data = json.loads(archive.read(entries["version.json"]))
        version = version_data.get("version")
        if not isinstance(version, str) or not version:
            raise ValueError("release archive version.json has no version")
        if expected_version and version != expected_version:
            raise ValueError(f"archive version {version} does not match expected {expected_version}")


def validate_manifest(manifest_path: Path, required_files: tuple[str, ...] = REQUIRED_APP_FILES) -> None:
    """Check that a manifest is usable by old clients before it is activated."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if not isinstance(manifest.get("version"), str) or not manifest["version"]:
        raise ValueError("manifest has no version")
    if not isinstance(manifest.get("url"), str) or not manifest["url"].startswith("https://"):
        raise ValueError("manifest URL must use HTTPS")
    if not isinstance(manifest.get("sha256"), str) or not SHA256_RE.fullmatch(manifest["sha256"]):
        raise ValueError("manifest SHA-256 is invalid")

    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("manifest has no file hash list")
    missing = sorted(path for path in required_files if path not in files)
    if missing:
        raise ValueError(f"manifest is missing required files: {', '.join(missing)}")
    invalid = sorted(path for path in required_files if not isinstance(files[path], str) or not SHA256_RE.fullmatch(files[path]))
    if invalid:
        raise ValueError(f"manifest has invalid file hashes: {', '.join(invalid)}")


def validate_update_entrypoint(start_script: Path) -> None:
    """Ensure the root launcher can invoke the updater before it starts the app."""
    content = start_script.read_text(encoding="utf-8-sig", errors="replace").lower()
    required_fragments = ("updater\\updateagent.exe", "updater-config.json", "app\\start-app.cmd")
    missing = [fragment for fragment in required_fragments if fragment not in content]
    if missing:
        raise ValueError(f"root Start.cmd has no update entrypoint: {', '.join(missing)}")


def validate_release(app_zip: Path, manifest: Path, start_script: Path, expected_version: str | None) -> None:
    validate_release_archive(app_zip, expected_version)
    validate_manifest(manifest)
    validate_update_entrypoint(start_script)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a clean upload-posting release candidate offline.")
    parser.add_argument("--app-zip", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--start-script", type=Path, required=True)
    parser.add_argument("--version")
    args = parser.parse_args()
    validate_release(args.app_zip, args.manifest, args.start_script, args.version)
    print(f"PASS {args.app_zip.name} sha256={sha256_file(args.app_zip)}")


if __name__ == "__main__":
    main()
