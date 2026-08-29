# API 投稿 2.0 桌面端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an isolated Windows desktop application that claims Sheet1 posting tasks and distributes one task at a time to ordered, quota-limited Qianchuan projects.

**Architecture:** `E:\自动化\api投稿2.0` is a self-contained Python application. A Tkinter desktop process manages local configuration, account/project catalogues, named posting plans, worker lifecycle, and status. A background worker reads only Feishu `Sheet1`, claims one unposted row, resolves an exactly named video in the selected advertiser material library, posts it to the selected project, and persists all state in a local SQLite database.

**Tech Stack:** Python 3.13, Tkinter/ttk, SQLite (`sqlite3`), HTTP (`urllib.request`), `unittest`, Windows batch and PowerShell scripts.

## Global Constraints

- Create files only under `E:\自动化\api投稿2.0`.
- Do not modify, copy runtime configuration from, or write to `E:\自动化\api` or `E:\自动化\api上传投稿`.
- Fixed source is the Feishu submission sheet named `Sheet1`; upload folders and source-book sheets are out of scope.
- One unposted Sheet1 row creates at most one posting unit.
- Search video material by exact book title only; select the newest exact-title material.
- All selected projects are processed in saved drag-and-drop order.
- Each project has an independent daily quota, reset at local `00:00`.
- A temporary failure is retried immediately once, then one hour later; after three attempts it is terminal and must not block following rows.
- Use only standard-library runtime dependencies. Do not add a web server or third-party UI framework.
- This directory is not a Git repository. Record validation commands in logs instead of requiring commits.

## Planned File Structure

- `app/desktop_posting/models.py`: immutable data types for accounts, projects, plan entries, plans, tasks, and status snapshots.
- `app/desktop_posting/storage.py`: isolated SQLite schema and state reads/writes.
- `app/desktop_posting/settings.py`: local settings, Qianchuan callback import, token refresh, and Feishu connection settings.
- `app/desktop_posting/qianchuan_client.py`: account/project/material/promotion API calls and temporary-error classification.
- `app/desktop_posting/feishu_client.py`: Sheet1 discovery, header validation, read/claim/update calls with network retries.
- `app/desktop_posting/plans.py`: plan validation, quota selection, daily reset, ordered project transition.
- `app/desktop_posting/posting_service.py`: one-row posting workflow with exact material resolution and retry bookkeeping.
- `app/desktop_posting/worker.py`: stop-aware long-running loop and heartbeat.
- `app/desktop_posting/desktop_app.py`: Tkinter notebook UI and background worker controls.
- `app/desktop_posting/main.py`: application entry point.
- `scripts/run_python.ps1`, `scripts/start_desktop.ps1`, `scripts/stop_worker.ps1`: local launch helpers.
- `启动桌面版.bat`, `停止投稿.bat`, `一键自检.bat`: Windows entry points.
- `tests/test_storage.py`, `tests/test_plans.py`, `tests/test_feishu_client.py`, `tests/test_posting_service.py`, `tests/test_worker.py`, `tests/test_desktop_app.py`: unit tests.
- `config/`, `data/`, `logs/`: generated at runtime beneath the new root only.

### Task 1: Create the isolated application foundation

**Files:**
- Create: `app/desktop_posting/__init__.py`
- Create: `app/desktop_posting/models.py`
- Create: `app/desktop_posting/storage.py`
- Create: `tests/test_storage.py`

**Interfaces:**
- Produces `StateStore(base_dir: Path)`, `ProjectRef`, `PlanEntry`, `PostingPlan`, and `TaskAttempt`.
- `StateStore.initialize() -> None` is idempotent and creates only `base_dir/data/state.db`.

- [ ] **Step 1: Write the failing storage test**

```python
def test_initialize_creates_only_local_database(tmp_path):
    store = StateStore(tmp_path)
    store.initialize()
    assert (tmp_path / "data" / "state.db").exists()
    assert store.list_plans() == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_storage.StateStoreTests.test_initialize_creates_only_local_database -v`

