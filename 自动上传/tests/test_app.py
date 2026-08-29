from pathlib import Path
import runpy

from video_feishu.app import AppState, preview_row_values
from video_feishu.models import PreviewItem, PreviewStatus, SourceRow
import video_feishu.app


def test_execute_is_disabled_until_preview_and_invalidated_by_setting_change():
    state = AppState()
    assert state.can_execute is False
    state.preview_token = "token"
    assert state.can_execute is True
    state.invalidate_preview()
    assert state.can_execute is False


def test_packaged_entrypoint_can_run_as_top_level_script(monkeypatch):
    called = []
    monkeypatch.setattr(video_feishu.app, "main", lambda: called.append(True))
    runpy.run_path(str(Path(video_feishu.app.__file__).with_name("__main__.py")), run_name="__main__")
    assert called == [True]


def test_preview_row_exposes_outer_folder_name():
    item = PreviewItem(
        Path("source/第一批/inner/A.mp4"),
        Path("target/A.mp4"),
        "第一批",
        "A",
        PreviewStatus.READY,
        SourceRow("A", "tag", "page", "link"),
    )

    assert preview_row_values(item)[1] == "第一批"
