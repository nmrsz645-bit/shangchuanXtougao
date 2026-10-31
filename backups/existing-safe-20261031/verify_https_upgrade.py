"""Run only the public updater against an isolated synthetic old installation."""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
OLD_ZIP = Path(r"C:\LOCAL_RELEASE_CANDIDATES\shangchuan-tougao-1.0.16-cmd-encoding\upload-payload-1.0.16\shang-chuan-tou-gao-zhong-xin-1.0.16.zip")
OLD_HASH = "ccffea6bf86cca0760ee222b36e9c5acd59f5bc2aebab838cd83c82e22b9f3b9"
PAYLOAD = HERE / "candidate-release" / "upload-payload-1.0.17"
NEW_APP = HERE / "candidate-release" / "package-root-clean-1.0.17" / "app"
CANDIDATE_URL = "https://luotuoruanjiangengx.oss-cn-beijing.aliyuncs.com/updates/shang-chuan-tou-gao-zhong-xin/1.0.17/latest.json"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", choices=["candidate", "production"], default="candidate")
    args = parser.parse_args()
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d-%H%M%S-%f")
    target = HERE / f"isolated-upgrade-https-{args.channel}-{stamp}"
    assert target.resolve().is_relative_to(HERE.resolve()) and not target.exists()
    assert digest(OLD_ZIP) == OLD_HASH
    with zipfile.ZipFile(OLD_ZIP) as archive:
        assert all(not Path(n).is_absolute() and ".." not in Path(n).parts and ":" not in n for n in archive.namelist())
        archive.extractall(target)
    config_path = target / "updater" / "updater-config.json"
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes.decode("utf-8-sig"))
    app = (config_path.parent / config["appRoot"]).resolve()
    assert app == target / "app" and app.is_relative_to(HERE.resolve())
    assert json.loads((app / "version.json").read_text("utf-8-sig"))["version"] == "1.0.16"
    marker_names = ["共享飞书设置.json", "个人数据/Chrome/Default/release-sentinel.txt",
                    "个人数据/upload_jobs.json", "API投稿2.0/config/settings.json",
                    "API投稿2.0/data/queue-sentinel.json", "API投稿2.0/logs/isolated.log",
                    "自动上传/个人数据/ledger.json", "custom-sentinel.txt"]
    marker_hashes = {}
    for index, name in enumerate(marker_names):
        path = app / name
        assert not path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"isolated_synthetic_marker":index,"no_real_credentials":True}), "utf-8")
        marker_hashes[name] = digest(path)
    if args.channel == "candidate":
        config["manifestUrl"] = CANDIDATE_URL
        config_path.write_text(json.dumps(config, ensure_ascii=False), "utf-8")
    else:
        assert config_path.read_bytes() == config_bytes
        assert config["manifestUrl"].endswith("/1.0.0/latest.json")
    assert config["manifestUrl"].startswith("https://")
    with urllib.request.urlopen(config["manifestUrl"], timeout=30) as response:
        public_manifest_bytes = response.read()
    assert public_manifest_bytes == (PAYLOAD / "latest.json").read_bytes()
    manifest = json.loads(public_manifest_bytes)
    updater_hash = digest(target / "updater" / "UpdateAgent.exe")
    print(json.dumps({"stage":"running_updater","channel":args.channel,"target":str(target),"manifest":config["manifestUrl"]},ensure_ascii=True),flush=True)
    try:
        run = subprocess.run([str(target / "updater" / "UpdateAgent.exe"), "--silent", "--check", r"updater\updater-config.json"],
                             cwd=target, capture_output=True, text=True, timeout=180)
        exit_code, stdout, stderr = run.returncode, run.stdout, run.stderr
    except subprocess.TimeoutExpired as exc:
        exit_code, stdout, stderr = None, str(exc.stdout or ""), "updater timed out"
    required = {name:(app / name).is_file() and digest(app / name) == expected.lower() for name, expected in manifest["files"].items()}
    preserved = {name:(app / name).is_file() and digest(app / name) == expected for name, expected in marker_hashes.items()}
    all_files = [path for path in NEW_APP.rglob("*") if path.is_file()]
    mismatches = [path.relative_to(NEW_APP).as_posix() for path in all_files
                  if not (app / path.relative_to(NEW_APP)).is_file() or digest(app / path.relative_to(NEW_APP)) != digest(path)]
    version = json.loads((app / "version.json").read_text("utf-8-sig")).get("version")
    report = {"time":stamp,"channel":args.channel,"manifest_url":config["manifestUrl"],"target":str(target),
              "exit_code":exit_code,"version":version,"required_file_hashes":required,
              "compared_bundle_files":len(all_files),"bundle_mismatches":mismatches,
              "synthetic_markers_preserved":preserved,"updater_unchanged":digest(target / "updater" / "UpdateAgent.exe") == updater_hash,
              "production_config_unchanged":config_path.read_bytes() == config_bytes if args.channel == "production" else None,
              "directories":[p.name for p in target.iterdir() if p.is_dir()],"stdout":stdout,"stderr":stderr,
              "business_gui_launched":False}
    report["passed"] = exit_code == 0 and version == "1.0.17" and all(required.values()) and all(preserved.values()) and not mismatches and report["updater_unchanged"]
    if args.channel == "production":
        report["passed"] = report["passed"] and report["production_config_unchanged"]
    output = HERE / "verification" / f"https-upgrade-{args.channel}-{stamp}.json"
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),"utf-8")
    print(json.dumps(report,ensure_ascii=True),flush=True)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