Expected: FAIL because `desktop_posting.storage` does not exist.

- [ ] **Step 3: Implement the minimal models and SQLite schema**

```python
@dataclass(frozen=True)
class ProjectRef:
    advertiser_id: str
    advertiser_name: str
    project_id: str
    project_name: str

class StateStore:
    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA_SQL)
```

Create tables for `plans`, `plan_entries`, `daily_project_counts`, `task_attempts`, `runtime_state`, and `catalog_projects`. Store timestamps as integer epoch seconds and daily counters by local `YYYY-MM-DD`.

- [ ] **Step 4: Run the storage test**

Run: `python -m unittest tests.test_storage -v`

Expected: PASS.

- [ ] **Step 5: Record validation**

Append the command and result to `logs/development-validation.log`; do not create a Git commit because this directory is not a repository.

### Task 2: Implement local settings and callback authorization import

**Files:**
- Create: `app/desktop_posting/settings.py`
- Create: `tests/test_settings.py`
- Modify: `app/desktop_posting/storage.py`

**Interfaces:**
- Consumes `StateStore` from Task 1.
- Produces `AppSettings`, `import_callback_url(settings, callback_url) -> TokenStatus`, and `refresh_access_token(settings) -> TokenStatus`.

- [ ] **Step 1: Write failing tests for callback parsing and local save**

```python
def test_import_callback_saves_only_new_root_token_file(tmp_path):
    settings = AppSettings(qianchuan_app_id="123", qianchuan_secret="secret")
    status = import_callback_url(settings, "https://callback/?auth_code=abc")
    assert status.access_token
    assert (tmp_path / "config" / "tokens.json").exists()
```

Mock the exchange request. Add a test that missing `auth_code` raises `ValueError("callback URL does not contain auth_code")`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_settings -v`

Expected: FAIL because the settings module does not exist.

- [ ] **Step 3: Implement settings persistence and token refresh**

```python
@dataclass
class AppSettings:
    base_dir: Path
    qianchuan_app_id: str = ""
    qianchuan_secret: str = ""
    feishu_app_id: str = ""
    feishu_secret: str = ""
    submission_sheet_url: str = ""

def token_path(base_dir: Path) -> Path:
    return base_dir / "config" / "tokens.json"
```

Persist non-secret display settings in `config/settings.json`; persist tokens in `config/tokens.json`; never read another program's config directory. Refresh before every API cycle when the access token expires within five minutes.

- [ ] **Step 4: Run settings tests**

Run: `python -m unittest tests.test_settings -v`

Expected: PASS.

- [ ] **Step 5: Record validation**

Append the passing command and result to `logs/development-validation.log`.

### Task 3: Discover accounts/projects and manage saved posting plans

**Files:**
- Create: `app/desktop_posting/qianchuan_client.py`
- Create: `app/desktop_posting/plans.py`
- Create: `tests/test_plans.py`
- Create: `tests/test_qianchuan_client.py`

**Interfaces:**
- Produces `list_advertisers(access_token) -> list[Account]`, `list_projects(access_token, advertiser_id) -> list[ProjectRef]`.
- Produces `save_plan(store, plan)`, `duplicate_plan(store, plan_id, name)`, and `choose_active_entry(store, plan_id, today) -> PlanEntry | None`.

- [ ] **Step 1: Write failing plan tests**

```python
def test_quota_switches_to_next_ordered_project(tmp_path):
    plan = make_plan([entry("p1", order=0, limit=2), entry("p2", order=1, limit=3)])
    store.save_plan(plan)
    store.increment_project_count(plan.id, "p1", "2026-07-10")
    store.increment_project_count(plan.id, "p1", "2026-07-10")
    assert choose_active_entry(store, plan.id, "2026-07-10").project_id == "p2"
