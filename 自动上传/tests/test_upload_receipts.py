"""Offline regressions for OceanEngine content-addressed upload receipts."""

from copy import deepcopy
import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from video_feishu.automation import UploadBatchResult
from video_feishu.config import Settings
from video_feishu.uploader import OceanEngineUploader, UploadJournal


OWNER_ID = "1234567890123456"
MATERIAL_ID = "7000000000000000001"
MATERIAL_URL = (
    "https://ad.oceanengine.com/material_center/management/video?aadvid=" + OWNER_ID
)
CONFIRM_URL = (
    "https://ad.oceanengine.com/material_center/api/v1/management/video/confirm"
)
ABC_MD5 = "900150983cd24fb0d6963f7d28e17f72"


class EventPage:
    """Only the page response-event boundary; this never starts a browser."""

    def __init__(self, url=MATERIAL_URL):
        self.url = url
        self.listeners = {}

    def on(self, event, callback):
        self.listeners.setdefault(event, []).append(callback)

    def remove_listener(self, event, callback):
        self.listeners[event].remove(callback)

    def emit(self, response):
        for callback in tuple(self.listeners.get("response", [])):
            callback(response)


class ConfirmResponse:
    def __init__(self, payload, *, url=CONFIRM_URL, method="POST", status=200):
        self.url = url
        self.status = status
        self.request = SimpleNamespace(method=method, url=url)
        self.payload = payload

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return deepcopy(self.payload)


def receipt_payload():
    # Shape observed on OceanEngine's real confirm endpoint. Local bytes and
    # their known digest replace the user's large file for this offline probe.
    return {
        "code": 0,
        "data": {
            "results": [
                {
                    "material_id": MATERIAL_ID,
                    "md5": ABC_MD5,
                    "size": "3",
                    "status_code": 0,
                    "request_video_id": "request-new-video",
                    "original_video_id": "retained-original-video",
                    "update_owner_results": [
                        {"owner_id": OWNER_ID, "status_code": 0}
                    ],
                }
            ],
            "failed": [],
        },
    }


@pytest.mark.parametrize("change_at", ["wait", "marker"])
def test_id_readback_rechecks_account_after_search(receipt_setup, change_at):
    uploader, page, video = receipt_setup
    uploader._prepare_confirm_receipts(page, [video])
    search = MagicMock()
    search.count.return_value = 1
    uploader._material_search = lambda _page: search
    other = "https://ad.oceanengine.com/material_center/management/video?aadvid=1872774218798096"
    page.wait_for_timeout = lambda _ms: setattr(page, "url", other) if change_at == "wait" else None
    marker = MagicMock()
    def count_marker():
        if change_at == "marker":
            page.url = other
        return 1
    marker.count.side_effect = count_marker
    page.get_by_text = lambda *_args, **_kwargs: SimpleNamespace(filter=lambda **_kw: marker)
    with pytest.raises(RuntimeError, match="账号变化"):
        uploader._search_material_id(page, MATERIAL_ID)


def test_receipt_verification_rechecks_account_before_success(receipt_setup):
    uploader, page, video = receipt_setup
    accept_receipt(uploader, page, video)
    def switched(_page, _material):
        page.url = "https://ad.oceanengine.com/material_center/management/video?aadvid=1872774218798096"
        return True
    uploader._search_material_id = switched
    with pytest.raises(RuntimeError, match="账号变化"):
        uploader._verify_receipt_material(page, video)


@pytest.fixture
def receipt_setup(tmp_path):
    video = tmp_path / "renamed.mp4"
    video.write_bytes(b"abc")
    uploader = OceanEngineUploader(
        Settings(material_url=MATERIAL_URL),
        confirmation_timeout_seconds=1,
        journal=UploadJournal(tmp_path / "jobs.json"),
    )
    uploader._confirm_iaa_materials = lambda *_args, **_kwargs: False
    return uploader, EventPage(), video


def accept_receipt(uploader, page, video):
    uploader._prepare_confirm_receipts(page, [video])
    page.emit(ConfirmResponse(receipt_payload()))


def fast_clock(monkeypatch, uploader):
    clock = [0.0]
    monkeypatch.setattr("video_feishu.uploader.time.monotonic", lambda: clock[0])
    uploader._wait = lambda _ms: clock.__setitem__(0, clock[0] + 2)


def test_duplicate_receipt_accepts_material_id_when_renamed_filename_is_absent(
    receipt_setup, monkeypatch
):
    """A duplicate keeps its old server title, so its receipt ID is the evidence."""
    uploader, page, video = receipt_setup
    accept_receipt(uploader, page, video)
    uploader._search_material_id = lambda _page, value: value == MATERIAL_ID
    uploader._search_ids = lambda *_args: pytest.fail("receipt must be verified by ID")
    fast_clock(monkeypatch, uploader)

    result = uploader._wait_for_result(page, [video], {video: set()})

    assert result.succeeded == (video,)
    assert result.failed == ()
    assert result.uncertain == ()
    assert video.read_bytes() == b"abc"


