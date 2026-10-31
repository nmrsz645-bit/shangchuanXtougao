"""Assemble a fresh PyInstaller build; never reads a user's installation."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import marshal
from pathlib import Path
import re
import shutil
import subprocess
import types
import zipfile

from release_safety import REQUIRED_APP_FILES, validate_release_archive, validate_update_entrypoint

ROOT = Path(__file__).resolve().parents[1]
UPDATER_SHA256 = "68721ebefcdebbe7b4133424d9e432bcfa0372f7a015ecf54d5aeeb5a6493316"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def zip_tree(root: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "x", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(root).as_posix())


def code_signature(value):
    if isinstance(value, types.CodeType):
        fields = ("co_argcount", "co_posonlyargcount", "co_kwonlyargcount", "co_nlocals",
                  "co_stacksize", "co_flags", "co_code", "co_consts", "co_names",
                  "co_varnames", "co_name", "co_qualname", "co_firstlineno",
                  "co_linetable", "co_exceptiontable", "co_freevars", "co_cellvars")
        return tuple((key, code_signature(getattr(value, key))) for key in fields)
    if isinstance(value, tuple):
        return tuple(code_signature(item) for item in value)
    return value


def verify_frozen_source(app_dist: Path, source_commit: str) -> None:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if source_commit != head:
        raise ValueError("source commit does not match current HEAD")
    from PyInstaller.archive.readers import CArchiveReader
    try:
        archive = CArchiveReader(str(app_dist / "上传投稿中心.exe"))
        pyz = archive.open_embedded_archive("PYZ.pyz")
        entry = marshal.loads(archive.extract("投稿中心"))
    except Exception as exc:
        raise ValueError("unverified frozen executable") from exc
    modules = {"entry": (ROOT / "投稿中心.py", entry)}
    for name in pyz.toc:
        source = None
        for prefix, folder in (("video_feishu", ROOT / "自动上传/src/video_feishu"),
                               ("desktop_posting", ROOT / "API投稿2.0/app/desktop_posting")):
            if name == prefix:
                source = folder / "__init__.py"
            elif name.startswith(prefix + "."):
                source = folder.joinpath(*name[len(prefix) + 1:].split(".")).with_suffix(".py")
            if source is not None:
                break
        if name in ("shared_feishu", "center_startup", "daily_restart"):
            source = ROOT / (name + ".py")
        if source is not None:
            if not source.is_file():
                source = source.with_suffix("") / "__init__.py"
            modules[name] = (source, pyz.extract(name))
    required = {"entry", "video_feishu.uploader", "video_feishu.config", "desktop_posting.desktop_app", "shared_feishu"}
    if not required <= modules.keys():
        raise ValueError("frozen executable is missing product modules")
    for name, (source, code) in modules.items():
        relative = source.relative_to(ROOT).as_posix()
        committed = subprocess.check_output(["git", "show", f"{source_commit}:{relative}"], cwd=ROOT)
        if committed != source.read_bytes():
            # Git's Windows checkout may translate LF to CRLF, without changing code.
            if committed.replace(b"\r\n", b"\n") != source.read_bytes().replace(b"\r\n", b"\n"):
                raise ValueError(f"uncommitted product source: {relative}")
        compiled = compile(committed, str(source), "exec", dont_inherit=True, optimize=0)
        if code_signature(code) != code_signature(compiled):
            raise ValueError(f"frozen code does not match source commit: {name}")
    toc = app_dist.parent.parent / "build" / "上传投稿中心" / "COLLECT-00.toc"
    entries = ast.literal_eval(toc.read_text("utf-8"))[0]
    expected = {}
    for name, source, kind in entries:
        relative = name if kind == "EXECUTABLE" else "_internal/" + name
        relative = relative.replace("\\", "/")
        if ".." in Path(relative).parts or Path(relative).is_absolute():
            raise ValueError("unsafe frozen file manifest")
        expected[relative] = sha256(Path(source))
    actual = {p.relative_to(app_dist).as_posix(): sha256(p) for p in app_dist.rglob("*") if p.is_file()}
    if actual != expected:
        raise ValueError("fresh frozen file manifest mismatch")


def assemble(app_dist: Path, updater: Path, destination: Path, source_commit: str) -> Path:
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite: {destination}")
    if sha256(updater) != UPDATER_SHA256:
        raise ValueError("updater SHA-256 does not match the audited legacy dependency")
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("source commit must be a full Git SHA")
    protected = {"个人数据", "chrome", "共享飞书设置.json", "state.db", "state.db-wal", "state.db-shm",
                 "cookies", "tokens.json", "settings.json", ".env"}
    for path in app_dist.rglob("*"):
        parts = {part.casefold() for part in path.relative_to(app_dist).parts}
        if path.is_symlink() or protected.intersection(parts) or any(p.startswith(".env.") for p in parts):
            raise ValueError("runtime data or symlink in fresh dist")
    verify_frozen_source(app_dist, source_commit)
    version = json.loads((ROOT / "API投稿2.0" / "version.json").read_text("utf-8"))["version"]
    package = destination / "package"
    app = package / "app"
    shutil.copytree(app_dist, app)
    shutil.copy2(ROOT / "API投稿2.0" / "Start-App.cmd", app / "Start-App.cmd")
    shutil.copy2(ROOT / "API投稿2.0" / "version.json", app / "version.json")
    shutil.copy2(ROOT / "release" / "Start.cmd", package / "Start.cmd")
    validate_update_entrypoint(package / "Start.cmd")
    for name in ("README.md", "HANDOFF.md"):
        shutil.copy2(ROOT / name, package / name)
    shutil.copytree(ROOT / "examples", package / "examples")
    (package / "updater").mkdir()
    shutil.copy2(updater, package / "updater" / "UpdateAgent.exe")
    config = {
        "appId": "shang-chuan-tou-gao-zhong-xin",
        "manifestUrl": "https://luotuoruanjiangengx.oss-cn-beijing.aliyuncs.com/updates/shang-chuan-tou-gao-zhong-xin/1.0.0/latest.json",
        "appRoot": "..\\app", "versionFile": "version.json", "preservePaths": ["*"],
        "requiredFiles": [x.replace("/", "\\") for x in REQUIRED_APP_FILES],
    }
    (package / "updater" / "updater-config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), "utf-8")
    info = {
        "productVersion": version, "distribution": "GitHub maintenance edition",
        "sourceCommit": source_commit, "legacyUpdaterSha256": UPDATER_SHA256,
        "requiredFileSha256": {name: sha256(app / name) for name in REQUIRED_APP_FILES},
        "productionOssChanged": False,
    }
    (package / "BUILD-INFO.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), "utf-8")
    app_zip = destination / "app-audit-only.zip"
    zip_tree(app, app_zip)
    validate_release_archive(app_zip, version)
    full = destination / f"shang-chuan-tou-gao-zhong-xin-{version}-github-windows-x64.zip"
    zip_tree(package, full)
    return full


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-dist", type=Path, required=True)
    parser.add_argument("--updater", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    print(assemble(args.app_dist, args.updater, args.destination, args.source_commit))


if __name__ == "__main__":
    main()