```

Add tests for drag-order persistence, plan duplication, disabled entries, and all-projects-full returning `None`.

- [ ] **Step 2: Run the plan tests to verify they fail**

Run: `python -m unittest tests.test_plans -v`

Expected: FAIL because plan services do not exist.

- [ ] **Step 3: Implement catalogue refresh and plan selection**

```python
def choose_active_entry(store: StateStore, plan_id: str, today: str) -> PlanEntry | None:
    for entry in store.list_plan_entries(plan_id):
        if entry.enabled and store.project_count(plan_id, entry.project_id, today) < entry.daily_limit:
            return entry
    return None
```

Refresh catalogue data from the Qianchuan advertiser and project APIs. Persist IDs and display names in the new local database. Reject an enabled plan entry with a non-positive limit. A missing or unauthorised project remains visible as invalid and is skipped with a runtime event.

- [ ] **Step 4: Run catalogue and plan tests**

Run: `python -m unittest tests.test_qianchuan_client tests.test_plans -v`

Expected: PASS.

- [ ] **Step 5: Record validation**

Append the passing command and result to `logs/development-validation.log`.

### Task 4: Implement reliable Sheet1 reading, validation, and claims

**Files:**
- Create: `app/desktop_posting/feishu_client.py`
- Create: `tests/test_feishu_client.py`

**Interfaces:**
- Produces `SubmissionRow`, `load_sheet1(settings) -> tuple[str, list[str], list[list[str]]]`, `find_claimable_row(rows, host, now) -> SubmissionRow | None`, and `claim_row(...) -> bool`.
- Requires Sheet1 headers containing `书名`, `标签`, `启动页`, `程序链接`, `投稿状态`, and claim columns.

- [ ] **Step 1: Write failing tests for fixed Sheet1 and claim recovery**

```python
def test_only_sheet1_is_selected_when_multiple_sheets_exist():
    assert resolve_sheet_id(sheets=[{"title": "其他"}, {"title": "Sheet1", "sheet_id": "s1"}]) == "s1"

def test_expired_claim_becomes_claimable_again():
    row = {"领取状态": "已领取", "领取时间": "2026-07-10 00:00:00"}
    assert is_claimable(row, now="2026-07-10 01:00:01")
```

- [ ] **Step 2: Run Feishu tests to verify they fail**

Run: `python -m unittest tests.test_feishu_client -v`

Expected: FAIL because the Feishu client does not exist.

- [ ] **Step 3: Implement bounded reads and retryable requests**

```python
SHEET_TITLE = "Sheet1"
READ_RANGE = "A1:BZ5000"
NETWORK_RETRY_DELAYS = (0, 3, 10)
```

Use a cached Sheet1 ID under `data/sheet_ids.json`. Never request `ZZ5000`; use the bounded BZ range. Claim a row by writing host, batch ID, and timestamp, then read the row back to confirm ownership. Use retries for timeout, SSL EOF, reset/closed connection, and HTTP 5xx errors.

- [ ] **Step 4: Run Feishu tests**

Run: `python -m unittest tests.test_feishu_client -v`

Expected: PASS.

- [ ] **Step 5: Record validation**

Append the passing command and result to `logs/development-validation.log`.

### Task 5: Build one-task posting with exact material selection and retries

**Files:**
- Create: `app/desktop_posting/posting_service.py`
- Create: `tests/test_posting_service.py`
- Modify: `app/desktop_posting/qianchuan_client.py`

**Interfaces:**
- Produces `run_one_task(settings, store, plan_id, now) -> PostResult`.
- `PostResult` has `status` in `posted`, `no_task`, `all_projects_full`, `retry_scheduled`, `terminal_failure`, `project_invalid`.

- [ ] **Step 1: Write failing posting tests**

```python
def test_exact_title_material_uses_latest_created_item():
    items = [{"filename": "书A", "create_time": 10}, {"filename": "书A", "create_time": 20}]
    assert select_exact_material(items, "书A")["create_time"] == 20

def test_failure_of_one_row_does_not_prevent_next_row():
    first = run_one_task(..., now=100)
    second = run_one_task(..., now=101)
    assert first.status == "retry_scheduled"
    assert second.status == "posted"
