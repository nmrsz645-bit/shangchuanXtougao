"""Exercise the unchanged updater in a new synthetic installation only."""
from pathlib import Path
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import shutil
import subprocess
import threading
import urllib.request

HERE = Path(__file__).resolve().parent
PAYLOAD = HERE / "candidate-release" / "upload-payload-1.0.17"
OLD = Path(r"C:\LOCAL_RELEASE_CANDIDATES\shangchuan-tougao-1.0.16-cmd-encoding\package-root-clean-1.0.16")
TARGET = HERE / "isolated-upgrade-local-02"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    assert TARGET.resolve().is_relative_to(HERE.resolve())
    assert not TARGET.exists()
    shutil.copytree(OLD, TARGET)
    config_path = TARGET / "updater" / "updater-config.json"
    config = json.loads(config_path.read_text("utf-8-sig"))
    app = (config_path.parent / config["appRoot"]).resolve()
    assert app == TARGET / "app" and app.is_relative_to(HERE.resolve())
    markers = [
        "共享飞书设置.json", "个人数据/Chrome/Default/release-sentinel.txt",
        "个人数据/upload_jobs.json", "API投稿2.0/config/settings.json",
        "API投稿2.0/data/queue-sentinel.json", "API投稿2.0/logs/isolated.log",
        "自动上传/个人数据/ledger.json", "custom-sentinel.txt",
    ]
    hashes = {}
    for index, name in enumerate(markers):
        path = app / name
        path.parent.mkdir(parents=True, exist_ok=True)
        assert not path.exists()
        path.write_text(json.dumps({"synthetic_release_marker":index,"no_real_credentials":True}), "utf-8")
        hashes[name] = digest(path)
    manifest = json.loads((PAYLOAD / "latest.json").read_text("utf-8"))
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            if self.path.split("?", 1)[0] == "/manifest.json":
                content = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            elif self.path.split("?", 1)[0] == "/app.zip":
                self.send_response(200)
                self.send_header("Content-Length", str((PAYLOAD / "app.zip").stat().st_size))
                self.end_headers()
                with (PAYLOAD / "app.zip").open("rb") as stream:
                    shutil.copyfileobj(stream, self.wfile)
            else:
                self.send_error(404)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    manifest["url"] = base + "/app.zip"
    config["manifestUrl"] = base + "/manifest.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False), "utf-8")
    try:
        result = subprocess.run([str(TARGET / "updater" / "UpdateAgent.exe"), "--silent", "--check", r"updater\updater-config.json"],
                                cwd=TARGET, capture_output=True, text=True, timeout=180)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    version = json.loads((app / "version.json").read_text("utf-8-sig")).get("version")
    required = {key:digest(app / key) == expected.lower() for key, expected in manifest["files"].items()}
    kept = {name:(app / name).is_file() and digest(app / name) == expected for name, expected in hashes.items()}
    report = {"mode":"isolated-loopback-http-updater-test-no-business-gui", "target":str(TARGET),
              "exit_code":result.returncode,"version":version,"required_hashes_match":required,
              "synthetic_markers_preserved":kept,"requests":requests,
              "stdout":result.stdout,"stderr":result.stderr,
              "directories":[p.name for p in TARGET.iterdir() if p.is_dir()]}
    report["passed"] = result.returncode == 0 and version == "1.0.17" and all(required.values()) and all(kept.values())
    (HERE / "verification" / "isolated-upgrade-local.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),"utf-8")
    print(json.dumps(report,ensure_ascii=True),flush=True)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
