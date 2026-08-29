from pathlib import Path

from video_feishu.models import PreviewItem, PreviewStatus, SourceRow


def test_preview_item_carries_exact_match_data():
    row = SourceRow("书A", "标签A", "活动A", "程序A")
    item = PreviewItem(
        Path("x/书A.mp4"),
        Path("y/书A.mp4"),
        "第一批",
        "书A",
        PreviewStatus.READY,
        row,
    )
    assert item.match_name == "书A"
    assert item.outer_folder == "第一批"
    assert item.source_row == row
