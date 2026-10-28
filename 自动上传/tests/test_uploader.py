from video_feishu.config import Settings
import pytest
from unittest.mock import MagicMock

from video_feishu.uploader import OceanEngineUploader, UploadCancelled, UploadJournal, find_chrome_executable
from video_feishu.automation import UploadBatchResult


def test_finds_system_wide_chrome(tmp_path):
    chrome = tmp_path / "Google" / "Chrome" / "Application" / "chrome.exe"
    chrome.parent.mkdir(parents=True)
    chrome.write_bytes(b"chrome")

    assert find_chrome_executable({"PROGRAMFILES": str(tmp_path)}) == chrome


def test_missing_chrome_is_reported_before_upload(monkeypatch):
    monkeypatch.setattr("video_feishu.uploader.find_chrome_executable", lambda: None)

    with pytest.raises(RuntimeError, match="视频尚未移动"):
        OceanEngineUploader(Settings()).ensure_browser_available()


def test_extracts_material_ids_from_video_row():
    text = "自动上传功能测试.mp4\nID:7665264333816414250"
    assert OceanEngineUploader._ids(text) == {"7665264333816414250"}


def test_material_id_requires_numeric_id_marker():
    assert OceanEngineUploader._ids("上传中 45%") == set()


def test_material_search_uses_visible_video_name_input():
    selectors = []

    class Page:
        def locator(self, selector):
            selectors.append(selector)
            return object()

    OceanEngineUploader._material_search(Page())

    assert selectors == ['input[placeholder*="视频名称"]:visible']


def test_journal_recovers_confirmed_remote_upload_without_resubmitting(tmp_path):
    video = tmp_path / "large.mp4"
    video.write_bytes(b"video")
    journal = UploadJournal(tmp_path / "jobs.json")
    journal.begin(video, {"100"})

    class Page:
        def goto(self, *_args, **_kwargs):
            pass

    uploader = OceanEngineUploader(Settings(), journal=journal)
    uploader._ensure_page = lambda: Page()
    uploader._search_ids = lambda _page, _name: {"100", "200"}

    result = uploader._upload_batch([video])

    assert result.succeeded == (video,)
    assert result.failed == ()
    assert result.uncertain == ()


def test_recent_unconfirmed_journal_entry_waits_instead_of_reuploading(tmp_path):
    video = tmp_path / "large.mp4"
    video.write_bytes(b"video")
    journal = UploadJournal(tmp_path / "jobs.json")
    journal.begin(video, {"100"})

    class Page:
        def goto(self, *_args, **_kwargs):
            pass

    uploader = OceanEngineUploader(Settings(recovery_grace_seconds=1800), journal=journal)
    uploader._ensure_page = lambda: Page()
    uploader._search_ids = lambda _page, _name: {"100"}

    result = uploader._upload_batch([video])

    assert result.succeeded == ()
    assert result.uncertain == (video,)


def test_journal_keeps_attempt_count_when_upload_is_retried(tmp_path):
    video = tmp_path / "large.mp4"
    video.write_bytes(b"video")
    journal = UploadJournal(tmp_path / "jobs.json")

    journal.begin(video, {"100"})
    journal.mark_retry([video])
    journal.begin(video, {"100"})

    assert journal.get(video)["attempts"] == 2
    assert "retry_now" not in journal.get(video)


def test_confirmed_duplicate_accepts_existing_material_id(tmp_path):
    video = tmp_path / "duplicate.mp4"
    video.write_bytes(b"video")
    uploader = OceanEngineUploader(Settings(), timeout_seconds=1)
    uploader._confirm_iaa_materials = lambda *_args, **_kwargs: False
    uploader._search_ids = lambda _page, _name: {"100"}

    result = uploader._wait_for_result(object(), [video], {video: {"100"}})

    assert result.succeeded == (video,)


