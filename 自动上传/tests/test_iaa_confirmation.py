"""Offline DOM checks for the optional post-upload IAA confirmation dialog.

Each page uses a fresh, non-persistent Chrome context. All requests are aborted;
the HTML and its timers are local fixtures, never the production material site.
"""

from html import escape
import threading

import pytest

from video_feishu.config import Settings
from video_feishu.uploader import (
    OceanEngineUploader,
    UploadCancelled,
    UploadJournal,
    find_chrome_executable,
)


TITLE = "请确认「仅IAA」素材"
SUCCESS_TEXT = "您本次成功上传了1个素材"
ZERO_SELECTED = "已选择0个素材仅投放IAA"


@pytest.fixture(scope="session")
def iaa_browser():
    playwright_api = pytest.importorskip(
        "playwright.sync_api", reason="Offline IAA DOM tests require Playwright"
    )
    executable = find_chrome_executable()
    if executable is None:
        pytest.skip("Offline IAA DOM tests require installed Google Chrome")
    with playwright_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(
                executable_path=str(executable),
                headless=True,
                args=["--disable-background-networking", "--no-first-run"],
            )
        except playwright_api.Error as exc:
            pytest.skip(f"Offline IAA Chrome could not start: {exc}")
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture
def iaa_page(iaa_browser):
    context = iaa_browser.new_context()
    context.route("**/*", lambda route: route.abort())
    page = context.new_page()
    page.set_default_timeout(1500)
    try:
        yield page
    finally:
        context.close()


@pytest.fixture
def iaa_uploader(tmp_path):
    return OceanEngineUploader(
        Settings(),
        confirmation_timeout_seconds=1,
        journal=UploadJournal(tmp_path / "isolated-jobs.json"),
    )


def _modal(
    *,
    attributes='role="dialog"',
    title=TITLE,
    success=SUCCESS_TEXT,
    selected=ZERO_SELECTED,
    controls='<input id="native" type="checkbox"><span id="aria" role="checkbox" aria-checked="false">素材</span>',
    buttons='<button data-target-confirm>确认</button>',
    extra="",
):
    return (
        f'<section id="target" {attributes}>'
        f"<h2>{escape(title)}</h2>"
        f"<p>{escape(success)}</p><p>{escape(selected)}</p>"
        '<input placeholder="搜索视频名称">'
        f"{controls}<footer>{buttons}</footer>{extra}</section>"
    )


def _production_namespace_modal(
    *, classes="material-center-v2-modal acceptance-extra", selected=0, checked=None,
    indeterminate_label=None,
    indeterminate_class="material-center-v2-checkbox--indeterminate",
):
    """Local shape from public modules 90378/23048 and the IAA component."""
    def checkbox(control_id):
        state = " checked" if control_id == checked else ""
        label_class = (
            f' class="material-center-v2-checkbox {escape(indeterminate_class, quote=True)}"'
            if control_id == indeterminate_label else ' class="material-center-v2-checkbox"'
        )
        return f'<label{label_class}><input id="{control_id}" type="checkbox"{state}></label>'

    rows = "".join(
        f'<tr><td>{checkbox(f"material-{index}")}</td>'
        f'<td><div>本地测试素材{index}.mp4</div><div>ID: {7700000000000000000 + index}</div></td></tr>'
        for index in (1, 2)
    )
    return (
        '<div class="material-center-v2-modal-wrap material-center-v2-oc-modal-wrap">'
        f'<div id="target" class="{escape(classes, quote=True)}">'
        '<div class="material-center-v2-modal-header">'
        f'<div class="material-center-v2-modal-title">{TITLE}</div></div>'
        '<div class="material-center-v2-modal-body"><div class="iaa-tag-modal-content">'
        '<div class="iaa-tag-msg">您本次成功上传 2 个素材。</div>'
        '<div class="iaa-tag-msg">若其中包含“免费”“0元解锁”等无需付费的信息，'
        '请在下方勾选标记此类「仅IAA」素材，标记后素材将仅投放 IAA，不投放 IAP。</div>'
        '<input class="iaa-tag-search" placeholder="输入视频名称/ID搜索">'
        '<table class="iaa-tag-table"><thead><tr>'
        f'<th>{checkbox("select-all")}</th><th>视频名称</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
        f'<div class="iaa-tag-selected-text">已选择 {selected} 个素材仅投放 IAA</div>'
        '</div></div><div class="material-center-v2-modal-footer">'
        '<div class="iaa-tag-footer"><button data-target-confirm>确认</button></div>'
        '</div></div></div>'
    )


