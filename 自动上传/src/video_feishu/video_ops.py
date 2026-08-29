from pathlib import Path
import shutil


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v", ".mpeg", ".mpg", ".ts", ".3gp"}
PROCESSING_SUFFIX = ".processing"


def is_ready_video(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS and not path.stem.lower().endswith(PROCESSING_SUFFIX)


def validate_roots(source: Path, destination: Path) -> tuple[Path, Path]:
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if not source.is_dir():
        raise ValueError("源文件夹不存在")
    if source == destination or source in destination.parents:
        raise ValueError("目标文件夹不能与源文件夹相同或位于源文件夹内部")
    destination.mkdir(parents=True, exist_ok=True)
    return source, destination


def scan_videos(source: Path) -> list[Path]:
    return sorted(
        (p for p in source.rglob("*") if is_ready_video(p)),
        key=lambda p: str(p).lower(),
    )


def scan_video_batches(source: Path) -> list[tuple[str, list[Path]]]:
    """Return videos grouped by root-level folder in deterministic path order."""
    batches: list[tuple[str, list[Path]]] = []
    outer_folders = sorted(
        (path for path in source.iterdir() if path.is_dir()),
        key=lambda path: path.name.lower(),
    )
    for outer in outer_folders:
        videos = sorted(
            (path for path in outer.rglob("*") if is_ready_video(path)),
            key=lambda path: str(path.relative_to(outer)).lower(),
        )
        if videos:
            batches.append((outer.name, videos))
    return batches


def move_video(source: Path, destination: Path) -> bool:
    if destination.exists():
        return False
    shutil.move(str(source), str(destination))
    return True


def remove_empty_descendants(source: Path) -> None:
    directories = sorted(
        (p for p in source.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    for directory in directories:
        if not any(directory.iterdir()):
            directory.rmdir()
