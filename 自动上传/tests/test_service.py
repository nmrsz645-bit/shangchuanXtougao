from pathlib import Path

from video_feishu.config import RetryStore, Settings
from video_feishu.models import PreviewStatus, SourceRow
from video_feishu.service import TaskService, mark_uploaded_names


class FakeFeishu:
    def __init__(self):
        self.rows = {
            "A": SourceRow("A", "tag-a", "activity-a", "program-a"),
            "B": SourceRow("B", "tag-b", "activity-b", "program-b"),
        }
        self.appended = []
        self.append_calls = []
        self.fail = False

    def connect(self, settings, secret):
        return self.rows, "dest-token", "dest-sheet"

    def append(self, token, sheet, rows):
        if self.fail:
            raise RuntimeError("boom")
        self.append_calls.append(rows)
        self.appended.extend(rows)


def test_preview_and_execute_moves_unmatched_but_writes_only_match(tmp_path):
    source = tmp_path / "source"; source.mkdir()
    destination = tmp_path / "destination"; destination.mkdir()
    (source / "batch" / "inner").mkdir(parents=True)
    (source / "batch" / "inner" / "A.mp4").write_bytes(b"a")
    (source / "batch" / "inner" / "C.mp4").write_bytes(b"b")
    feishu = FakeFeishu()
    service = TaskService(feishu, RetryStore(tmp_path / "retry.json"))
    settings = Settings("id", "copy", "paste", str(source), str(destination))
    preview = service.preview(settings, "secret")
    assert [i.status for i in preview.items] == [PreviewStatus.READY, PreviewStatus.UNMATCHED]
    result = service.execute(preview, preview.token)
    assert (destination / "A.mp4").exists() and (destination / "C.mp4").exists()
    assert feishu.appended == [["A", "tag-a", "activity-a", "program-a"]]
    assert len(result) == 2


def test_failed_write_is_durable_and_retry_does_not_move_again(tmp_path):
    source = tmp_path / "source"; source.mkdir()
    destination = tmp_path / "destination"; destination.mkdir()
    (source / "batch" / "inner").mkdir(parents=True)
    (source / "batch" / "inner" / "A.mp4").write_bytes(b"a")
    feishu = FakeFeishu(); feishu.fail = True
    retries = RetryStore(tmp_path / "retry.json")
    service = TaskService(feishu, retries)
    settings = Settings("id", "copy", "paste", str(source), str(destination))
    preview = service.preview(settings, "secret")
    service.execute(preview, preview.token)
    assert retries.load() == [["A", "tag-a", "activity-a", "program-a"]]
    feishu.fail = False
    service.retry_failed_writes("dest-token", "dest-sheet")
    assert retries.load() == []
    assert (destination / "A.mp4").exists()


def test_execute_removes_empty_nested_folder_but_keeps_source_root(tmp_path):
    source = tmp_path / "source"; (source / "nested").mkdir(parents=True)
    destination = tmp_path / "destination"; destination.mkdir()
    (source / "nested" / "A.mp4").write_bytes(b"a")
    service = TaskService(FakeFeishu(), RetryStore(tmp_path / "retry.json"))
    settings = Settings("id", "copy", "paste", str(source), str(destination))
    preview = service.preview(settings, "secret")
    service.execute(preview, preview.token)
    assert source.exists()
    assert not (source / "nested").exists()


def test_preview_ignores_root_video_and_keeps_outer_folder_batches(tmp_path):
    source = tmp_path / "source"; source.mkdir()
    destination = tmp_path / "destination"; destination.mkdir()
    (source / "root.mp4").write_bytes(b"root")
    (source / "B" / "inner").mkdir(parents=True)
    (source / "B" / "inner" / "B.mp4").write_bytes(b"b")
    (source / "A" / "inner").mkdir(parents=True)
    (source / "A" / "inner" / "A.mp4").write_bytes(b"a")
    service = TaskService(FakeFeishu(), RetryStore(tmp_path / "retry.json"))
    preview = service.preview(Settings("id", "copy", "paste", str(source), str(destination)), "secret")

    assert [(item.outer_folder, item.source.name) for item in preview.items] == [("A", "A.mp4"), ("B", "B.mp4")]


def test_execute_appends_one_outer_folder_before_the_next(tmp_path):
    source = tmp_path / "source"; source.mkdir()
    destination = tmp_path / "destination"; destination.mkdir()
    (source / "A" / "inner").mkdir(parents=True)
    (source / "A" / "inner" / "A.mp4").write_bytes(b"a")
    (source / "B" / "inner").mkdir(parents=True)
    (source / "B" / "inner" / "B.mp4").write_bytes(b"b")
    feishu = FakeFeishu()
    service = TaskService(feishu, RetryStore(tmp_path / "retry.json"))
    preview = service.preview(Settings("id", "copy", "paste", str(source), str(destination)), "secret")

    service.execute(preview, preview.token)

    assert feishu.append_calls == [
        [["A", "tag-a", "activity-a", "program-a"]],
        [["B", "tag-b", "activity-b", "program-b"]],
    ]


def test_marks_last_matching_a_row_in_e_column():
    class Client:
        writes = []

        def authenticate(self, app_id, secret):
            pass

        def resolve_spreadsheet(self, url):
            return "token", "hint"

        def list_sheets(self, token):
            return [{"title": "Sheet1", "sheet_id": "sheet"}]

        def read_values(self, token, sheet):
            return [["书名"], ["A"], ["B"], ["A"]]

        def write_values(self, token, range_value, values):
            self.writes.append((range_value, values))

    client = Client()
    completed = mark_uploaded_names(Settings(paste_url="paste"), "secret", ["A", "missing"], client)

    assert completed == {"A"}
    assert client.writes == [("sheet!E4:E4", [["A"]])]