def _render(page, modal="", *, close_delay=0, setup="", extra=""):
    close_delay_js = "null" if close_delay is None else str(close_delay)
    page.set_content(
        "<!doctype html><html><body>"
        '<main><input placeholder="请输入视频名称"></main>'
        '<section role="dialog" id="unrelated"><h2>其他操作确认</h2>'
        '<button data-unrelated-confirm>确认</button></section>'
        f"{modal}{extra}"
        "<script>"
        "window.events = {targetClicks: 0, unrelatedClicks: 0, checkboxClicks: 0, checkboxChanges: 0};"
        "window.selectedAtConfirm = null;"
        f"window.closeDelay = {close_delay_js};"
        "document.addEventListener('click', event => {"
        "  if (event.target.closest('input[type=checkbox],[role=checkbox]')) window.events.checkboxClicks++;"
        "  if (event.target.closest('[data-unrelated-confirm]')) window.events.unrelatedClicks++;"
        "  if (event.target.closest('[data-target-confirm]')) {"
        "    window.events.targetClicks++;"
        "    window.selectedAtConfirm = [...document.getElementById('target').querySelectorAll('input[type=checkbox],[role=checkbox]')].some(control => "
        "      control.checked || control.indeterminate || ['true', 'mixed'].includes(control.getAttribute('aria-checked')));"
        "    if (window.closeDelay !== null) setTimeout(() => document.getElementById('target')?.remove(), window.closeDelay);"
        "  }"
        "}, true);"
        "document.addEventListener('change', event => {"
        "  if (event.target.matches('input[type=checkbox],[role=checkbox]')) window.events.checkboxChanges++;"
        "}, true);"
        f"{setup}"
        "</script></body></html>"
    )


def _assert_no_actions(page):
    assert page.evaluate("window.events") == {
        "targetClicks": 0,
        "unrelatedClicks": 0,
        "checkboxClicks": 0,
        "checkboxChanges": 0,
    }


def _assert_only_target_confirm(page):
    assert page.evaluate("window.events") == {
        "targetClicks": 1,
        "unrelatedClicks": 0,
        "checkboxClicks": 0,
        "checkboxChanges": 0,
    }
    assert page.evaluate("window.selectedAtConfirm") is False
    assert page.locator("#unrelated").is_visible()


@pytest.mark.parametrize(
    "attributes",
    [
        'role="dialog"',
        'aria-modal="true"',
        'class="byted-modal"',
        'class="arco-modal"',
        'class="ant-modal"',
    ],
)
def test_confirms_only_recognized_iaa_modal_without_selecting_materials(
    iaa_page, iaa_uploader, attributes
):
    _render(iaa_page, _modal(attributes=attributes))

    assert iaa_uploader._confirm_iaa_materials(iaa_page) is True

    _assert_only_target_confirm(iaa_page)
    assert iaa_page.locator("#target").count() == 0


@pytest.mark.parametrize(
    "classes",
    [
        "material-center-v2-modal",
        "acceptance-extra material-center-v2-modal material-center-v2-modal-divider",
    ],
    ids=["exact-class", "class-token-with-extra-classes"],
)
def test_production_namespace_modal_confirms_real_div_structure_once_without_selection(
    iaa_page, iaa_uploader, classes
):
    _render(iaa_page, _production_namespace_modal(classes=classes))
    target = iaa_page.locator("#target")
    assert target.evaluate("element => element.tagName") == "DIV"
    assert target.get_attribute("role") is None
    assert target.get_attribute("aria-modal") is None
    assert target.locator("input[type=checkbox]").count() == 3
    assert target.locator("input[type=checkbox]:checked").count() == 0
    assert target.locator("tbody tr").count() == 2

    assert iaa_uploader._confirm_iaa_materials(iaa_page) is True

    _assert_only_target_confirm(iaa_page)
    assert target.count() == 0


