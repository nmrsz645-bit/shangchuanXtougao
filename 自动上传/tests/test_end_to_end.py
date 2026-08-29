from video_feishu.config import RetryStore, Settings
from video_feishu.models import MoveStatus, SourceRow, WriteStatus
from video_feishu.service import TaskService


class BatchFeishu:
    def __init__(self):
        self.rows = {
            "A": SourceRow("A", "tag-a", "activity-a", "program-a"),
            "B": SourceRow("B", "tag-b", "activity-b", "program-b"),
        }
        self.calls = []
        self.fail_first_append = True

    def connect(self, settings, secret):
        return self.rows, "destination-token", "sheet-id"

    def append(self, token, sheet, rows):
        self.calls.append(rows)
        if self.fail_first_append:
            self.fail_first_append = False
            raise RuntimeError("simulated first batch failure")


def test_complete_outer_folder_workflow(tmp_path):
    source = tmp_path / "source"; source.mkdir()
    destination = tmp_path / "destination"; destination.mkdir()
    retries = RetryStore(tmp_path / "retry.json")

    # Root video must remain untouched.
    (source / "root.mp4").write_bytes(b"root")

    # First batch: one matched, one unmatched, and one destination collision.
    (source / "A" / "inner").mkdir(parents=True)
    (source / "A" / "inner" / "A.mp4").write_bytes(b"a")
    (source / "A" / "inner" / "Unknown.mp4").write_bytes(b"unknown")
    (source / "A" / "inner" / "Collision.mp4").write_bytes(b"source")
    (destination / "Collision.mp4").write_bytes(b"existing")

    # Second batch has one matched video and must still run after batch A write failure.
    (source / "B" / "inner").mkdir(parents=True)
    (source / "B" / "inner" / "B.mp4").write_bytes(b"b")

    feishu = BatchFeishu()
    service = TaskService(feishu, retries)
    settings = Settings("id", "copy", "paste", str(source), str(destination))
    preview = service.preview(settings, "secret")

    assert [(item.outer_folder, item.source.name) for item in preview.items] == [
        ("A", "A.mp4"),
        ("A", "Collision.mp4"),
        ("A", "Unknown.mp4"),
        ("B", "B.mp4"),
    ]

    results = service.execute(preview, preview.token)

    assert (source / "root.mp4").exists()
    assert (destination / "A.mp4").exists()
    assert (destination / "Unknown.mp4").exists()
    assert (destination / "B.mp4").exists()
    assert (source / "A" / "inner" / "Collision.mp4").exists()
    assert not (source / "B").exists()
    assert retries.load() == [["A", "tag-a", "activity-a", "program-a"]]
    assert feishu.calls == [
        [["A", "tag-a", "activity-a", "program-a"]],
        [["B", "tag-b", "activity-b", "program-b"]],
    ]
    assert [result.move_status for result in results] == [
        MoveStatus.MOVED,
        MoveStatus.SKIPPED,
        MoveStatus.MOVED,
        MoveStatus.MOVED,
    ]
    assert [result.write_status for result in results] == [
        WriteStatus.FAILED,
        WriteStatus.NOT_REQUIRED,
        WriteStatus.NOT_REQUIRED,
        WriteStatus.WRITTEN,
    ]

    service.retry_failed_writes("destination-token", "sheet-id")

    assert retries.load() == []
    assert feishu.calls[-1] == [["A", "tag-a", "activity-a", "program-a"]]