def test_prepare_hashes_original_bytes_and_maps_valid_duplicate_receipt(receipt_setup):
    uploader, page, video = receipt_setup
    accept_receipt(uploader, page, video)

    assert uploader._confirmed_receipts == {str(video.resolve()): {MATERIAL_ID}}
    assert video.read_bytes() == b"abc"


def test_receipt_maps_only_matching_content_in_batch(receipt_setup, tmp_path):
    uploader, page, video = receipt_setup
    other = tmp_path / "different.mp4"
    other.write_bytes(b"xyz")
    uploader._prepare_confirm_receipts(page, [video, other])

    page.emit(ConfirmResponse(receipt_payload()))

    assert uploader._confirmed_receipts.get(str(video.resolve())) == {MATERIAL_ID}
    assert not uploader._confirmed_receipts.get(str(other.resolve()))


def test_confirmed_receipt_is_deduplicated(receipt_setup):
    uploader, page, video = receipt_setup
    accept_receipt(uploader, page, video)
    page.emit(ConfirmResponse(receipt_payload()))

    assert uploader._confirmed_receipts == {str(video.resolve()): {MATERIAL_ID}}


@pytest.mark.parametrize(
    "path,value",
    [
        ("code", 1),
        ("code", "0"),
        ("code", False),
        ("data", None),
        ("data.results", None),
        ("data.results", {}),
        ("data.results", [None]),
        ("data.failed", [{"status_code": 1}]),
        ("data.failed", None),
        ("data.results.0.status_code", 1),
        ("data.results.0.status_code", "0"),
        ("data.results.0.status_code", False),
        ("data.results.0.md5", "d16fb36f0911f878998c136191af705e"),
        ("data.results.0.md5", None),
        ("data.results.0.size", "4"),
        ("data.results.0.size", None),
        ("data.results.0.material_id", "0"),
        ("data.results.0.material_id", "-123"),
        ("data.results.0.material_id", "untrusted-id"),
        ("data.results.0.material_id", None),
        ("data.results.0.update_owner_results", []),
        ("data.results.0.update_owner_results", None),
        ("data.results.0.update_owner_results.0.owner_id", "1869328457013324"),
        ("data.results.0.update_owner_results.0.status_code", 1),
        ("data.results.0.update_owner_results.0.status_code", False),
    ],
    ids=[
        "top-error", "string-top-code", "boolean-top-code", "missing-data",
        "missing-results", "non-list-results", "non-object-result", "has-failures",
        "unknown-failures", "row-error", "string-row-code", "boolean-row-code",
        "other-content", "missing-md5", "wrong-size", "missing-size", "zero-id",
        "negative-id", "non-numeric-id", "missing-id", "no-owner-update",
        "unknown-owner-updates", "wrong-account", "owner-update-error",
        "boolean-owner-code",
    ],
)
def test_untrusted_or_failed_receipt_is_not_accepted(receipt_setup, path, value):
    uploader, page, video = receipt_setup
    uploader._prepare_confirm_receipts(page, [video])
    payload = receipt_payload()
    parts = path.split(".")
    current = payload
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    final = int(parts[-1]) if isinstance(current, list) else parts[-1]
    current[final] = value

    page.emit(ConfirmResponse(payload))

    assert not uploader._confirmed_receipts.get(str(video.resolve()))
    assert video.read_bytes() == b"abc"


@pytest.mark.parametrize(
    "changes",
    [
        {"url": "http://ad.oceanengine.com/material_center/api/v1/management/video/confirm"},
        {"url": "https://ad.oceanengine.com.evil.invalid/material_center/api/v1/management/video/confirm"},
        {"url": "https://other.invalid/material_center/api/v1/management/video/confirm"},
        {"url": CONFIRM_URL + "/unexpected"},
        {"method": "GET"},
        {"status": 199},
        {"status": 302},
        {"status": 500},
    ],
    ids=["http", "host-suffix", "other-host", "other-path", "get", "1xx", "redirect", "http-error"],
)
def test_only_confirm_post_success_responses_are_accepted(receipt_setup, changes):
    uploader, page, video = receipt_setup
    uploader._prepare_confirm_receipts(page, [video])

    page.emit(ConfirmResponse(receipt_payload(), **changes))

    assert not uploader._confirmed_receipts.get(str(video.resolve()))


@pytest.mark.parametrize("payload", [None, [], "not-an-object", ValueError("invalid JSON")])
def test_malformed_json_receipt_is_ignored_without_interrupting_upload(receipt_setup, payload):
    uploader, page, video = receipt_setup
    uploader._prepare_confirm_receipts(page, [video])

    page.emit(ConfirmResponse(payload))

    assert not uploader._confirmed_receipts.get(str(video.resolve()))


