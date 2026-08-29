from pathlib import Path
import threading

from video_feishu.automation import AutoUploadCoordinator, UploadBatchResult
from video_feishu.config import Settings


class FakeUploader:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def upload_batch(self, videos):
        self.calls.append([path.name for path in videos])
        return self.results.pop(0)


def settings_for(destination: Path) -> Settings:
    return Settings(destination_dir=str(destination), upload_retry_seconds=0)


def test_uploads_ten_at_a_time_and_deletes_only_success(tmp_path):
    videos = []
    for index in range(11):
        path = tmp_path / f"{index:02}.mp4"
        path.write_bytes(b"video")
        videos.append(path)
    uploader = FakeUploader([
        UploadBatchResult(tuple(videos[:10])),
        UploadBatchResult((videos[10],)),
    ])
    coordinator = AutoUploadCoordinator(settings_for(tmp_path), lambda: None, uploader)

    assert coordinator.run_cycle(threading.Event()) is True
    assert uploader.calls == [[f"{index:02}.mp4" for index in range(10)], ["10.mp4"]]
    assert list(tmp_path.glob("*.mp4")) == []


def test_failed_video_is_retried_without_reuploading_successes(tmp_path):
    good = tmp_path / "good.mp4"; good.write_bytes(b"good")
    failed = tmp_path / "failed.mp4"; failed.write_bytes(b"failed")
    uploader = FakeUploader([
        UploadBatchResult((good,), (failed,)),
        UploadBatchResult((failed,), ()),
    ])
    coordinator = AutoUploadCoordinator(settings_for(tmp_path), lambda: None, uploader)

    coordinator.run_cycle(threading.Event())

    assert uploader.calls == [["failed.mp4", "good.mp4"], ["failed.mp4"]]
    assert not good.exists() and not failed.exists()


def test_extracts_when_empty_and_reports_empty_when_nothing_arrives(tmp_path):
    extracted = []
    uploader = FakeUploader([])
    coordinator = AutoUploadCoordinator(settings_for(tmp_path), lambda: extracted.append(True), uploader)

    assert coordinator.run_cycle(threading.Event()) is False
    assert extracted == [True]


def test_wake_event_forces_early_rescan(tmp_path):
    extracted = []
    wake = threading.Event()
    stop = threading.Event()
    first_scan = threading.Event()

    def extract():
        extracted.append(True)
        if len(extracted) == 1:
            first_scan.set()
        else:
            stop.set()

    coordinator = AutoUploadCoordinator(
        Settings(destination_dir=str(tmp_path), check_interval_minutes=30),
        extract,
        FakeUploader([]),
    )
    worker = threading.Thread(target=coordinator.run_forever, args=(stop, wake))
    worker.start()
    assert first_scan.wait(1)

    wake.set()
    worker.join(1)

    assert not worker.is_alive()
    assert extracted == [True, True]


def test_uncertain_result_is_not_deleted(tmp_path):
    video = tmp_path / "keep.mp4"; video.write_bytes(b"video")
    stop = threading.Event()

    class StopUploader:
        def upload_batch(self, videos):
            stop.set()
            return UploadBatchResult()

    coordinator = AutoUploadCoordinator(settings_for(tmp_path), lambda: None, StopUploader())
    coordinator.run_cycle(stop)

    assert video.exists()


def test_only_uploads_videos_moved_to_destination_root(tmp_path):
    nested = tmp_path / "source" / "inner"
    nested.mkdir(parents=True)
    (nested / "not-yet-extracted.mp4").write_bytes(b"video")
    uploader = FakeUploader([])
    coordinator = AutoUploadCoordinator(settings_for(tmp_path), lambda: None, uploader)

    assert coordinator.run_cycle(threading.Event()) is False
    assert uploader.calls == []


def test_skips_processing_video_in_destination_queue(tmp_path):
    ready = tmp_path / "ready.mp4"
    processing = tmp_path / "editing.processing.mp4"
    ready.write_bytes(b"video")
    processing.write_bytes(b"video")
    uploader = FakeUploader([UploadBatchResult((ready,))])
    coordinator = AutoUploadCoordinator(settings_for(tmp_path), lambda: None, uploader)

    coordinator.run_cycle(threading.Event())

    assert uploader.calls == [["ready.mp4"]]
    assert processing.exists()


def test_permanent_failure_does_not_block_later_batches(tmp_path):
    videos = []
    for index in range(11):
        path = tmp_path / f"{index:02}.mp4"
        path.write_bytes(b"video")
        videos.append(path)
    bad = videos[0]
    uploader = FakeUploader([
        UploadBatchResult(tuple(videos[1:10]), (bad,)),
        UploadBatchResult((), (bad,)),
        UploadBatchResult((), (), permanent=(bad,)),
        UploadBatchResult((videos[10],)),
    ])
    coordinator = AutoUploadCoordinator(settings_for(tmp_path), lambda: None, uploader)

    coordinator.run_cycle(threading.Event())

    assert uploader.calls[-1] == ["10.mp4"]
    assert not bad.exists()
    assert (tmp_path / "永久跳过" / bad.name).exists()
    assert not videos[10].exists()


def test_unconfirmed_video_retries_immediately_then_skips_permanently(tmp_path):
    video = tmp_path / "00-missing.mp4"
    later = tmp_path / "01-later.mp4"
    video.write_bytes(b"video")
    later.write_bytes(b"video")
    uploader = FakeUploader([
        UploadBatchResult((), (), (), (video,)),
        UploadBatchResult((), (), (), (video,)),
        UploadBatchResult((), (), (), (video,)),
        UploadBatchResult((later,)),
    ])
    coordinator = AutoUploadCoordinator(Settings(destination_dir=str(tmp_path), batch_size=1, upload_retry_seconds=60, max_batch_attempts=3), lambda: None, uploader)

    coordinator.run_cycle(threading.Event())

    assert uploader.calls == [["00-missing.mp4"], ["00-missing.mp4"], ["00-missing.mp4"], ["01-later.mp4"]]
    assert (tmp_path / "永久跳过" / video.name).exists()
    assert not later.exists()


def test_deferred_failure_returns_after_check_interval(tmp_path):
    failed_dir = tmp_path / "上传失败"
    failed_dir.mkdir()
    video = failed_dir / "retry.mp4"
    video.write_bytes(b"video")
    old = __import__("time").time() - 31 * 60
    __import__("os").utime(video, (old, old))
    uploader = FakeUploader([UploadBatchResult((tmp_path / "retry.mp4",))])
    coordinator = AutoUploadCoordinator(settings_for(tmp_path), lambda: None, uploader)

    coordinator.run_cycle(threading.Event())

    assert uploader.calls == [["retry.mp4"]]
    assert not video.exists()


def test_reports_success_and_explicit_failure_once(tmp_path):
    good = tmp_path / "good.mp4"; good.write_bytes(b"good")
    bad = tmp_path / "bad.mp4"; bad.write_bytes(b"bad")
    uploader = FakeUploader([
        UploadBatchResult((good,), (bad,)),
        UploadBatchResult((), (bad,)),
        UploadBatchResult((), (bad,)),
    ])
    succeeded, failed = [], []
    coordinator = AutoUploadCoordinator(
        settings_for(tmp_path), lambda: None, uploader,
        on_succeeded=lambda videos: succeeded.extend(path.name for path in videos),
        on_failed=lambda videos: failed.extend(path.name for path in videos),
    )

    coordinator.run_cycle(threading.Event())

    assert succeeded == ["good.mp4"]
    assert failed == ["bad.mp4"]