def test_confirmation_search_uses_its_own_timeout(tmp_path, monkeypatch):
    video = tmp_path / "missing.mp4"
    video.write_bytes(b"video")
    clock = [0.0]
    uploader = OceanEngineUploader(Settings(upload_confirmation_timeout_minutes=1), timeout_seconds=999)
    uploader._confirm_iaa_materials = lambda *_args, **_kwargs: False
    uploader._search_ids = lambda _page, _name: set()
    uploader._wait = lambda _milliseconds: clock.__setitem__(0, clock[0] + 61)
    monkeypatch.setattr("video_feishu.uploader.time.monotonic", lambda: clock[0])

    result = uploader._wait_for_result(object(), [video], {video: set()})

    assert result.uncertain == (video,)
    assert clock[0] == 61


def test_restart_recovers_confirmed_duplicate_without_reuploading(tmp_path):
    video = tmp_path / "duplicate.mp4"
    video.write_bytes(b"video")
    journal = UploadJournal(tmp_path / "jobs.json")
    journal.begin(video, {"100"})
    journal.mark_confirmed([video])

    class Page:
        def goto(self, *_args, **_kwargs):
            pass

    uploader = OceanEngineUploader(Settings(), journal=journal)
    uploader._ensure_page = lambda: Page()
    uploader._search_ids = lambda _page, _name: {"100"}

    result = uploader._upload_batch([video])

    assert result.succeeded == (video,)


def test_dialog_cancels_only_failed_file_for_next_cycle(tmp_path):
    good = tmp_path / "good.mp4"
    failed = tmp_path / "failed.mp4"
    good.write_bytes(b"good")
    failed.write_bytes(b"failed")

    class Page:
        tick = 0

        def wait_for_timeout(self, _milliseconds):
            self.tick += 1

    page = Page()
    uploader = OceanEngineUploader(Settings(), timeout_seconds=5)
    uploader._dialog_all_uploaded = lambda *_args: False
    uploader._row_text = lambda current, filename: (
        "上传成功" if filename == good.name or current.tick > 0 else "上传失败 重试"
    )
    uploader._dialog_progress = lambda _page, _filename: []
    uploader._wait = lambda _milliseconds: setattr(page, "tick", page.tick + 1)
    cancelled = []
    uploader._click_dialog_cancel = lambda _page, filename: cancelled.append(filename) or True

    result = uploader._wait_for_dialog_uploads(page, [good, failed])

    assert result.succeeded == (good,)
    assert result.failed == (failed,)
    assert cancelled == [failed.name]


def test_dialog_cancels_stalled_file_after_configured_minutes(tmp_path, monkeypatch):
    video = tmp_path / "stalled.mp4"
    video.write_bytes(b"video")
    clock = [0.0]
    uploader = OceanEngineUploader(Settings(upload_stall_timeout_minutes=1), timeout_seconds=120)
    uploader._dialog_all_uploaded = lambda *_args: False
    uploader._row_text = lambda _page, _filename: "stalled.mp4 2%"
    uploader._dialog_progress = lambda _page, _filename: []
    uploader._wait = lambda _milliseconds: clock.__setitem__(0, clock[0] + 61)
    monkeypatch.setattr("video_feishu.uploader.time.monotonic", lambda: clock[0])
    cancelled = []
    uploader._click_dialog_cancel = lambda _page, filename: cancelled.append(filename) or True

    result = uploader._wait_for_dialog_uploads(object(), [video])

    assert result.failed == (video,)
    assert cancelled == [video.name]


def test_dialog_keeps_failed_video_when_cancel_control_is_missing(tmp_path):
    video = tmp_path / "uncancellable.mp4"
    video.write_bytes(b"video")
    uploader = OceanEngineUploader(Settings(), timeout_seconds=5)
    uploader._dialog_all_uploaded = lambda *_args: False
    uploader._row_text = lambda _page, _filename: "上传失败"
    uploader._dialog_progress = lambda _page, _filename: []
    uploader._click_dialog_cancel = lambda *_args: False

    result = uploader._wait_for_dialog_uploads(object(), [video])

    assert result.failed == (video,)


