"""Assemble this release solely from fresh build output and a verified updater."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import zipfile

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent
sys.path.insert(0, str(SOURCE))
from build_release_candidate import build
from release_safety import validate_release_archive, validate_manifest, sha256_file

VERSION = "1.0.17"
OLD_RELEASE = Path(r"C:\LOCAL_RELEASE_CANDIDATES\shangchuan-tougao-1.0.16-cmd-encoding")
OLD_ROOT = OLD_RELEASE / "package-root-clean-1.0.16"
OLD_ZIP = OLD_RELEASE / "upload-payload-1.0.16" / "shang-chuan-tou-gao-zhong-xin-1.0.16.zip"
OLD_HASH = "ccffea6bf86cca0760ee222b36e9c5acd59f5bc2aebab838cd83c82e22b9f3b9"


def main():
    assert sha256_file(OLD_ZIP).lower() == OLD_HASH, "old clean package hash mismatch"
    new_app = HERE / "dist" / "上传投稿中心"
    assert (new_app / "上传投稿中心.exe").is_file()
    with zipfile.ZipFile(OLD_ZIP) as old_archive:
        updater_files = [p for p in (OLD_ROOT / "updater").rglob("*") if p.is_file()]
        assert updater_files
        for path in updater_files:
            relative = path.relative_to(OLD_ROOT).as_posix()
            assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(old_archive.read(relative)).digest(), relative
    staging = HERE / "staging-base"
    if "--audit-only" not in sys.argv:
        assert not staging.exists()
        assert not (HERE / "candidate-release").exists()
        staging.mkdir()
        shutil.copytree(new_app, staging / "app")
        shutil.copytree(OLD_ROOT / "updater", staging / "updater")
        shutil.copy2(SOURCE / "release" / "Start.cmd", staging / "Start.cmd")
        build(staging, HERE / "candidate-release", VERSION,
              SOURCE / "release" / "Start.cmd", SOURCE / "API投稿2.0" / "Start-App.cmd")
    payload = HERE / "candidate-release" / f"upload-payload-{VERSION}"
    manifest_path = payload / "latest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    if "--audit-only" not in sys.argv:
        manifest["notes"] = "修复视频上传完成状态识别；仅IAA弹窗出现时，在零勾选状态下自动确认并等待关闭；修复改名重复素材的成功核验及发布版版本号显示。"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", "utf-8")
    manifest = validate_manifest(manifest_path)
    expected_app = {p.relative_to(new_app).as_posix() for p in new_app.rglob("*") if p.is_file()} | {"version.json", "Start-App.cmd"}
    report = {"version":VERSION,"old_baseline_sha256":OLD_HASH,"new_source_app_files":len(expected_app),"archives":{}}
    for name in ("app.zip", f"shang-chuan-tou-gao-zhong-xin-{VERSION}.zip"):
        path = payload / name
        validate_release_archive(path, VERSION)
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            entries = [info.filename for info in archive.infolist() if not info.is_dir()]
            assert len(entries) == len(set(entries)), "duplicate archive entries"
            assert all(not n.startswith(("/", "\\")) and ".." not in Path(n).parts and ":" not in n for n in entries)
            if name == "app.zip":
                assert set(entries) == expected_app
                for key, digest in manifest["files"].items():
                    assert hashlib.sha256(archive.read(key)).hexdigest() == digest.lower(), key
            else:
                expected_full = {"app/"+n for n in expected_app} | {"Start.cmd"} | {p.relative_to(staging).as_posix() for p in (staging/"updater").rglob("*") if p.is_file()}
                assert set(entries) == expected_full
            # Playwright's shipped browser icons are vendor files already in
            # the exact fresh-build whitelist; they are not user/test images.
            assert not any(n.lower().endswith((".mp4", ".webm", ".jpg", ".png", ".jsonl"))
                           and not n.removeprefix("app/").startswith("_internal/playwright/") for n in entries)
            assert not any("验收-" in n or "候选发布-" in n or "个人数据" in n or "共享飞书设置" in n for n in entries)
        report["archives"][name] = {"bytes":path.stat().st_size,"sha256":sha256_file(path).lower(),"files":len(entries)}
    assert report["archives"]["app.zip"]["sha256"] == manifest["sha256"].lower()
    (HERE / "verification").mkdir(exist_ok=True)
    (HERE / "verification" / "package-audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),"utf-8")
    print(json.dumps(report,ensure_ascii=True),flush=True)


if __name__ == "__main__":
    main()
