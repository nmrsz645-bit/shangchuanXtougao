import os
from pathlib import Path


STARTUP_FILE = "UploadPostingCenter.vbs"


def startup_file() -> Path:
    roaming = os.environ.get("APPDATA")
    base = Path(roaming) if roaming else Path.home() / "AppData" / "Roaming"
    return base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / STARTUP_FILE


def is_enabled(path: Path | None = None) -> bool:
    return (path or startup_file()).exists()


def set_enabled(enabled: bool, launcher: str, runner: Path | None = None, path: Path | None = None) -> None:
    path = path or startup_file()
    if not enabled:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    command = f'"{launcher}"' + (f' "{runner}"' if runner else "")
    path.write_text(
        "Set shell = CreateObject(\"WScript.Shell\")\r\n"
        "Do\r\n"
        f'  shell.Run "{command.replace(chr(34), chr(34) * 2)}", 0, True\r\n'
        "  WScript.Sleep 60000\r\n"
        "Loop\r\n",
        encoding="utf-8-sig",
    )