@pytest.mark.parametrize(
    "classes",
    [
        "material-center-v2-modal__body",
        "material-center-v2-modal-fake",
        "material-center-v2-modal-wrap",
        "material-center-v2-oc-modal-wrap",
    ],
    ids=["body-suffix", "fake-suffix", "only-modal-wrap", "only-oc-modal-wrap"],
)
def test_production_namespace_modal_rejects_prefix_suffix_and_wrapper_impostors(
    iaa_page, iaa_uploader, classes
):
    _render(iaa_page, _production_namespace_modal(classes=classes))

    with pytest.raises(RuntimeError, match="未识别到仅IAA确认弹窗容器"):
        iaa_uploader._confirm_iaa_materials(iaa_page)

    _assert_no_actions(iaa_page)
    assert iaa_page.locator("#target").is_visible()


@pytest.mark.parametrize(
    "selected,checked",
    [(1, None), (0, "select-all"), (0, "material-1"), (0, "material-2")],
    ids=["nonzero-summary", "checked-header", "checked-first-row", "checked-second-row"],
)
def test_production_namespace_modal_rejects_selected_materials_without_actions(
    iaa_page, iaa_uploader, selected, checked
):
    _render(iaa_page, _production_namespace_modal(selected=selected, checked=checked))
    before = iaa_page.locator("#target input[type=checkbox]").evaluate_all(
        "controls => controls.map(control => control.checked)"
    )

    with pytest.raises(RuntimeError, match="选中数量不为0|已勾选或状态不明"):
        iaa_uploader._confirm_iaa_materials(iaa_page)

    _assert_no_actions(iaa_page)
    assert iaa_page.locator("#target input[type=checkbox]").evaluate_all(
        "controls => controls.map(control => control.checked)"
    ) == before
    assert iaa_page.locator("#target").is_visible()


def test_production_namespace_modal_rejects_class_only_indeterminate_selection(
    iaa_page, iaa_uploader
):
    _render(iaa_page, _production_namespace_modal(indeterminate_label="select-all"))
    control = iaa_page.locator("#select-all")
    assert control.evaluate(
        "input => ({checked: input.checked, indeterminate: input.indeterminate, "
        "ariaChecked: input.getAttribute('aria-checked')})"
    ) == {"checked": False, "indeterminate": False, "ariaChecked": None}
    assert control.locator("..").get_attribute("class").split() == [
        "material-center-v2-checkbox", "material-center-v2-checkbox--indeterminate"
    ]

    with pytest.raises(RuntimeError, match="已勾选或状态不明"):
        iaa_uploader._confirm_iaa_materials(iaa_page)

    _assert_no_actions(iaa_page)
    assert iaa_page.locator("#target").is_visible()
    assert control.is_checked() is False


def test_production_namespace_modal_does_not_treat_checkbox_class_suffix_as_indeterminate(
    iaa_page, iaa_uploader
):
    _render(
        iaa_page,
        _production_namespace_modal(
            indeterminate_label="select-all",
            indeterminate_class="material-center-v2-checkbox--indeterminate-fake",
        ),
    )

    assert iaa_uploader._confirm_iaa_materials(iaa_page) is True

    _assert_only_target_confirm(iaa_page)
    assert iaa_page.locator("#target").count() == 0


@pytest.mark.parametrize("title", ["请确认“仅IAA”素材", "请确认 「仅 IAA」 素材"])
def test_accepts_chinese_quote_and_whitespace_variants(iaa_page, iaa_uploader, title):
    _render(iaa_page, _modal(title=title))

    assert iaa_uploader._confirm_iaa_materials(iaa_page) is True

    _assert_only_target_confirm(iaa_page)


def test_hidden_duplicate_does_not_make_visible_confirmation_ambiguous(
    iaa_page, iaa_uploader
):
    hidden = (
        '<section role="dialog" style="display:none">'
        f"<h2>{TITLE}</h2><p>{SUCCESS_TEXT}</p><p>{ZERO_SELECTED}</p>"
        '<button data-unrelated-confirm>确认</button></section>'
    )
    _render(iaa_page, _modal(), extra=hidden)

    assert iaa_uploader._confirm_iaa_materials(iaa_page) is True

    _assert_only_target_confirm(iaa_page)