def test_changed_local_file_cannot_use_its_previous_content_receipt(receipt_setup):
    uploader, page, video = receipt_setup
    uploader._prepare_confirm_receipts(page, [video])
    previous = video.stat()
    video.write_bytes(b"xyz")
    os.utime(video, ns=(previous.st_atime_ns, previous.st_mtime_ns + 1_000_000))
    assert video.stat().st_mtime_ns != previous.st_mtime_ns

    page.emit(ConfirmResponse(receipt_payload()))

    assert not uploader._confirmed_receipts.get(str(video.resolve()))
    assert video.read_bytes() == b"xyz"


def test_changed_file_after_receipt_stays_unconfirmed_and_preserves_new_bytes(
    receipt_setup, monkeypatch
):
    uploader, page, video = receipt_setup
    accept_receipt(uploader, page, video)
    previous = video.stat()
    video.write_bytes(b"xyz")
    os.utime(video, ns=(previous.st_atime_ns, previous.st_mtime_ns + 1_000_000))
    assert video.stat().st_mtime_ns != previous.st_mtime_ns
    uploader._search_material_id = lambda *_args: True
    uploader._search_ids = lambda *_args: pytest.fail("receipt must be verified by ID")
    fast_clock(monkeypatch, uploader)

    result = uploader._wait_for_result(page, [video], {video: set()})

    assert result.succeeded == ()
    assert result.uncertain == (video,)
    assert video.read_bytes() == b"xyz"


def test_local_file_changed_during_id_readback_is_not_reported_success(receipt_setup):
    uploader, page, video = receipt_setup
    accept_receipt(uploader, page, video)

    def readback(_page, _value):
        previous = video.stat()
        video.write_bytes(b"xyz")
        os.utime(video, ns=(previous.st_atime_ns, previous.st_mtime_ns + 1_000_000))
        assert video.stat().st_mtime_ns != previous.st_mtime_ns
        return True

    uploader._search_material_id = readback

    assert uploader._verify_receipt_material(page, video) is False
    assert video.read_bytes() == b"xyz"


def test_new_batch_detaches_previous_page_and_clears_stale_receipts(receipt_setup):
    uploader, old_page, video = receipt_setup
    accept_receipt(uploader, old_page, video)
    new_page = EventPage()

    uploader._prepare_confirm_receipts(new_page, [video])

    assert not uploader._confirmed_receipts.get(str(video.resolve()))
    old_page.emit(ConfirmResponse(receipt_payload()))
    assert not uploader._confirmed_receipts.get(str(video.resolve()))
    new_page.emit(ConfirmResponse(receipt_payload()))
    assert uploader._confirmed_receipts.get(str(video.resolve())) == {MATERIAL_ID}
    assert len(new_page.listeners["response"]) == 1


def test_prepare_same_page_does_not_register_duplicate_listeners(receipt_setup):
    uploader, page, video = receipt_setup
    uploader._prepare_confirm_receipts(page, [video])
    uploader._prepare_confirm_receipts(page, [video])

    assert len(page.listeners["response"]) == 1


@pytest.mark.parametrize("action", ["_stop_receipt_tracking", "close"])
def test_stopped_receipt_tracking_ignores_later_events(receipt_setup, action):
    uploader, page, video = receipt_setup
    uploader._prepare_confirm_receipts(page, [video])

    getattr(uploader, action)()
    page.emit(ConfirmResponse(receipt_payload()))

    assert not uploader._confirmed_receipts.get(str(video.resolve()))


@pytest.mark.parametrize("raises", [False, True], ids=["success", "exception"])
def test_upload_batch_always_detaches_receipt_listener(receipt_setup, raises):
    uploader, page, video = receipt_setup

    def upload(_videos):
        uploader._prepare_confirm_receipts(page, [video])
        if raises:
            raise RuntimeError("upload interrupted")
        return UploadBatchResult((video,), ())

    uploader._upload_batch = upload
    if raises:
        with pytest.raises(RuntimeError, match="upload interrupted"):
            uploader.upload_batch([video])
    else:
        assert uploader.upload_batch([video]).succeeded == (video,)

    page.emit(ConfirmResponse(receipt_payload()))
    assert not uploader._confirmed_receipts.get(str(video.resolve()))


