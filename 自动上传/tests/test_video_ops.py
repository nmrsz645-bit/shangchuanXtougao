import pytest

from video_feishu.video_ops import move_video, remove_empty_descendants, scan_video_batches, scan_videos, validate_roots


def test_scan_includes_root_nested_and_case_insensitive_extensions(tmp_path):
    (tmp_path / "A.MP4").write_bytes(b"a")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "B.mkv").write_bytes(b"b")
    (nested / "C.mpeg").write_bytes(b"c")
    (nested / "note.txt").write_text("x")
    assert [p.name for p in scan_videos(tmp_path)] == ["A.MP4", "B.mkv", "C.mpeg"]


def test_scan_ignores_processing_videos_until_editing_finishes(tmp_path):
    (tmp_path / "ready.mp4").write_bytes(b"video")
    (tmp_path / "editing.processing.mp4").write_bytes(b"video")
    (tmp_path / "render.mp4.processing").write_bytes(b"video")

    assert [path.name for path in scan_videos(tmp_path)] == ["ready.mp4"]


def test_move_refuses_collision(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"a")
    destination = tmp_path / "target"
    destination.mkdir()
    (destination / source.name).write_bytes(b"b")
    assert move_video(source, destination / source.name) is False
    assert source.exists()


def test_move_cuts_file_and_removes_source(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    destination = tmp_path / "target" / source.name
    destination.parent.mkdir()

    assert move_video(source, destination) is True
    assert not source.exists()
    assert destination.read_bytes() == b"video"


def test_cleanup_removes_only_empty_descendants(tmp_path):
    empty = tmp_path / "a" / "b"
    empty.mkdir(parents=True)
    kept = tmp_path / "kept"
    kept.mkdir()
    (kept / "note.txt").write_text("x")
    remove_empty_descendants(tmp_path)
    assert not (tmp_path / "a").exists()
    assert kept.exists() and tmp_path.exists()


def test_destination_inside_source_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        validate_roots(tmp_path, tmp_path / "out")


def test_scan_batches_ignores_root_videos_and_groups_by_outer_folder(tmp_path):
    (tmp_path / "root.mp4").write_bytes(b"x")
    (tmp_path / "B" / "two").mkdir(parents=True)
    (tmp_path / "B" / "two" / "b.mp4").write_bytes(b"x")
    (tmp_path / "A" / "z").mkdir(parents=True)
    (tmp_path / "A" / "z" / "z.mp4").write_bytes(b"x")
    (tmp_path / "A" / "a").mkdir()
    (tmp_path / "A" / "a" / "a.mp4").write_bytes(b"x")
    (tmp_path / "A" / "a" / "editing.processing.mp4").write_bytes(b"x")

    batches = scan_video_batches(tmp_path)

    assert [(name, [video.name for video in videos]) for name, videos in batches] == [
        ("A", ["a.mp4", "z.mp4"]),
        ("B", ["b.mp4"]),
    ]
