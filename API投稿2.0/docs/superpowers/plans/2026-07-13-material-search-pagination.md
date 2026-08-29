# Material Search Pagination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Search the assigned account's Qianchuan material library page by page until a matching video is found, the API has no further pages, or two minutes elapse.

**Architecture:** Extend the standalone posting client's `search_materials` function. It will retain the current account boundary, issue sequential page requests, prefer an exact filename match, and use a contains-name fallback on each page. Existing `run_once` error handling will mark the row for retry when no material is returned, preserving the existing locked account and project.

**Tech Stack:** Python 3.13 standard library, `unittest`, Qianchuan Open API.

## Global Constraints

- Modify only `E:\自动化\api投稿2.0`; do not modify the older posting or upload programs.
- Search only the task's assigned advertiser account.
- Stop pagination at the first match, API page exhaustion, or 120 seconds.
- Keep existing project quota, retry, and task-target lock behavior unchanged.

---

### Task 1: Specify paginated material lookup

**Files:**
- Modify: `E:\自动化\api投稿2.0\tests\test_posting_service.py`
- Modify: `E:\自动化\api投稿2.0\app\desktop_posting\qianchuan_client.py`

**Interfaces:**
- Consumes: `search_materials(access_token, advertiser_id, book_name)`.
- Produces: a newest-first list of exact matches, otherwise contains matches, otherwise an empty list.

- [ ] **Step 1: Write failing tests**

Add tests that patch `_get` and assert that `search_materials`:

```python
def test_search_materials_reads_later_page_until_exact_match():
    pages = [
        {"list": [{"filename": "other.mp4"}], "page_info": {"total_page": 2}},
        {"list": [{"filename": "book.mp4", "create_time": 2}], "page_info": {"total_page": 2}},
    ]
    with patch("desktop_posting.qianchuan_client._get", side_effect=pages) as get:
        assert search_materials("token", "account", "book") == [pages[1]["list"][0]]
    assert [call.kwargs["params"]["page"] for call in get.call_args_list] == [1, 2]
```

```python
def test_search_materials_returns_contains_match_when_no_exact_match():
    response = {"list": [{"filename": "book_1.mp4", "create_time": 2}], "page_info": {"total_page": 1}}
    with patch("desktop_posting.qianchuan_client._get", return_value=response):
        assert search_materials("token", "account", "book") == response["list"]
```

```python
def test_search_materials_stops_after_two_minutes(monkeypatch):
    with patch("desktop_posting.qianchuan_client._get", return_value={"list": [{"filename": "other.mp4"}]}) as get:
        with patch("desktop_posting.qianchuan_client.time.monotonic", side_effect=[0, 121]):
            assert search_materials("token", "account", "book") == []
    assert get.call_count == 1
```

- [ ] **Step 2: Run the focused test file and confirm the new later-page test fails**

Run:

```powershell
Set-Location 'E:\自动化\api投稿2.0'
python -m unittest tests.test_posting_service -v
```

Expected: the later-page and contains-match tests fail because the current implementation only requests page 1 and rejects contains matches.

- [ ] **Step 3: Implement sequential lookup**

Replace the single `_get` call in `search_materials` with a loop that starts at page 1, checks `time.monotonic() - started_at < 120`, stops when `page_info.total_page` is reached or the API returns an empty list, and returns exact matches before contains matches for each page.

- [ ] **Step 4: Run focused tests**

Run the Task 1 command again.

Expected: all material-search tests pass.

### Task 2: Verify unchanged posting failure behavior

**Files:**
- Test: `E:\自动化\api投稿2.0\tests\test_run_once.py`

**Interfaces:**
- Consumes: `run_once(base_dir)` and empty result from `search_materials`.
- Produces: existing retry result with the locked project preserved.

- [ ] **Step 1: Run the existing retry tests before any posting-flow edit**

Run:

```powershell
Set-Location 'E:\自动化\api投稿2.0'
python -m unittest tests.test_run_once -v
```

Expected: all existing retry and locked-project tests pass without changing production posting-flow code.

- [ ] **Step 2: Run the full verification suite**

Run:

```powershell
Set-Location 'E:\自动化\api投稿2.0'
python -m compileall -q app
python -m unittest discover -s tests -v
```

Expected: compilation succeeds and every test passes.