def test_waits_for_delayed_optional_modal(iaa_page, iaa_uploader):
    _render(
        iaa_page,
        _modal(attributes='role="dialog" style="display:none"'),
        setup="setTimeout(() => document.getElementById('target').style.display = 'block', 75);",
    )

    assert iaa_uploader._confirm_iaa_materials(iaa_page, timeout_ms=500) is True

    _assert_only_target_confirm(iaa_page)


def test_absent_optional_modal_leaves_unrelated_confirmation_untouched(
    iaa_page, iaa_uploader
):
    _render(iaa_page)

    assert iaa_uploader._confirm_iaa_materials(iaa_page, timeout_ms=50) is False

    _assert_no_actions(iaa_page)


@pytest.mark.parametrize("selected", ["已选择1个素材仅投放IAA", "已选择10个素材仅投放IAA"])
def test_rejects_nonzero_selected_count(iaa_page, iaa_uploader, selected):
    _render(iaa_page, _modal(selected=selected))

    with pytest.raises(RuntimeError):
        iaa_uploader._confirm_iaa_materials(iaa_page)

    _assert_no_actions(iaa_page)
    assert iaa_page.locator("#target").is_visible()


@pytest.mark.parametrize(
    "controls,setup",
    [
        ('<input id="native" type="checkbox" checked>', ""),
        ('<input id="native" type="checkbox">', "document.getElementById('native').indeterminate = true;"),
        ('<span role="checkbox" aria-checked="true">素材</span>', ""),
        ('<span role="checkbox" aria-checked="mixed">素材</span>', ""),
        ('<span role="checkbox">素材</span>', ""),
    ],
    ids=["native-checked", "native-indeterminate", "aria-checked", "aria-mixed", "aria-unknown"],
)
def test_rejects_preselected_or_indeterminate_materials_even_when_summary_is_zero(
    iaa_page, iaa_uploader, controls, setup
):
    _render(iaa_page, _modal(controls=controls), setup=setup)
    before = iaa_page.locator("#target").evaluate(
        "element => [...element.querySelectorAll('input,[role=checkbox]')].map(control => "
        "({checked: control.checked, indeterminate: control.indeterminate, aria: control.getAttribute('aria-checked')}))"
    )

    with pytest.raises(RuntimeError):
        iaa_uploader._confirm_iaa_materials(iaa_page)

    _assert_no_actions(iaa_page)
    assert iaa_page.locator("#target").evaluate(
        "element => [...element.querySelectorAll('input,[role=checkbox]')].map(control => "
        "({checked: control.checked, indeterminate: control.indeterminate, aria: control.getAttribute('aria-checked')}))"
    ) == before


def test_duplicate_visible_titles_are_rejected_without_clicking(iaa_page, iaa_uploader):
    extra = f'<section role="dialog"><h2>{TITLE}</h2><button data-unrelated-confirm>确认</button></section>'
    _render(iaa_page, _modal(), extra=extra)

    with pytest.raises(RuntimeError):
        iaa_uploader._confirm_iaa_materials(iaa_page)

    _assert_no_actions(iaa_page)


@pytest.mark.parametrize(
    "buttons",
    [
        '<button data-target-confirm>确认</button><button data-target-confirm>确认</button>',
        '<button data-target-confirm disabled>确认</button>',
        '<button data-target-confirm>确认其他事项</button>',
    ],
    ids=["duplicate", "disabled", "not-exact"],
)
def test_ambiguous_disabled_or_nonexact_confirm_button_is_rejected(
    iaa_page, iaa_uploader, buttons
):
    _render(iaa_page, _modal(buttons=buttons))

    with pytest.raises(RuntimeError):
        iaa_uploader._confirm_iaa_materials(iaa_page)

    _assert_no_actions(iaa_page)


@pytest.mark.parametrize(
    "changes",
    [
        {"success": ""},
        {"selected": ""},
        {"attributes": ""},
    ],
    ids=["missing-upload-signature", "missing-selected-signature", "unknown-container"],
)
def test_incomplete_signature_or_unknown_container_fails_closed(
    iaa_page, iaa_uploader, changes
):
    _render(iaa_page, _modal(**changes))

    with pytest.raises(RuntimeError):
        iaa_uploader._confirm_iaa_materials(iaa_page)

    _assert_no_actions(iaa_page)