```

Add tests for immediate temporary retry, one-hour retry scheduling, third failure terminal state, quota increment only after success, and no write when material title has no exact match.

- [ ] **Step 2: Run posting tests to verify they fail**

Run: `python -m unittest tests.test_posting_service -v`

Expected: FAIL because the posting service does not exist.

- [ ] **Step 3: Implement the one-row flow**

```python
def run_one_task(settings, store, plan_id, now):
    entry = choose_active_entry(store, plan_id, local_date(now))
    if entry is None:
        return PostResult("all_projects_full")
    row = claim_next_due_row(...)
    if row is None:
        return PostResult("no_task")
    return post_claimed_row(settings, store, entry, row, now)
```

Search only the selected entry's advertiser material library. Require `filename == book_name`; sort matches by API creation time descending. Create one promotion by copying the selected project template and filling Sheet1 title, tag, start page, generated program link, and enabled operation. On success update the row as posted and increment only the selected project's counter.

- [ ] **Step 4: Run posting tests**

Run: `python -m unittest tests.test_posting_service -v`

Expected: PASS.

- [ ] **Step 5: Record validation**

Append the passing command and result to `logs/development-validation.log`.

### Task 6: Add a stop-aware 7x24 worker and runtime status

**Files:**
- Create: `app/desktop_posting/worker.py`
- Create: `tests/test_worker.py`
- Modify: `app/desktop_posting/storage.py`

**Interfaces:**
- Produces `PostingWorker(base_dir, plan_id, event_sink)`, `start()`, `request_stop()`, `status() -> RuntimeStatus`.
- Worker writes `data/heartbeat_post.txt`, `data/worker.pid`, and `data/STOP` only beneath the new root.

- [ ] **Step 1: Write failing worker tests**

```python
def test_worker_stops_before_claiming_another_row(tmp_path):
    worker = PostingWorker(tmp_path, "plan-1", event_sink=list.append)
    worker.request_stop()
    assert worker.run_cycle() == "stopped"

def test_daily_reset_uses_local_midnight():
    assert reset_needed("2026-07-10", datetime(2026, 7, 11, 0, 0))
```

- [ ] **Step 2: Run worker tests to verify they fail**

Run: `python -m unittest tests.test_worker -v`

Expected: FAIL because the worker module does not exist.

- [ ] **Step 3: Implement loop, heartbeat, and reset**

```python
while not self.should_stop():
    self.store.reset_daily_counts_if_date_changed(local_date(time.time()))
    result = run_one_task(self.settings, self.store, self.plan_id, time.time())
    self.store.write_heartbeat("post", time.time())
    self.sleep_interruptibly(result.next_delay_seconds)
```

When all projects are full, wait until the next local midnight or stop request. When no task is available, poll Sheet1 every 30 seconds. Continue immediately with the next claim after a terminal task failure.

- [ ] **Step 4: Run worker tests**

Run: `python -m unittest tests.test_worker -v`

Expected: PASS.

- [ ] **Step 5: Record validation**

Append the passing command and result to `logs/development-validation.log`.

### Task 7: Build the Tkinter desktop interface

**Files:**
- Create: `app/desktop_posting/desktop_app.py`
- Create: `app/desktop_posting/main.py`
- Create: `tests/test_desktop_app.py`

**Interfaces:**
- `DesktopApp(root: tk.Tk, base_dir: Path)` creates tabs `授权`, `账户项目`, `投稿方案`, `运行状态`.
- `PlanEditor.move_entry(entry_id, delta: int) -> None` persists order after drag/drop.

- [ ] **Step 1: Write failing UI model/controller tests without a visible window**

```python
def test_move_entry_reorders_and_saves(tmp_path):
    editor = PlanEditor(store, plan_id="p")
    editor.move_entry("entry-2", -1)
    assert [item.project_id for item in store.list_plan_entries("p")] == ["project-2", "project-1"]
