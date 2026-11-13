from pathlib import Path

import pytest

from video_feishu.tracking import DailyStatsStore, FeishuWriteQueue, TrackingReadError


def test_daily_stats_deduplicates_and_resets_next_day(tmp_path):
    current = ["2026-07-22"]
    store = DailyStatsStore(tmp_path / "stats.json", lambda: current[0])
    video = tmp_path / "A.mp4"
    video.write_bytes(b"video")

    store.record("success", [video, video])
    store.record("failure", [video])
    assert store.snapshot() == {"date": "2026-07-22", "success": 1, "failure": 1}

    current[0] = "2026-07-23"
    assert store.snapshot() == {"date": "2026-07-23", "success": 0, "failure": 0}
    current[0] = "2026-07-22"
    assert store.snapshot() == {"date": "2026-07-22", "success": 1, "failure": 1}


@pytest.mark.parametrize("queue_file", [False, True], ids=["stats", "queue"])
def test_tracking_write_preserves_data_after_a_read_error(tmp_path, monkeypatch, queue_file):
    path = tmp_path / "tracking.json"
    today = lambda: "2026-11-14"
    if queue_file:
        queue = FeishuWriteQueue(path, today=today)
        queue.add(["A"])
        write = lambda: queue.add(["B"])
    else:
        stats = DailyStatsStore(path, today=today)
        stats.record("success", [tmp_path / "A.mp4"])
        write = lambda: stats.record("failure", [tmp_path / "B.mp4"])
    before = path.read_bytes()

    def fail_read(*_args, **_kwargs):
        raise PermissionError("file temporarily locked")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_text", fail_read)
        with pytest.raises(TrackingReadError, match="无法读取"):
            write()
    assert path.read_bytes() == before

    write()
    if queue_file:
        assert FeishuWriteQueue(path).load() == ["A", "B"]
    else:
        snapshot = DailyStatsStore(path, today=today).snapshot()
        assert (snapshot["success"], snapshot["failure"]) == (1, 1)


def test_tracking_rejects_invalid_saved_documents(tmp_path):
    path = tmp_path / "stats.json"
    path.write_text('{"date":"2026-11-14","success":1}', encoding="utf-8")
    with pytest.raises(TrackingReadError, match="格式不正确"):
        DailyStatsStore(path).record("success", [tmp_path / "A.mp4"])
    assert path.read_text(encoding="utf-8") == '{"date":"2026-11-14","success":1}'

    path.write_text('{"A":123}', encoding="utf-8")
    with pytest.raises(TrackingReadError, match="格式不正确"):
        FeishuWriteQueue(path).remove({"A"})
    assert path.read_text(encoding="utf-8") == '{"A":123}'


def test_feishu_queue_is_durable_and_deduplicated(tmp_path):
    path = tmp_path / "queue.json"
    queue = FeishuWriteQueue(path)
    queue.add(["A", "A", "B"])
    assert FeishuWriteQueue(path).load() == ["A", "B"]
    queue.remove({"A"})
    assert queue.load() == ["B"]


def test_feishu_queue_daily_count_keeps_old_entries_available_for_retry(tmp_path):
    path = tmp_path / "queue.json"
    path.write_text('["旧记录"]', encoding="utf-8")
    current = ["2026-11-14"]
    queue = FeishuWriteQueue(path, today=lambda: current[0])
    assert queue.count(current[0]) == 0

    queue.add(["昨天上传"])
    assert queue.count(current[0]) == 1
    current[0] = "2026-11-15"
    queue = FeishuWriteQueue(path, today=lambda: current[0])
    assert queue.count(current[0]) == 0

    queue.add(["今天上传", "今天上传", "昨天上传"])
    assert queue.count(current[0]) == 2
    assert queue.load() == ["旧记录", "昨天上传", "今天上传"]
    queue.remove({"旧记录", "今天上传"})
    assert queue.count(current[0]) == 1
    assert queue.load() == ["昨天上传"]


def test_feishu_queue_counts_success_on_its_upload_day_across_midnight(tmp_path):
    current = ["2026-11-14"]
    stats = DailyStatsStore(tmp_path / "stats.json", lambda: current[0])
    queue = FeishuWriteQueue(tmp_path / "queue.json", today=lambda: current[0])
    video = tmp_path / "A.mp4"
    day = stats.record("success", [video])
    current[0] = "2026-11-15"

    queue.add([video.stem], day=day)

    assert queue.count("2026-11-14") == 1
    assert queue.count("2026-11-15") == 0
    assert queue.load() == ["A"]