def test_dialog_progress_growth_resets_stall_timer(tmp_path, monkeypatch):
    video = tmp_path / "growing.mp4"
    video.write_bytes(b"video")
    clock = [0.0]
    uploader = OceanEngineUploader(Settings(upload_stall_timeout_minutes=1), timeout_seconds=120)
    uploader._dialog_all_uploaded = lambda *_args: False
    uploader._row_text = lambda _page, _filename: "growing.mp4 " + ("2%" if clock[0] < 30 else "3%" if clock[0] < 60 else "100%")
    uploader._dialog_progress = lambda _page, _filename: []
    uploader._wait = lambda _milliseconds: clock.__setitem__(0, clock[0] + 30)
    monkeypatch.setattr("video_feishu.uploader.time.monotonic", lambda: clock[0])
    uploader._click_dialog_cancel = lambda *_args: pytest.fail("progressing video must not be cancelled")

    result = uploader._wait_for_dialog_uploads(object(), [video])

    assert result.succeeded == (video,)


def test_dialog_accepts_100_percent_as_complete(tmp_path):
    video = tmp_path / "large.mp4"
    video.write_bytes(b"video")

    class Page:
        def wait_for_timeout(self, _milliseconds):
            pass

    uploader = OceanEngineUploader(Settings(), timeout_seconds=1)
    uploader._dialog_all_uploaded = lambda *_args: False
    uploader._row_text = lambda _page, _filename: "large.mp4 100%"
    uploader._dialog_progress = lambda _page, _filename: [100]

    uploader._wait_for_dialog_uploads(Page(), [video])


def test_cancel_interrupts_upload_wait_without_deleting_video(tmp_path):
    video = tmp_path / "large.mp4"
    video.write_bytes(b"video")
    uploader = OceanEngineUploader(Settings(), timeout_seconds=60)
    uploader.cancel()

    with pytest.raises(UploadCancelled):
        uploader._wait_for_dialog_uploads(object(), [video])

    assert video.exists()


def test_login_page_uses_normal_chrome_and_waits_for_close(monkeypatch, tmp_path):
    class Process:
        checks = 0

        def poll(self):
            self.checks += 1
            return 0 if self.checks > 2 else None

    uploader = OceanEngineUploader(Settings())
    uploader.ensure_browser_available = lambda: tmp_path / "chrome.exe"
    uploader.close = lambda: None
    launched = []
    monkeypatch.setattr("video_feishu.uploader.subprocess.Popen", lambda command: launched.append(command) or Process())
    waits = []
    uploader._wait = waits.append

    uploader.open_login_page()

    assert waits == [500, 500]
    assert "--new-window" in launched[0]
    assert not any("no-sandbox" in item for item in launched[0])


def test_close_accepts_browser_already_closed():
    class Context:
        def close(self):
            raise RuntimeError("already closed")

    class Playwright:
        stopped = False

        def stop(self):
            self.stopped = True

    uploader = OceanEngineUploader(Settings())
    uploader._context = Context()
    uploader._playwright = Playwright()

    uploader.close()

    assert uploader._playwright is None


def _ready_upload(tmp_path):
    video = tmp_path / "ready.mp4"
    video.write_bytes(b"offline-video")
    journal = UploadJournal(tmp_path / "jobs.json")
    uploader = OceanEngineUploader(Settings(), journal=journal)
    page = MagicMock()
    page.get_by_text.return_value.count.return_value = 1
    page.get_by_role.return_value.count.return_value = 1
    page.get_by_role.return_value.is_enabled.return_value = True
    uploader._ensure_page = lambda: page
    uploader._search_ids = lambda *_args: set()
    uploader._wait_for_dialog_uploads = lambda *_args: UploadBatchResult((video,))
    return uploader, page, video