def test_waits_for_modal_to_disappear_after_single_confirm(iaa_page, iaa_uploader):
    _render(iaa_page, _modal(), close_delay=100)

    assert iaa_uploader._confirm_iaa_materials(iaa_page) is True

    _assert_only_target_confirm(iaa_page)
    assert iaa_page.locator("#target").count() == 0


def test_confirmation_that_never_closes_is_not_reported_as_complete(
    iaa_page, iaa_uploader
):
    _render(iaa_page, _modal(), close_delay=None)
    iaa_uploader.confirmation_timeout_seconds = 0.15

    with pytest.raises((RuntimeError, TimeoutError)):
        iaa_uploader._confirm_iaa_materials(iaa_page)

    _assert_only_target_confirm(iaa_page)
    assert iaa_page.locator("#target").is_visible()


def test_title_disappearing_does_not_count_as_modal_dismissal(iaa_page, iaa_uploader):
    _render(
        iaa_page,
        _modal(),
        close_delay=None,
        setup="document.querySelector('[data-target-confirm]').addEventListener('click', () => document.querySelector('#target h2').remove());",
    )
    iaa_uploader.confirmation_timeout_seconds = 0.15

    with pytest.raises(TimeoutError):
        iaa_uploader._confirm_iaa_materials(iaa_page)

    _assert_only_target_confirm(iaa_page)
    assert iaa_page.locator("#target").is_visible()


def test_cancel_during_actionability_wait_does_not_click_later(iaa_page, iaa_uploader):
    _render(
        iaa_page,
        _modal(),
        setup="""
            const cover = document.createElement('div');
            cover.id = 'cover';
            cover.style.cssText = 'position:fixed;inset:0;z-index:99999;background:white';
            document.body.appendChild(cover);
            setTimeout(() => cover.remove(), 500);
        """,
    )
    timer = threading.Timer(0.15, iaa_uploader.cancel)
    timer.start()
    try:
        with pytest.raises(UploadCancelled):
            iaa_uploader._confirm_iaa_materials(iaa_page)
    finally:
        timer.cancel()
        timer.join()

    _assert_no_actions(iaa_page)
    assert iaa_page.locator("#target").is_visible()


def test_selection_changing_during_actionability_wait_is_not_confirmed(iaa_page, iaa_uploader):
    _render(
        iaa_page,
        _modal(),
        setup="""
            const cover = document.createElement('div');
            cover.style.cssText = 'position:fixed;inset:0;z-index:99999;background:white';
            document.body.appendChild(cover);
            setTimeout(() => document.getElementById('native').checked = true, 100);
            setTimeout(() => cover.remove(), 250);
        """,
    )

    with pytest.raises(RuntimeError):
        iaa_uploader._confirm_iaa_materials(iaa_page)

    _assert_no_actions(iaa_page)
    assert iaa_page.locator("#native").is_checked()


def test_cancellation_before_confirmation_preserves_modal_and_selections(
    iaa_page, iaa_uploader
):
    _render(iaa_page, _modal())
    iaa_uploader.cancel()

    with pytest.raises(UploadCancelled):
        iaa_uploader._confirm_iaa_materials(iaa_page)

    _assert_no_actions(iaa_page)
    assert iaa_page.locator("#target").is_visible()


def test_cancellation_while_waiting_for_dismissal_interrupts_without_reclicking(
    iaa_page, iaa_uploader
):
    _render(
        iaa_page,
        _modal(),
        close_delay=None,
        setup="document.querySelector('[data-target-confirm]').addEventListener('click', () => console.log('cancel-after-confirm'));",
    )
    iaa_page.on(
        "console",
        lambda message: iaa_uploader.cancel() if message.text == "cancel-after-confirm" else None,
    )

    with pytest.raises(UploadCancelled):
        iaa_uploader._confirm_iaa_materials(iaa_page)

    _assert_only_target_confirm(iaa_page)
    assert iaa_page.locator("#target").is_visible()