def test_batch_listens_before_file_chooser_can_emit_confirm_receipt(receipt_setup):
    uploader, page, video = receipt_setup
    control = MagicMock()
    control.count.return_value = 1
    control.is_enabled.return_value = True
    chooser = MagicMock()

    class ChooserContext:
        def __enter__(self):
            return SimpleNamespace(value=chooser)

        def __exit__(self, *_args):
            return False

    page.goto = lambda *_args, **_kwargs: None
    page.wait_for_timeout = lambda *_args: None
    page.locator = lambda *_args: control
    page.get_by_text = lambda *_args, **_kwargs: control
    page.get_by_role = lambda *_args, **_kwargs: control
    page.expect_file_chooser = lambda **_kwargs: ChooserContext()
    uploader._ensure_page = lambda: page
    uploader._search_ids = lambda *_args: set()
    uploader._wait_for_dialog_uploads = lambda *_args: UploadBatchResult((video,), ())
    uploader._search_material_id = lambda _page, value: value == MATERIAL_ID
    chooser.set_files.side_effect = lambda _paths: page.emit(ConfirmResponse(receipt_payload()))

    result = uploader.upload_batch([video])

    assert result.succeeded == (video,)
    assert uploader._confirmed_receipts.get(str(video.resolve())) == {MATERIAL_ID}
    assert video.read_bytes() == b"abc"


def test_receipt_still_requires_id_readback_and_never_uses_filename_as_substitute(
    receipt_setup, monkeypatch
):
    uploader, page, video = receipt_setup
    accept_receipt(uploader, page, video)
    uploader._search_material_id = lambda _page, _value: False
    uploader._search_ids = lambda *_args: pytest.fail("receipt must be verified by ID")
    fast_clock(monkeypatch, uploader)

    result = uploader._wait_for_result(page, [video], {video: set()})

    assert result.succeeded == ()
    assert result.failed == ()
    assert result.uncertain == (video,)
    assert video.read_bytes() == b"abc"


def test_no_receipt_keeps_filename_verification_path(receipt_setup):
    uploader, page, video = receipt_setup
    uploader._search_ids = lambda _page, name: {"123"} if name == video.name else set()
    uploader._search_material_id = lambda *_args: pytest.fail("no receipt ID exists")

    result = uploader._wait_for_result(page, [video], {video: set()})

    assert result.succeeded == (video,)


def test_receipt_arriving_during_filename_search_is_verified_before_success(
    receipt_setup, monkeypatch
):
    uploader, page, video = receipt_setup
    uploader._prepare_confirm_receipts(page, [video])

    def filename_search(_page, _name):
        page.emit(ConfirmResponse(receipt_payload()))
        return set()

    uploader._search_ids = filename_search
    uploader._search_material_id = lambda _page, value: value == MATERIAL_ID
    fast_clock(monkeypatch, uploader)

    result = uploader._wait_for_result(page, [video], {video: set()})

    assert result.succeeded == (video,)
    assert result.uncertain == ()


def test_late_receipt_blocks_unrelated_filename_id_when_receipt_id_is_absent(
    receipt_setup, monkeypatch
):
    uploader, page, video = receipt_setup
    uploader._prepare_confirm_receipts(page, [video])

    def filename_search(_page, _name):
        page.emit(ConfirmResponse(receipt_payload()))
        return {"123456"}

    uploader._search_ids = filename_search
    uploader._search_material_id = lambda _page, _value: False
    fast_clock(monkeypatch, uploader)

    result = uploader._wait_for_result(page, [video], {video: set()})

    assert result.succeeded == ()
    assert result.uncertain == (video,)


def test_id_readback_is_repeated_after_dismissing_delayed_iaa_modal(receipt_setup):
    uploader, page, video = receipt_setup
    accept_receipt(uploader, page, video)
    guards = iter([False, True, False])
    uploader._confirm_iaa_materials = lambda *_args, **_kwargs: next(guards, False)
    searches = iter([True, False])
    uploader._search_material_id = lambda *_args: next(searches)

    assert uploader._verify_receipt_material(page, video) is False


def test_id_search_error_is_retried_only_when_iaa_modal_was_handled(receipt_setup):
    uploader, page, video = receipt_setup
    accept_receipt(uploader, page, video)
    guards = iter([False, True, False])
    uploader._confirm_iaa_materials = lambda *_args, **_kwargs: next(guards, False)
    attempts = []

    def readback(_page, value):
        attempts.append(value)
        if len(attempts) == 1:
            raise RuntimeError("delayed modal covered search")
        return value == MATERIAL_ID

    uploader._search_material_id = readback

    assert uploader._verify_receipt_material(page, video) is True
    assert attempts == [MATERIAL_ID, MATERIAL_ID]


def test_id_search_error_without_known_modal_propagates(receipt_setup):
    uploader, page, video = receipt_setup
    accept_receipt(uploader, page, video)

    def readback(_page, _value):
        raise RuntimeError("unexpected page structure")

    uploader._search_material_id = readback

    with pytest.raises(RuntimeError, match="unexpected page structure"):
        uploader._verify_receipt_material(page, video)