def test_upload_handles_iaa_before_marking_confirmed_and_querying_results(tmp_path):
    uploader, page, video = _ready_upload(tmp_path)
    events = []
    page.get_by_role.return_value.click.side_effect = lambda: events.append("upload-confirm")
    uploader._confirm_iaa_materials = lambda *_args, **_kwargs: events.append("iaa-confirm") or True
    mark_confirmed = uploader.journal.mark_confirmed

    def mark(paths):
        events.append("journal-confirmed")
        mark_confirmed(paths)

    def result(*_args):
        events.append("verify-material")
        assert events == ["upload-confirm", "iaa-confirm", "journal-confirmed", "verify-material"]
        return UploadBatchResult((video,))

    uploader.journal.mark_confirmed = mark
    uploader._wait_for_result = result

    result = uploader._upload_batch([video])

    assert result.succeeded == (video,)
    assert video.exists()


def test_iaa_failure_preserves_video_and_does_not_mark_upload_confirmed(tmp_path):
    uploader, _page, video = _ready_upload(tmp_path)

    def stuck(*_args, **_kwargs):
        raise TimeoutError("仅IAA确认弹窗未关闭")

    uploader._confirm_iaa_materials = stuck
    uploader._wait_for_result = lambda *_args: pytest.fail("must not verify before confirmation")

    with pytest.raises(TimeoutError, match="仅IAA"):
        uploader._upload_batch([video])

    assert video.exists()
    assert "confirmed_at" not in uploader.journal.get(video)


def test_delayed_iaa_dialog_is_handled_before_each_material_search(tmp_path):
    video = tmp_path / "late.mp4"
    uploader = OceanEngineUploader(Settings())
    events = []
    checks = iter((True, False))
    uploader._confirm_iaa_materials = lambda *_args, **_kwargs: events.append("iaa-check") or next(checks)
    uploader._search_ids = lambda *_args: events.append("search") or {"200"}

    result = uploader._wait_for_result(object(), [video], {video: set()})

    assert result.succeeded == (video,)
    assert events == ["iaa-check", "search", "iaa-check"]


def test_iaa_appearing_during_search_is_confirmed_then_search_retried(tmp_path):
    video = tmp_path / "race.mp4"
    uploader = OceanEngineUploader(Settings())
    events = []
    checks = iter((False, True, False))

    def confirm(*_args, **_kwargs):
        events.append("iaa-check")
        return next(checks)

    def search(*_args):
        events.append("search")
        if events.count("search") == 1:
            raise RuntimeError("two visible video search inputs")
        return {"200"}

    uploader._confirm_iaa_materials = confirm
    uploader._search_ids = search

    result = uploader._wait_for_result(object(), [video], {video: set()})

    assert result.succeeded == (video,)
    assert events == ["iaa-check", "search", "iaa-check", "search", "iaa-check"]


def test_unrelated_search_error_is_not_hidden_by_iaa_handling(tmp_path):
    video = tmp_path / "error.mp4"
    uploader = OceanEngineUploader(Settings())
    uploader._confirm_iaa_materials = lambda *_args, **_kwargs: False

    def search(*_args):
        raise RuntimeError("unrelated search failure")

    uploader._search_ids = search

    with pytest.raises(RuntimeError, match="unrelated search failure"):
        uploader._wait_for_result(object(), [video], {video: set()})


def test_iaa_appearing_during_successful_search_requires_fresh_material_query(tmp_path):
    video = tmp_path / "late-success.mp4"
    uploader = OceanEngineUploader(Settings())
    events = []
    checks = iter((False, True))
    ids = iter(({"modal-id"}, {"verified-material-id"}))

    def confirm(*_args, **_kwargs):
        events.append("iaa-check")
        return next(checks)

    def search(*_args):
        events.append("search")
        return next(ids)

    uploader._confirm_iaa_materials = confirm
    uploader._search_ids = search

    result = uploader._wait_for_result(object(), [video], {video: set()})

    assert result.succeeded == (video,)
    assert events == ["iaa-check", "search", "iaa-check", "search"]
