"""Build a clean, immutable Windows release candidate from an audited base package."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from release_safety import REQUIRED_APP_FILES, validate_release


OSS_BASE = "https://luotuoruanjiangengx.oss-cn-beijing.aliyuncs.com"
APP_ID = "shang-chuan-tou-gao-zhong-xin"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def zip_directory(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source).as_posix())


def build(base_root: Path, destination: Path, version: str, launcher: Path, app_launcher: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing candidate: {destination}")
    if not base_root.is_dir():
        raise FileNotFoundError(f"base package root not found: {base_root}")

    package_root = destination / f"package-root-clean-{version}"
    payload = destination / f"upload-payload-{version}"
    shutil.copytree(base_root, package_root)
    payload.mkdir(parents=True)
    shutil.copy2(launcher, package_root / "Start.cmd")
    shutil.copy2(app_launcher, package_root / "app" / "Start-App.cmd")
    (package_root / "app" / "version.json").write_text(
        json.dumps({"version": version}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    app_zip = payload / "app.zip"
    zip_directory(package_root / "app", app_zip)
    app_hash = sha256(app_zip)
    files = {name: sha256(package_root / "app" / name) for name in REQUIRED_APP_FILES}
    manifest = {
        "version": version,
        "url": f"{OSS_BASE}/updates/{APP_ID}/{version}/app.zip",
        "sha256": app_hash,
        "notes": f"投稿中心 {version}：修复 Windows CMD 对中文启动文件名的编码误读。",
        "files": files,
    }
    (payload / "latest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (payload / "latest.js").write_text(
        "window.SHANG_CHUAN_TOU_GAO_ZHONG_XIN_LATEST = Object.freeze({\n"
        f'  version: "{version}",\n'
        f'  fullPackageUrl: "{OSS_BASE}/packages/{APP_ID}-{version}.zip"\n'
        "});\n",
        encoding="utf-8",
    )
    full_zip = payload / f"{APP_ID}-{version}.zip"
    zip_directory(package_root, full_zip)
    validate_release(app_zip, payload / "latest.json", package_root / "Start.cmd", version)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a clean upload-posting release candidate.")
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--launcher", type=Path, default=Path(__file__).with_name("release") / "Start.cmd")
    parser.add_argument("--app-launcher", type=Path, default=Path(__file__).with_name("API投稿2.0") / "Start-App.cmd")
    args = parser.parse_args()
    build(args.base_root, args.destination, args.version, args.launcher, args.app_launcher)
    print(f"PASS {args.destination}")


if __name__ == "__main__":
    main()