def test_cancellation_while_waiting_for_optional_modal_interrupts_detection(
    iaa_page, iaa_uploader
):
    _render(
        iaa_page,
        setup="setTimeout(() => console.log('cancel-detection'), 75);",
    )
    iaa_page.on(
        "console",
        lambda message: iaa_uploader.cancel() if message.text == "cancel-detection" else None,
    )

    with pytest.raises(UploadCancelled):
        iaa_uploader._confirm_iaa_materials(iaa_page, timeout_ms=500)

    _assert_no_actions(iaa_page)


def _completed_upload_drawer(names):
    count = len(names)
    labels = [f"全部({count})", f"已上传({count})", "上传失败(0)", "上传中(0)"]
    return (
        '<section id="target" role="dialog"><h2>本地上传</h2><nav>'
        + "".join(f"<span>{label}</span>" for label in labels)
        + "</nav>"
        + "".join(f"<div><span>{escape(name)}</span><button>删除</button></div>" for name in names)
        + f'<footer>已选择{count}/10<button data-target-confirm>确定</button></footer></section>'
    )


@pytest.mark.parametrize("names", [["快速完成.mp4"], ["快速完成.mp4", "第二个.mp4"]])
def test_all_uploaded_summary_accepts_fast_upload_without_progress(
    iaa_page, iaa_uploader, tmp_path, names
):
    _render(iaa_page, _completed_upload_drawer(names))

    assert iaa_uploader._dialog_all_uploaded(iaa_page, [tmp_path / name for name in names]) is True

    _assert_no_actions(iaa_page)


@pytest.mark.parametrize(
    "old,new,extra",
    [
        ("<nav><span>全部(1)</span><span>已上传(1)</span><span>上传失败(0)</span><span>上传中(0)</span></nav>", "", ""),
        ("上传中(0)", "", ""),
        ("全部(1)", "全部(2)", ""),
        ("已上传(1)", "已上传(0)", ""),
        ("上传失败(0)", "上传失败(1)", ""),
        ("上传中(0)", "上传中(1)", ""),
        ("本地上传", "", ""),
        ("本地上传", "本地上传中", ""),
        ("快速完成.mp4", "", ""),
        ("", "", "<h2>本地上传</h2>"),
    ],
    ids=[
        "missing-summary", "partial-summary", "total-mismatch", "upload-incomplete",
        "upload-failed", "upload-active", "missing-title", "nonexact-title", "missing-file",
        "duplicate-title",
    ],
)
def test_all_uploaded_summary_rejects_incomplete_or_ambiguous_visible_evidence(
    iaa_page, iaa_uploader, tmp_path, old, new, extra
):
    drawer = _completed_upload_drawer(["快速完成.mp4"])
    _render(iaa_page, drawer.replace(old, new, 1) if old else drawer, extra=extra)

    assert iaa_uploader._dialog_all_uploaded(iaa_page, [tmp_path / "快速完成.mp4"]) is False

    _assert_no_actions(iaa_page)


def test_all_uploaded_summary_ignores_hidden_duplicate_evidence(iaa_page, iaa_uploader, tmp_path):
    drawer = _completed_upload_drawer(["快速完成.mp4"])
    _render(iaa_page, drawer, extra=f'<aside style="display:none">{drawer}</aside>')

    assert iaa_uploader._dialog_all_uploaded(iaa_page, [tmp_path / "快速完成.mp4"]) is True

    _assert_no_actions(iaa_page)


def test_wait_for_dialog_uploads_finishes_immediate_summary_and_preserves_originals(
    iaa_page, iaa_uploader, tmp_path
):
    videos = [tmp_path / "快速完成.mp4", tmp_path / "第二个.mp4"]
    for video in videos:
        video.write_bytes(b"original-video-bytes")
    _render(iaa_page, _completed_upload_drawer([video.name for video in videos]))
    iaa_uploader.timeout_seconds = 0.05

    result = iaa_uploader._wait_for_dialog_uploads(iaa_page, videos)

    assert result.succeeded == tuple(videos)
    assert result.failed == ()
    assert [video.read_bytes() for video in videos] == [b"original-video-bytes"] * 2
    _assert_no_actions(iaa_page)


