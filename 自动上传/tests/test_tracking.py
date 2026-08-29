from video_feishu.tracking import DailyStatsStore, FeishuWriteQueue


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


def test_feishu_queue_is_durable_and_deduplicated(tmp_path):
    path = tmp_path / "queue.json"
    queue = FeishuWriteQueue(path)
    queue.add(["A", "A", "B"])
    assert FeishuWriteQueue(path).load() == ["A", "B"]
    queue.remove({"A"})
    assert queue.load() == ["B"]