```

Add tests that Start is disabled without an active valid plan and that Stop calls `request_stop()`.

- [ ] **Step 2: Run UI tests to verify they fail**

Run: `python -m unittest tests.test_desktop_app -v`

Expected: FAIL because the desktop module does not exist.

- [ ] **Step 3: Implement the four tabs and non-blocking UI updates**

```python
root.after(1000, self.refresh_runtime_view)
tree.bind("<ButtonPress-1>", self.begin_drag)
tree.bind("<ButtonRelease-1>", self.finish_drag)
```

Use `ttk.Notebook`, `ttk.Treeview`, buttons with familiar text commands, numeric `Spinbox` quota inputs, and a read-only event log. Run API refresh and worker startup on background threads; update widgets only through `root.after`. Do not use modal prompts during worker execution.

- [ ] **Step 4: Run UI tests**

Run: `python -m unittest tests.test_desktop_app -v`

Expected: PASS.

- [ ] **Step 5: Manual UI verification**

Run: `python -m desktop_posting.main --base-dir "E:\自动化\api投稿2.0"`

Expected: A desktop window opens; it can create a plan, reorder projects, save, and display an idle state without accessing old program paths.

### Task 8: Add Windows launchers, health check, and end-to-end verification

**Files:**
- Create: `scripts/run_python.ps1`
- Create: `scripts/start_desktop.ps1`
- Create: `scripts/stop_worker.ps1`
- Create: `启动桌面版.bat`
- Create: `停止投稿.bat`
- Create: `一键自检.bat`
- Create: `tests/test_launchers.py`
- Modify: `docs/superpowers/specs/2026-07-10-api-posting-desktop-design.md`

**Interfaces:**
- `一键自检.bat` returns non-zero for missing Python, configuration, token, Sheet1, or no catalogue projects.
- `停止投稿.bat` requests stop without killing unrelated Python processes.

- [ ] **Step 1: Write failing launcher and health-check tests**

```python
def test_health_check_rejects_missing_sheet1(tmp_path):
    result = run_health_check(tmp_path, sheets=[{"title": "其他"}])
    assert result.ok is False
    assert "Sheet1" in result.errors[0]
```

- [ ] **Step 2: Run launcher tests to verify they fail**

Run: `python -m unittest tests.test_launchers -v`

Expected: FAIL because health-check and launcher files do not exist.

- [ ] **Step 3: Implement local-only launch scripts and health check**

```bat
@echo off
set ROOT=%~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\start_desktop.ps1" -BaseDir "%ROOT%."
pause
```

The health check must verify Python, local config, refresh token, Qianchuan advertiser/project API access, fixed Sheet1 headers, a valid selected plan, write access to the new `data` directory, and free disk space for logs. It must never write to Feishu or create promotions.

- [ ] **Step 4: Run the complete automated suite**

Run: `python -m unittest discover -s tests -v`

Expected: PASS with all desktop-posting tests green.

- [ ] **Step 5: Run controlled end-to-end verification**

Use a dedicated test plan with one project quota set to `1`, one explicitly prepared Sheet1 test row, and one exact-title test material. Verify: one claim, one unit creation, row marked posted, counter equals `1`, next project selected after quota, and no file change under either old program directory.

- [ ] **Step 6: Record release evidence**

Write `docs/verification-YYYY-MM-DD.md` with the commands, results, affected new-root files, and SHA-256 directory manifests for `E:\自动化\api` and `E:\自动化\api上传投稿` captured before and after implementation.

## Plan Self-Review

Coverage mapping:

- Independent directory and local-only state: Tasks 1, 2, 8.
- Callback import and account/project detection: Tasks 2 and 3.
- Multi-plan project selection, ordering, and limits: Tasks 3 and 7.
- Fixed Sheet1, one row/one video, exact-title latest-material selection: Tasks 4 and 5.
- Per-project quota transition and midnight reset: Tasks 3 and 6.
- Failure isolation and retry policy: Task 5 and Task 6.
- Windows desktop controls and 7x24 operation: Tasks 6, 7, and 8.

No incomplete or deferred implementation placeholders remain. Public interfaces introduced by each task are named in that task and consumed only by later tasks.
