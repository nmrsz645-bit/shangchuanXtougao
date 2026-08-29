import os
from pathlib import Path
import shutil
import sys


STARTUP_FILE = "VideoFeishuTool.cmd"


def startup_dir() -> Path:
    roaming = os.environ.get("APPDATA")
    if roaming:
        return Path(roaming) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def startup_file() -> Path:
    return startup_dir() / STARTUP_FILE


def current_target() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    return Path(sys.argv[0]).resolve()


def cleanup_old_versions(target: Path | None = None) -> None:
    app_dir = (target or current_target()).resolve().parent
    old_dirs = [app_dir.with_name(app_dir.name + ".previous")]
    old_dirs.extend(app_dir.parent.glob(app_dir.name + ".previous.archived-*"))
    for old_dir in old_dirs:
        if old_dir.is_dir():
            shutil.rmtree(old_dir, ignore_errors=True)


def is_auto_start_enabled() -> bool:
    return startup_file().exists()


def set_auto_start(enabled: bool, target: Path | None = None) -> None:
    path = startup_file()
    if not enabled:
        path.unlink(missing_ok=True)
        return
    target = target or current_target()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "@echo off\r\n"
        ":restart\r\n"
        'if not exist "%~f0" exit /b\r\n'
        f'start /wait "" "{target}"\r\n'
        'if not exist "%~f0" exit /b\r\n'
        "timeout /t 60 /nobreak >nul\r\n"
        "goto restart\r\n",
        "utf-8",
    )