def test_all_uploaded_summary_rejects_expected_file_only_on_background_page(iaa_page, iaa_uploader, tmp_path):
    _render(iaa_page, _completed_upload_drawer(["另一个文件.mp4"]),
            extra='<main><span>快速完成.mp4</span></main>')

    assert iaa_uploader._dialog_all_uploaded(iaa_page, [tmp_path / "快速完成.mp4"]) is False
    _assert_no_actions(iaa_page)


@pytest.mark.parametrize("extra", ["<span>全部(1)</span>", "<span>已上传(1)</span>",
                                  "<span>上传失败(0)</span>", "<span>上传中(0)</span>",
                                  "<main><span>快速完成.mp4</span></main>"])
def test_all_uploaded_summary_ignores_evidence_outside_recognized_drawer(iaa_page, iaa_uploader, tmp_path, extra):
    _render(iaa_page, _completed_upload_drawer(["快速完成.mp4"]), extra=extra)
    assert iaa_uploader._dialog_all_uploaded(iaa_page, [tmp_path / "快速完成.mp4"]) is True
    _assert_no_actions(iaa_page)


def test_all_uploaded_summary_recognizes_observed_production_drawer_class(iaa_page, iaa_uploader, tmp_path):
    drawer = _completed_upload_drawer(["快速完成.mp4"]).replace('role="dialog"', 'class="material-center-v2-drawer"')
    _render(iaa_page, drawer)
    assert iaa_uploader._dialog_all_uploaded(iaa_page, [tmp_path / "快速完成.mp4"]) is True


def test_all_uploaded_summary_rejects_unknown_container(iaa_page, iaa_uploader, tmp_path):
    _render(iaa_page, _completed_upload_drawer(["快速完成.mp4"]).replace('role="dialog"', ''))
    assert iaa_uploader._dialog_all_uploaded(iaa_page, [tmp_path / "快速完成.mp4"]) is False


@pytest.mark.parametrize("markers,expected", [
    (["7000000000000000001"], True), (["7000000000000000002"], False),
    (["7000000000000000001", "7000000000000000001"], False),
])
def test_receipt_id_readback_searches_id_and_requires_unique_visible_record(iaa_page, tmp_path, markers, expected):
    target = "https://ad.oceanengine.com/material_center/management/video?aadvid=1234567890123456#source=ad_navigator"
    html = '<input placeholder="输入视频名称或ID后回车搜索" onkeydown="if(event.key===\'Enter\') document.getElementById(\'rows\').hidden=false">'
    html += '<section id="rows" hidden><span>平台保留的原名.mp4</span>'
    html += "".join(f'<p>ID: {value}</p>' for value in markers) + '</section>'
    iaa_page.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html; charset=utf-8", body=html))
    iaa_page.goto(target)
    uploader = OceanEngineUploader(Settings(material_url=target))
    source = tmp_path / "改名后的文件.mp4"
    source.write_bytes(b"abc")
    uploader._prepare_confirm_receipts(iaa_page, [source])
    try:
        assert uploader._search_material_id(iaa_page, "7000000000000000001") is expected
        assert iaa_page.locator("input").input_value() == "7000000000000000001"
    finally:
        uploader._stop_receipt_tracking()


@pytest.mark.parametrize("current", [
    "https://ad.oceanengine.com/material_center/management/video?aadvid=1872774218798096",
    "https://example.test/material_center/management/video?aadvid=1234567890123456",
    "https://ad.oceanengine.com/other?aadvid=1234567890123456",
])
def test_receipt_id_readback_rejects_changed_account_or_destination(iaa_page, tmp_path, current):
    iaa_page.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html; charset=utf-8", body='<input placeholder="视频名称">'))
    iaa_page.goto(current)
    uploader = OceanEngineUploader(Settings(material_url="https://ad.oceanengine.com/material_center/management/video?aadvid=1234567890123456"))
    source = tmp_path / "改名后的文件.mp4"
    source.write_bytes(b"abc")
    uploader._prepare_confirm_receipts(iaa_page, [source])
    try:
        with pytest.raises(RuntimeError, match="账号变化"):
            uploader._search_material_id(iaa_page, "7000000000000000001")
        assert iaa_page.locator("input").input_value() == ""
    finally:
        uploader._stop_receipt_tracking()
