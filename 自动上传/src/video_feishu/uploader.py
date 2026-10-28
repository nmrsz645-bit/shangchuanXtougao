from pathlib import Path
import hashlib
import json
import logging
import os
import re
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlparse

from .automation import UploadBatchResult
from .config import Settings, app_data_dir, chrome_profile_dir


FAILURE_WORDS = ("上传失败", "失败", "重试")
SUCCESS_WORDS = ("上传成功", "已完成")
IAA_CONFIRMATION_TITLE = re.compile(r'^请确认\s*[「『“"]?\s*仅\s*IAA\s*[」』”"]?\s*素材$', re.IGNORECASE)


def find_chrome_executable(environ: dict[str, str] | None = None) -> Path | None:
    environ = os.environ if environ is None else environ
    roots = (
        environ.get("LOCALAPPDATA"),
        environ.get("PROGRAMFILES"),
        environ.get("PROGRAMFILES(X86)"),
    )
    for root in roots:
        if root and (path := Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe").is_file():
            return path
    return None


class UploadCancelled(Exception):
    pass


class UploadJournal:
    """Crash-safe baseline IDs for uploads that have been submitted."""

    def __init__(self, path: Path | None = None):
        self.path = path or app_data_dir() / "upload_jobs.json"

    def _load(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError):
            logging.exception("上传任务记录损坏，将重新建立")
            return {}

    def _save(self, rows: dict[str, dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
        temp.replace(self.path)

    @staticmethod
    def _key(path: Path) -> str:
        return str(path.resolve())

    @staticmethod
    def _fingerprint(path: Path) -> tuple[int, int]:
        stat = path.stat()
        return stat.st_size, stat.st_mtime_ns

    def get(self, path: Path) -> dict | None:
        rows = self._load()
        row = rows.get(self._key(path))
        if not row:
            return None
        if (row.get("size"), row.get("mtime_ns")) != self._fingerprint(path):
            rows.pop(self._key(path), None)
            self._save(rows)
            return None
        return row

    def begin(self, path: Path, baseline_ids: set[str]) -> None:
        rows = self._load()
        size, mtime_ns = self._fingerprint(path)
        previous = rows.get(self._key(path), {})
        rows[self._key(path)] = {
            "size": size,
            "mtime_ns": mtime_ns,
            "baseline_ids": sorted(baseline_ids),
            "submitted_at": time.time(),
            "attempts": int(previous.get("attempts", 0)) + 1,
        }
        self._save(rows)

    def clear(self, paths: list[Path]) -> None:
        rows = self._load()
        for path in paths:
            rows.pop(self._key(path), None)
        self._save(rows)

    def mark_confirmed(self, paths: list[Path]) -> None:
        rows = self._load()
        for path in paths:
            if row := rows.get(self._key(path)):
                row["confirmed_at"] = time.time()
        self._save(rows)

    def mark_retry(self, paths: list[Path]) -> None:
        rows = self._load()
        for path in paths:
            if row := rows.get(self._key(path)):
                row["retry_now"] = True
        self._save(rows)


class OceanEngineUploader:
    def __init__(self, settings: Settings, timeout_seconds: int | None = None, confirmation_timeout_seconds: int | None = None, journal: UploadJournal | None = None):
        self.settings = settings
        self.timeout_seconds = timeout_seconds or settings.upload_timeout_seconds
        self.confirmation_timeout_seconds = confirmation_timeout_seconds or settings.upload_confirmation_timeout_minutes * 60
        self.journal = journal or UploadJournal()
        self._playwright = None
        self._context = None
        self._page = None
        self._cancelled = threading.Event()
        self._receipt_sources: dict[str, tuple[str, int]] = {}
        self._receipt_fingerprints: dict[str, tuple[int, int]] = {}
        self._confirmed_receipts: dict[str, set[str]] = {}
        self._receipt_page = None
        self._receipt_owner = ""

    def ensure_browser_available(self) -> Path:
        path = find_chrome_executable()
        if not path:
            raise RuntimeError("未找到 Google Chrome，请先安装正式版 Chrome 后再启动上传。视频尚未移动。")
        return path

    def cancel(self) -> None:
        self._cancelled.set()

    def _check_cancelled(self) -> None:
        if self._cancelled.is_set():
            raise UploadCancelled("用户停止了自动上传")

    def _wait(self, milliseconds: int) -> None:
        if self._cancelled.wait(milliseconds / 1000):
            self._check_cancelled()

    def close(self) -> None:
        self._stop_receipt_tracking()
        context, playwright = self._context, self._playwright
        self._context = self._playwright = self._page = None
        try:
            if context:
                try:
                    context.close()
                except Exception:
                    logging.debug("浏览器已经关闭", exc_info=True)
        finally:
            if playwright:
                try:
                    playwright.stop()
                except Exception:
                    logging.debug("浏览器驱动已经停止", exc_info=True)

    def reset(self) -> None:
        self.close()

    def acknowledge(self, videos: list[Path]) -> None:
        self.journal.clear(videos)

    def open_login_page(self) -> None:
        """Open a normal Chrome window for the user to complete login."""
        self.close()
        process = subprocess.Popen([
            str(self.ensure_browser_available()),
            f"--user-data-dir={chrome_profile_dir()}",
            "--new-window",
            self.settings.material_url,
        ])
        while process.poll() is None:
            self._wait(500)

    def _ensure_page(self):
        if self._page and not self._page.is_closed():
            return self._page
        from playwright.sync_api import sync_playwright

        chrome_profile_dir().mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            str(chrome_profile_dir()),
            executable_path=str(self.ensure_browser_available()),
            headless=False,
            no_viewport=True,
            chromium_sandbox=True,
            args=["--start-maximized", "--no-first-run"],
        )
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        self._page.goto(self.settings.material_url, wait_until="domcontentloaded")
        return self._page

    @staticmethod
    def _row_text(page, filename: str) -> str:
        matches = page.get_by_text(filename, exact=True)
        count = matches.count()
        texts = []
        for index in range(count):
            text = matches.nth(index).evaluate(
                """element => {
                    let current = element.parentElement;
                    for (let i = 0; i < 6 && current; i++, current = current.parentElement) {
                        const value = (current.innerText || '').trim();
                        if (value.length > element.innerText.length && value.length <= 800) return value;
                    }
                    return element.innerText || '';
                }"""
            )
            texts.append(text)
        return "\n".join(texts)

    @staticmethod
    def _ids(text: str) -> set[str]:
        return set(re.findall(r"ID[:：]\s*(\d+)", text))

    @staticmethod
    def _material_search(page):
        return page.locator('input[placeholder*="视频名称"]:visible')

    def _search_ids(self, page, filename: str) -> set[str]:
        search = self._material_search(page)
        search.wait_for(state="visible", timeout=60_000)
        if search.count() != 1:
            raise RuntimeError("未找到唯一的素材搜索框")
        search.fill(filename)
        search.press("Enter")
        page.wait_for_timeout(1000)
        return self._ids(self._row_text(page, filename))

    def _stop_receipt_tracking(self) -> None:
        page, self._receipt_page = self._receipt_page, None
        if page is not None:
            try:
                page.remove_listener("response", self._capture_confirm_response)
            except Exception:
                logging.debug("上传确认回执监听已结束")

    def _prepare_confirm_receipts(self, page, videos: list[Path]) -> None:
        self._stop_receipt_tracking()
        self._receipt_sources.clear()
        self._receipt_fingerprints.clear()
        self._confirmed_receipts.clear()
        owners = parse_qs(urlparse(self.settings.material_url).query).get("aadvid", [])
        self._receipt_owner = owners[0] if len(owners) == 1 and owners[0].isdigit() else ""
        if not self._receipt_owner:
            return
        for video in videos:
            self._check_cancelled()
            before = UploadJournal._fingerprint(video)
            with video.open("rb") as stream:
                md5 = hashlib.file_digest(stream, "md5").hexdigest()
            if UploadJournal._fingerprint(video) != before:
                raise RuntimeError(f"视频在读取期间发生变化，已停止上传：{video.name}")
            key = str(video.resolve())
            self._receipt_sources[key] = (md5, before[0])
            self._receipt_fingerprints[key] = before
        self._check_cancelled()
        page.on("response", self._capture_confirm_response)
        self._receipt_page = page

    def _receipt_source_unchanged(self, video: Path) -> bool:
        expected = self._receipt_fingerprints.get(str(video.resolve()))
        try:
            return expected is not None and UploadJournal._fingerprint(video) == expected
        except OSError:
            return False

    def _capture_confirm_response(self, response) -> None:
        """Accept only this batch's content and this account's successful receipt."""
        try:
            parsed = urlparse(response.url)
            if (parsed.scheme, parsed.netloc, parsed.path) != (
                "https", "ad.oceanengine.com", "/material_center/api/v1/management/video/confirm"
            ) or response.request.method != "POST" or not 200 <= response.status < 300:
                return
            payload = response.json()
            if not isinstance(payload, dict) or type(payload.get("code")) is not int or payload["code"] != 0:
                return
            data = payload.get("data")
            if not isinstance(data, dict) or data.get("failed") != [] or not isinstance(data.get("results"), list):
                return
            for row in data["results"]:
                if not isinstance(row, dict) or type(row.get("status_code")) is not int or row["status_code"] != 0:
                    continue
                owners = row.get("update_owner_results", [])
                if not isinstance(owners, list) or not any(
                    isinstance(owner, dict) and str(owner.get("owner_id", "")) == self._receipt_owner
                    and type(owner.get("status_code")) is int and owner["status_code"] == 0
                    for owner in owners
                ):
                    continue
                material_id = str(row.get("material_id", ""))
                md5 = str(row.get("md5", "")).lower()
                if not material_id.isdigit() or int(material_id) <= 0:
                    continue
                for key, (expected_md5, size) in self._receipt_sources.items():
                    if md5 == expected_md5 and str(row.get("size", "")) == str(size) and self._receipt_source_unchanged(Path(key)):
                        self._confirmed_receipts.setdefault(key, set()).add(material_id)
                        logging.info("平台确认上传内容：%s -> 素材ID %s", Path(key).name, material_id)
        except Exception as exc:
            logging.debug("忽略无法核实的上传确认回执（%s）", type(exc).__name__)

    def _require_material_account(self, page) -> None:
        parsed = urlparse(page.url)
        if (parsed.scheme, parsed.netloc, parsed.path) != (
            "https", "ad.oceanengine.com", "/material_center/management/video"
        ) or parse_qs(parsed.query).get("aadvid") != [self._receipt_owner]:
            raise RuntimeError("素材ID或当前账号变化，已停止上传结果核验；原视频已保留")

    def _search_material_id(self, page, material_id: str) -> bool:
        self._require_material_account(page)
        if not material_id.isdigit() or int(material_id) <= 0:
            raise RuntimeError("素材ID无效，已停止上传结果核验；原视频已保留")
        search = self._material_search(page)
        search.wait_for(state="visible", timeout=60_000)
        if search.count() != 1:
            raise RuntimeError("未找到唯一的素材搜索框")
        search.fill(material_id)
        search.press("Enter")
        page.wait_for_timeout(1000)
        markers = page.get_by_text(re.compile(rf"^ID[:：]\s*{material_id}$")).filter(visible=True)
        unique = markers.count() == 1
        self._require_material_account(page)
        return unique

    def _verify_receipt_material(self, page, video: Path) -> bool:
        if not self._receipt_source_unchanged(video):
            return False
        for material_id in sorted(self._confirmed_receipts.get(str(video.resolve()), set())):
            self._check_cancelled()
            self._confirm_iaa_materials(page)
            try:
                visible = self._search_material_id(page, material_id)
            except Exception:
                if not self._confirm_iaa_materials(page):
                    raise
                visible = self._search_material_id(page, material_id)
            if self._confirm_iaa_materials(page):
                visible = self._search_material_id(page, material_id)
            if visible and self._receipt_source_unchanged(video):
                self._require_material_account(page)
                logging.info("按平台回执及素材ID核验成功：%s -> %s", video.name, material_id)
                return True
        return False

    @staticmethod
    def _require_unselected_iaa(modal) -> None:
        selected = re.findall(r"已选择\s*(\d+)\s*个素材\s*仅投放\s*IAA", modal.inner_text())
        if selected != ["0"]:
            raise RuntimeError("仅IAA弹窗选中数量不为0或状态不明，已停止自动确认；原视频已保留")
        unsafe_selection = modal.locator(
            'input[type="checkbox"], [role="checkbox"], .material-center-v2-checkbox--indeterminate'
        ).evaluate_all(
            """elements => elements.some(element => {
                // This site's checkbox expresses partial selection only in CSS.
                if (element.classList.contains('material-center-v2-checkbox--indeterminate')) {
                    return true;
                }
                if (element.matches('input[type="checkbox"]')) {
                    return element.checked || element.indeterminate;
                }
                return element.getAttribute('aria-checked') !== 'false';
            })"""
        )
        if unsafe_selection:
            raise RuntimeError("仅IAA弹窗存在已勾选或状态不明的素材，已停止自动确认；原视频已保留")

    def _confirm_iaa_materials(self, page, *, timeout_ms: int = 0) -> bool:
        """Dismiss only the known IAA dialog, without changing any selection."""
        titles = page.get_by_text(IAA_CONFIRMATION_TITLE).filter(visible=True)
        deadline = time.monotonic() + timeout_ms / 1000
        while True:
            self._check_cancelled()
            count = titles.count()
            if count:
                break
            if time.monotonic() >= deadline:
                return False
            self._wait(100)
        if count != 1:
            raise RuntimeError("仅IAA确认弹窗不唯一，已停止自动确认；原视频已保留")
        # Restrict the button search to a recognized modal ancestor of its title.
        # Never fall back to a page-wide '确认' button when the site changes.
        modal = titles.locator(
            'xpath=ancestor::*[@role="dialog" or @aria-modal="true" or '
            'contains(concat(" ", normalize-space(@class), " "), " byted-modal ") or '
            'contains(concat(" ", normalize-space(@class), " "), " arco-modal ") or '
            'contains(concat(" ", normalize-space(@class), " "), " ant-modal ") or '
            'contains(concat(" ", normalize-space(@class), " "), " material-center-v2-modal ")][1]'
        )
        if modal.count() != 1 or not modal.is_visible():
            raise RuntimeError("未识别到仅IAA确认弹窗容器，已停止自动确认；原视频已保留")
        text = modal.inner_text()
        uploads = re.findall(r"本次成功上传\s*了?\s*(\d+)\s*个素材", text)
        if len(uploads) != 1 or int(uploads[0]) < 1:
            raise RuntimeError("仅IAA弹窗内容变化，已停止自动确认；原视频已保留")
        self._require_unselected_iaa(modal)
        confirm = modal.get_by_role("button", name="确认", exact=True).filter(visible=True)
        if confirm.count() != 1 or not confirm.is_enabled():
            raise RuntimeError("仅IAA弹窗未找到唯一可用的“确认”按钮；原视频已保留")
        self._check_cancelled()
        # Keep the actual container: its title may disappear before the modal does.
        element = modal.element_handle()
        if element is None:
            raise RuntimeError("仅IAA确认弹窗已变化，已停止自动确认；原视频已保留")
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

            deadline = time.monotonic() + min(10, self.confirmation_timeout_seconds)
            while True:
                self._check_cancelled()
                try:
                    # Short actionability probes keep a covered button's wait
                    # cancellable; a probe never dispatches a click.
                    confirm.click(trial=True, timeout=100)
                    break
                except PlaywrightTimeoutError:
                    self._check_cancelled()
                    if time.monotonic() >= deadline:
                        raise TimeoutError("仅IAA确认按钮持续不可点击；原视频已保留") from None
            self._require_unselected_iaa(modal)
            self._check_cancelled()
            confirm.click(timeout=250)
            deadline = time.monotonic() + min(10, self.confirmation_timeout_seconds)
            while True:
                self._check_cancelled()
                if not element.is_visible():
                    logging.info("已确认仅IAA素材弹窗，未勾选任何素材")
                    return True
                if time.monotonic() >= deadline:
                    raise TimeoutError("仅IAA确认弹窗未关闭；原视频已保留，尚未确认上传结果")
                self._wait(100)
        finally:
            element.dispose()

    def _wait_for_result(self, page, videos: list[Path], previous_ids: dict[Path, set[str]]) -> UploadBatchResult:
        deadline = time.monotonic() + self.confirmation_timeout_seconds
        succeeded: set[Path] = set()
        failed: set[Path] = set()
        while time.monotonic() < deadline:
            self._check_cancelled()
            for video in videos:
                if video in succeeded or video in failed:
                    continue
                if self._confirmed_receipts.get(str(video.resolve())):
                    if self._verify_receipt_material(page, video):
                        succeeded.add(video)
                    continue
                self._confirm_iaa_materials(page)
                try:
                    current_ids = self._search_ids(page, video.name)
                except Exception:
                    # A delayed dialog can add another video search input between
                    # the guard above and the search. Retry only after dismissing it.
                    if not self._confirm_iaa_materials(page):
                        raise
                    current_ids = self._search_ids(page, video.name)
                if self._confirm_iaa_materials(page):
                    # IDs read from an open IAA modal are not list verification.
                    current_ids = self._search_ids(page, video.name)
                if self._confirmed_receipts.get(str(video.resolve())):
                    if self._verify_receipt_material(page, video):
                        succeeded.add(video)
                    continue
                new_ids = current_ids - previous_ids[video]
                if new_ids or (previous_ids[video] and current_ids):
                    if not new_ids:
                        logging.info("同名素材已存在，按重复素材完成：%s", video.name)
                    succeeded.add(video)
            if len(succeeded) + len(failed) == len(videos):
                break
            self._wait(5000)
        unresolved = set(videos) - succeeded - failed
        return UploadBatchResult(tuple(succeeded), tuple(failed), tuple(unresolved))

    @staticmethod
    def _click_dialog_cancel(page, filename: str) -> bool:
        matches = page.get_by_text(filename, exact=True)
        if matches.count() != 1:
            return False
        return bool(matches.evaluate(
            """element => {
                let current = element.parentElement;
                for (let i = 0; i < 7 && current; i++, current = current.parentElement) {
                    const controls = [...current.querySelectorAll('button,[role="button"]')];
                    const cancel = controls.find(control => {
                        const label = `${control.innerText || ''} ${control.getAttribute('aria-label') || ''} ${control.title || ''}`;
                        return label.includes('取消');
                    });
                    if (cancel) { cancel.click(); return true; }
                }
                return false;
            }"""
        ))

    @staticmethod
    def _dialog_progress(page, filename: str) -> list[float]:
        matches = page.get_by_text(filename, exact=True)
        if matches.count() != 1:
            return []
        values = matches.evaluate(
            """element => {
                let current = element.parentElement;
                for (let i = 0; i < 7 && current; i++, current = current.parentElement) {
                    const bars = [...current.querySelectorAll('progress,[role="progressbar"]')];
                    if (bars.length) return bars.map(bar => {
                        const value = bar.getAttribute('aria-valuenow') ?? bar.value ?? 0;
                        return Number(value);
                    }).filter(Number.isFinite);
                }
                return [];
            }"""
        )
        return [float(value) for value in values]

    @staticmethod
    def _dialog_all_uploaded(page, videos: list[Path]) -> bool:
        """Recognize a batch that finished before any progress was observed."""
        if not videos or len({video.name for video in videos}) != len(videos):
            return False
        titles = page.get_by_text("本地上传", exact=True).filter(visible=True)
        if titles.count() != 1:
            return False
        drawer = titles.locator(
            'xpath=ancestor::*[@role="dialog" or @aria-modal="true" or '
            'contains(concat(" ", normalize-space(@class), " "), " material-center-v2-drawer ")][1]'
        )
        if drawer.count() != 1 or not drawer.is_visible():
            return False
        counts = {}
        for label in ("全部", "已上传", "上传失败", "上传中"):
            pattern = re.compile(rf"^{label}\s*[（(]\s*(\d+)\s*[）)]$")
            matches = drawer.get_by_text(pattern).filter(visible=True)
            if matches.count() != 1:
                return False
            match = pattern.fullmatch(matches.inner_text().strip())
            if not match:
                return False
            counts[label] = int(match[1])
        if counts != {"全部": len(videos), "已上传": len(videos), "上传失败": 0, "上传中": 0}:
            return False
        return all(drawer.get_by_text(video.name, exact=True).filter(visible=True).count() == 1 for video in videos)

    def _wait_for_dialog_uploads(self, page, videos: list[Path]) -> UploadBatchResult:
        deadline = time.monotonic() + self.timeout_seconds
        stall_timeout = self.settings.upload_stall_timeout_minutes * 60
        seen_progress = {video: False for video in videos}
        last_progress = {video: -1.0 for video in videos}
        last_progress_at = {video: time.monotonic() for video in videos}
        completed: set[Path] = set()
        failed: set[Path] = set()
        next_log = 0.0
        while time.monotonic() < deadline:
            self._check_cancelled()
            if not failed and self._dialog_all_uploaded(page, videos):
                logging.info("上传弹窗确认全部文件已上传：%s/%s", len(videos), len(videos))
                return UploadBatchResult(tuple(videos))
            states: list[str] = []
            for video in videos:
                if video in completed or video in failed:
                    continue
                text = self._row_text(page, video.name)
                progress = self._dialog_progress(page, video.name)
                percentages = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)\s*%", text)]
                active_progress = any(value < 100 for value in [*progress, *percentages])
                finished_progress = any(value >= 100 for value in [*progress, *percentages])
                if progress or percentages:
                    seen_progress[video] = True
                    current_progress = max([*progress, *percentages])
                    if current_progress > last_progress[video]:
                        last_progress[video] = current_progress
                        last_progress_at[video] = time.monotonic()
                states.append(f"{video.name}: {text[:160].replace(chr(10), ' | ')}")
                if any(word in text for word in SUCCESS_WORDS) or finished_progress:
                    completed.add(video)
                    continue
                if seen_progress[video] and not active_progress and text:
                    completed.add(video)
                    continue
                stalled = time.monotonic() - last_progress_at[video] >= stall_timeout
                if any(word in text for word in FAILURE_WORDS) or stalled:
                    if not self._click_dialog_cancel(page, video.name):
                        # The page occasionally renders a failed row without its cancel
                        # control.  Treat it as this video's failure; raising here used
                        # to reset Chrome and discard its retry record for the whole batch.
                        logging.error("上传异常且未找到取消按钮，留待重试：%s", video.name)
                    failed.add(video)
                    reason = "上传失败" if any(word in text for word in FAILURE_WORDS) else f"连续 {self.settings.upload_stall_timeout_minutes} 分钟无进度"
                    logging.warning("取消上传，留待下轮重试：%s（%s）", video.name, reason)
            if time.monotonic() >= next_log:
                logging.info("上传弹窗进度（完成 %s/%s）：%s", len(completed), len(videos), "；".join(states))
                next_log = time.monotonic() + 30
            if len(completed) + len(failed) == len(videos):
                return UploadBatchResult(tuple(completed), tuple(failed))
            self._wait(2000)
        raise TimeoutError("等待上传弹窗全部完成超时；原视频已保留")

    def upload_batch(self, videos: list[Path]) -> UploadBatchResult:
        if not videos or len(videos) > self.settings.batch_size:
            raise ValueError(f"每批必须为 1 到 {self.settings.batch_size} 条视频")
        if missing := [str(path) for path in videos if not path.is_file()]:
            raise FileNotFoundError("待上传视频不存在：" + "、".join(missing))

        try:
            return self._upload_batch(videos)
        except Exception:
            self.reset()
            raise
        finally:
            self._stop_receipt_tracking()

    def _upload_batch(self, videos: list[Path]) -> UploadBatchResult:
        page = self._ensure_page()
        page.goto(self.settings.material_url, wait_until="domcontentloaded")

        recovered: list[Path] = []
        waiting: list[Path] = []
        fresh: list[Path] = []
        permanent: list[Path] = []
        previous_ids: dict[Path, set[str]] = {}
        now = time.time()
        for video in videos:
            current_ids = self._search_ids(page, video.name)
            row = self.journal.get(video)
            if row:
                baseline = set(row.get("baseline_ids", []))
                if current_ids - baseline:
                    recovered.append(video)
                elif row.get("confirmed_at") and current_ids:
                    logging.info("恢复已确认的重复素材：%s", video.name)
                    recovered.append(video)
                elif int(row.get("attempts", 0)) >= self.settings.max_batch_attempts:
                    permanent.append(video)
                elif row.get("retry_now"):
                    previous_ids[video] = current_ids
                    fresh.append(video)
                elif now - float(row.get("submitted_at", 0)) < self.settings.recovery_grace_seconds:
                    waiting.append(video)
                else:
                    previous_ids[video] = current_ids
                    fresh.append(video)
            else:
                previous_ids[video] = current_ids
                fresh.append(video)

        if not fresh:
            return UploadBatchResult(tuple(recovered), (), tuple(waiting), permanent=tuple(permanent))

        search = self._material_search(page)
        search.fill("")
        search.press("Enter")
        page.wait_for_timeout(500)
        upload = page.get_by_text("上传视频", exact=True)
        upload.wait_for(state="visible", timeout=60_000)
        if upload.count() != 1:
            raise RuntimeError("未找到唯一的“上传视频”按钮，请确认账号已登录且网址正确")
        upload.click()
        choose = page.get_by_text("点击上传", exact=True)
        choose.wait_for(state="visible", timeout=30_000)
        if choose.count() != 1:
            raise RuntimeError("上传窗口结构已变化：未找到唯一的“点击上传”入口")
        with page.expect_file_chooser(timeout=30_000) as chooser_info:
            choose.click()
        chooser = chooser_info.value
        if len(fresh) > 1 and not chooser.is_multiple():
            raise RuntimeError("当前上传窗口不支持一次选择多个视频")
        self._prepare_confirm_receipts(page, fresh)
        for video in fresh:
            self.journal.begin(video, previous_ids[video])
        chooser.set_files([str(path) for path in fresh])

        confirm = page.get_by_role("button", name="确定", exact=True)
        if confirm.count() != 1:
            raise RuntimeError("上传窗口结构已变化：未找到唯一的“确定”按钮")
        dialog_result = self._wait_for_dialog_uploads(page, fresh)
        self.journal.mark_retry(list(dialog_result.failed))
        dialog_permanent = [video for video in dialog_result.failed if (row := self.journal.get(video)) and int(row.get("attempts", 0)) >= self.settings.max_batch_attempts]
        dialog_failed = [video for video in dialog_result.failed if video not in dialog_permanent]
        if not dialog_result.succeeded:
            return UploadBatchResult(tuple(recovered), tuple(dialog_failed), tuple(waiting), permanent=tuple([*permanent, *dialog_permanent]))
        if not confirm.is_enabled():
            self.journal.mark_retry(list(dialog_result.succeeded))
            disabled = [*dialog_failed, *dialog_result.succeeded]
            disabled_permanent = [video for video in disabled if (row := self.journal.get(video)) and int(row.get("attempts", 0)) >= self.settings.max_batch_attempts]
            return UploadBatchResult(tuple(recovered), tuple(video for video in disabled if video not in disabled_permanent), tuple(waiting), permanent=tuple([*permanent, *dialog_permanent, *disabled_permanent]))
        confirm.click()
        self._confirm_iaa_materials(page, timeout_ms=min(10_000, int(self.confirmation_timeout_seconds * 1000)))
        self.journal.mark_confirmed(list(dialog_result.succeeded))

        result = self._wait_for_result(page, list(dialog_result.succeeded), previous_ids)
        self.journal.mark_retry(list(result.failed))
        self.journal.mark_retry(list(result.uncertain))
        result_permanent = [video for video in [*result.failed, *result.uncertain] if (row := self.journal.get(video)) and int(row.get("attempts", 0)) >= self.settings.max_batch_attempts]
        result = UploadBatchResult(
            tuple([*recovered, *result.succeeded]),
            tuple(video for video in [*dialog_failed, *result.failed] if video not in result_permanent),
            tuple(waiting),
            tuple(video for video in result.uncertain if video not in result_permanent),
            tuple([*permanent, *dialog_permanent, *result_permanent]),
        )
        logging.info("巨量上传完成：成功=%s 失败=%s", len(result.succeeded), len(result.failed))
        return result
