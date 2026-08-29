import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
from datetime import date
import time

from .plans import add_plan_entry, auto_proxy_enabled, create_plan, move_entry, project_picker_label, set_auto_proxy_enabled, sync_auto_proxy_plan, sync_auto_proxy_plans, valid_daily_limit
from .qianchuan_client import import_callback, is_access_token_expired_error, list_projects, refresh_if_needed, selected_advertiser_ids, latest_projects_by_name
from .settings import AppSettings, load_settings, save_settings
from .storage import StateStore
from .models import ProjectRef
from .worker import PostingWorker


class DesktopApp:
    def __init__(self, root, base_dir, auto_start=False, embedded=False, on_alert=None):
        self.root, self.base_dir = root, Path(base_dir)
        self.on_alert = on_alert or (lambda _: None)
        self.store = StateStore(self.base_dir); self.store.initialize()
        self.settings = load_settings(self.base_dir)
        if not embedded:
            root.title("API 投稿 2.0"); root.geometry("980x650")
        self.tabs = ttk.Notebook(root); self.tabs.pack(fill="both", expand=True, padx=8, pady=8)
        self._build_auth(); self._build_catalog(); self._build_plan(); self._build_status()
        if auto_start:
            self.tabs.select(3)
            self.root.after(1200, self.start_worker)

    def _build_auth(self):
        tab = ttk.Frame(self.tabs); self.tabs.add(tab, text="授权")
        self.fields = {}
        for row, (key, label) in enumerate((("qianchuan_app_id", "千川 App ID"), ("qianchuan_secret", "千川 Secret"), ("configured_advertiser_ids", "指定账户 ID（逗号分隔）"))):
            ttk.Label(tab, text=label).grid(row=row, column=0, sticky="w", padx=12, pady=6)
            entry = ttk.Entry(tab, width=90, show="*" if "secret" in key else "")
            entry.insert(0, getattr(self.settings, key)); entry.grid(row=row, column=1, sticky="ew", padx=12, pady=6); self.fields[key] = entry
        ttk.Button(tab, text="保存连接设置", command=self.save_connection).grid(row=6, column=1, sticky="w", padx=12, pady=8)
        ttk.Label(tab, text="完整回调链接").grid(row=7, column=0, sticky="nw", padx=12, pady=6)
        self.callback = tk.Text(tab, height=5, width=80); self.callback.grid(row=7, column=1, padx=12, pady=6)
        ttk.Button(tab, text="导入授权", command=self.do_import).grid(row=8, column=1, sticky="w", padx=12, pady=8)

    def save_connection(self):
        values = {key: getattr(self.settings, key) for key in AppSettings.__dataclass_fields__}
        values.update({key: widget.get().strip() for key, widget in self.fields.items()})
        self.settings = AppSettings(**values); save_settings(self.base_dir, self.settings); messagebox.showinfo("完成", "连接设置已保存到本程序目录")

    def set_shared_feishu(self, app_id, secret, sheet_url):
        self.settings.feishu_app_id = app_id
        self.settings.feishu_secret = secret
        self.settings.submission_sheet_url = sheet_url
        save_settings(self.base_dir, self.settings)

    def do_import(self):
        try:
            self.save_connection(); result = import_callback(self.base_dir, self.settings, self.callback.get("1.0", "end").strip()); messagebox.showinfo("授权成功", f"检测到账户 {len(result['advertiser_ids'])} 个")
        except Exception as exc: messagebox.showerror("授权失败", str(exc))

    def _build_catalog(self):
        tab = ttk.Frame(self.tabs); self.tabs.add(tab, text="账户项目")
        ttk.Button(tab, text="检测账户项目", command=self.refresh_catalog).pack(anchor="w", padx=10, pady=8)
        self.catalog = ttk.Treeview(tab, columns=("account", "project_id"), show="tree headings"); self.catalog.heading("#0", text="项目名称"); self.catalog.heading("account", text="账户"); self.catalog.heading("project_id", text="项目 ID"); self.catalog.pack(fill="both", expand=True, padx=10, pady=8)
        ttk.Button(tab, text="将选中项目加入当前方案", command=self.add_selected_project).pack(anchor="w", padx=10, pady=4)

    def refresh_catalog(self):
        try:
            token = refresh_if_needed(self.base_dir, self.settings); self.catalog.delete(*self.catalog.get_children()); self.available_projects = {}
            errors = []
            for advertiser_id in selected_advertiser_ids(self.settings.configured_advertiser_ids, token.get("advertiser_ids")):
                root = self.catalog.insert("", "end", text=f"账户 {advertiser_id}", values=(advertiser_id, ""), open=True)
                try:
                    for item in latest_projects_by_name(list_projects(token["access_token"], advertiser_id)):
                        project = ProjectRef(str(advertiser_id), f"账户 {advertiser_id}", str(item.get("project_id") or item.get("id")), item.get("name", "未命名项目")); label = project_picker_label(project); self.available_projects[label] = project; self.catalog.insert(root, "end", text=project.project_name, values=(advertiser_id, project.project_id))
                except Exception as exc:
                    if is_access_token_expired_error(exc):
                        token = refresh_if_needed(self.base_dir, self.settings, force=True)
                        for item in latest_projects_by_name(list_projects(token["access_token"], advertiser_id)):
                            project = ProjectRef(str(advertiser_id), f"账户 {advertiser_id}", str(item.get("project_id") or item.get("id")), item.get("name", "未命名项目")); label = project_picker_label(project); self.available_projects[label] = project; self.catalog.insert(root, "end", text=project.project_name, values=(advertiser_id, project.project_id))
                        continue
                    self.catalog.item(root, text=f"账户 {advertiser_id}（无项目权限）")
                    errors.append(f"{advertiser_id}: {exc}")
            if errors:
                messagebox.showwarning("部分账户无法检测", "\n".join(errors))
            self.refresh_project_picker()
        except Exception as exc: messagebox.showerror("检测失败", str(exc))

    def _build_plan(self):
        tab = ttk.Frame(self.tabs); self.tabs.add(tab, text="投稿方案")
        top = ttk.Frame(tab); top.pack(fill="x", padx=10, pady=8); ttk.Label(top, text="方案").pack(side="left"); self.plan_box = ttk.Combobox(top, state="readonly", width=18); self.plan_box.pack(side="left", padx=6); self.plan_box.bind("<<ComboboxSelected>>", lambda _: self.select_plan()); ttk.Label(top, text="新方案名称").pack(side="left"); self.plan_name = ttk.Entry(top, width=12); self.plan_name.pack(side="left", padx=6); ttk.Button(top, text="新建", command=self.new_plan).pack(side="left"); ttk.Button(top, text="删除方案", command=self.delete_current_plan).pack(side="left", padx=6)
        speed = ttk.Frame(tab); speed.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(speed, text="投稿速度").pack(side="left")
        self.plan_speed_box = ttk.Combobox(speed, state="readonly", width=18, values=("最快（每条间隔3秒）", "最慢（每条间隔60秒）"))
        self.plan_speed_box.pack(side="left", padx=6)
        self.plan_speed_box.bind("<<ComboboxSelected>>", lambda _: self.save_plan_speed())
        self.auto_proxy = tk.BooleanVar(value=False)
        ttk.Checkbutton(speed, text="自动代理（每日 40，满后 83）", variable=self.auto_proxy, command=self.save_auto_proxy).pack(side="left", padx=12)
        pick = ttk.Frame(tab); pick.pack(fill="x", padx=10, pady=(0, 8)); ttk.Label(pick, text="选择项目").pack(side="left"); self.project_picker = ttk.Combobox(pick, state="readonly", width=55); self.project_picker.pack(side="left", padx=6); ttk.Button(pick, text="加入方案", command=self.add_picked_project).pack(side="left")
        self.plan_entries = ttk.Treeview(tab, columns=("project", "account", "limit"), show="headings"); self.plan_entries.heading("project", text="项目"); self.plan_entries.heading("account", text="账户"); self.plan_entries.heading("limit", text="每日投稿数量"); self.plan_entries.pack(fill="both", expand=True, padx=10, pady=8)
        buttons = ttk.Frame(tab); buttons.pack(fill="x", padx=10); ttk.Button(buttons, text="上移", command=lambda: self.move_selected(-1)).pack(side="left"); ttk.Button(buttons, text="下移", command=lambda: self.move_selected(1)).pack(side="left", padx=4); ttk.Button(buttons, text="移除项目", command=self.remove_selected).pack(side="left", padx=4)
        self.plan_entries.bind("<ButtonPress-1>", self.begin_drag); self.plan_entries.bind("<ButtonRelease-1>", self.finish_drag); self.plan_entries.bind("<Double-1>", self.edit_limit)
        self.active_plan_id = int(self.store.get_state("active_plan_id", "0") or 0) or None
        self.drag_entry_id = None; self.refresh_plan_list(); self.refresh_plan_speed(); self.refresh_auto_proxy()

    def new_plan(self):
        try: self.active_plan_id = create_plan(self.store, self.plan_name.get()); self.store.set_state("active_plan_id", self.active_plan_id); self.refresh_plan_list(); self.refresh_entries(); messagebox.showinfo("完成", "方案已创建")
        except Exception as exc: messagebox.showerror("创建失败", str(exc))

    def refresh_plan_list(self):
        rows = self.store.list_plans(); self.plan_lookup = {row[1]: row[0] for row in rows}; self.plan_box["values"] = list(self.plan_lookup)
        if self.active_plan_id:
            for name, plan_id in self.plan_lookup.items():
                if plan_id == self.active_plan_id: self.plan_box.set(name)

    def select_plan(self):
        self.active_plan_id = self.plan_lookup.get(self.plan_box.get()); self.store.set_state("active_plan_id", self.active_plan_id); self.refresh_plan_speed(); self.refresh_auto_proxy(); self.refresh_entries()

    def refresh_plan_speed(self):
        if not hasattr(self, "plan_speed_box"):
            return
        speed = self.store.plan_speed(self.active_plan_id) if self.active_plan_id else "fast"
        self.plan_speed_box.set("最慢（每条间隔60秒）" if speed == "slow" else "最快（每条间隔3秒）")

    def save_plan_speed(self):
        if self.active_plan_id:
            self.store.set_plan_speed(self.active_plan_id, "slow" if self.plan_speed_box.get().startswith("最慢") else "fast")

    def refresh_auto_proxy(self):
        if hasattr(self, "auto_proxy"):
            self.auto_proxy.set(bool(self.active_plan_id and auto_proxy_enabled(self.store, self.active_plan_id)))

    def save_auto_proxy(self):
        if not self.active_plan_id:
            self.auto_proxy.set(False)
            return messagebox.showerror("无法设置", "请先创建或选择投稿方案")
        set_auto_proxy_enabled(self.store, self.active_plan_id, self.auto_proxy.get(), date.today().isoformat())
        self.refresh_entries()

    def new_entry_limit(self):
        phase_limit, _ = sync_auto_proxy_plan(self.store, self.active_plan_id, date.today().isoformat())
        return phase_limit or 1

    def refresh_entries(self):
        self.plan_entries.delete(*self.plan_entries.get_children())
        if not self.active_plan_id: return
        self.refresh_plan_speed(); self.refresh_auto_proxy()
        for row in self.store.list_plan_entries(self.active_plan_id): self.plan_entries.insert("", "end", iid=str(row[0]), values=(row[5], row[3], row[7]))

    def add_selected_project(self):
        selected = self.catalog.selection()
        if not self.active_plan_id: return messagebox.showerror("无法加入", "请先创建或选择投稿方案")
        if not selected: return messagebox.showerror("无法加入", "请先选择一个项目")
        item = self.catalog.item(selected[0]); account, project_id = item["values"]
        if not project_id: return messagebox.showerror("无法加入", "请选择账户下的具体项目")
        try: add_plan_entry(self.store, self.active_plan_id, ProjectRef(str(account), f"账户 {account}", str(project_id), item["text"]), self.new_entry_limit()); self.refresh_entries()
        except Exception as exc: messagebox.showerror("加入失败", str(exc))

    def refresh_project_picker(self):
        if hasattr(self, "project_picker"):
            self.project_picker["values"] = list(getattr(self, "available_projects", {}))

    def add_picked_project(self):
        project = getattr(self, "available_projects", {}).get(self.project_picker.get())
        if not self.active_plan_id: return messagebox.showerror("无法加入", "请先创建或选择投稿方案")
        if not project: return messagebox.showerror("无法加入", "请先到“账户项目”页检测项目后选择")
        try: add_plan_entry(self.store, self.active_plan_id, project, self.new_entry_limit()); self.refresh_entries()
        except Exception as exc: messagebox.showerror("加入失败", str(exc))

    def move_selected(self, delta):
        selected = self.plan_entries.selection()
        if selected: move_entry(self.store, self.active_plan_id, int(selected[0]), delta); self.refresh_entries()

    def edit_limit(self, event):
        if self.plan_entries.identify_column(event.x) != "#3": return
        item_id = self.plan_entries.identify_row(event.y)
        if not item_id: return
        x, y, width, height = self.plan_entries.bbox(item_id, "#3")
        editor = ttk.Entry(self.plan_entries, width=8); editor.insert(0, self.plan_entries.item(item_id, "values")[2]); editor.place(x=x, y=y, width=width, height=height); editor.focus_set(); editor.select_range(0, "end")
        def save(_=None):
            try: self.store.update_entry_limit(int(item_id), valid_daily_limit(editor.get()))
            except Exception as exc: messagebox.showerror("数量无效", str(exc)); editor.focus_set(); return
            editor.destroy(); self.refresh_entries()
        editor.bind("<Return>", save); editor.bind("<FocusOut>", save); editor.bind("<Escape>", lambda _: editor.destroy())

    def remove_selected(self):
        selected = self.plan_entries.selection()
        if selected: self.store.delete_entry(int(selected[0])); self.refresh_entries()

    def delete_current_plan(self):
        if self.active_plan_id: self.store.delete_plan(self.active_plan_id); self.active_plan_id = None; self.refresh_plan_list(); self.refresh_auto_proxy(); self.refresh_entries()

    def begin_drag(self, event): self.drag_entry_id = self.plan_entries.identify_row(event.y)
    def finish_drag(self, event):
        target = self.plan_entries.identify_row(event.y)
        if self.drag_entry_id and target and target != self.drag_entry_id:
            ids = [int(item) for item in self.plan_entries.get_children()]; source, destination = ids.index(int(self.drag_entry_id)), ids.index(int(target)); entry = ids.pop(source); ids.insert(destination, entry); self.store.set_entry_order(self.active_plan_id, ids); self.refresh_entries()
        self.drag_entry_id = None

    def _build_status(self):
        tab = ttk.Frame(self.tabs); self.tabs.add(tab, text="运行状态")
        row = ttk.Frame(tab); row.pack(fill="x", padx=10, pady=10); ttk.Button(row, text="启动投稿", command=self.start_worker).pack(side="left"); ttk.Button(row, text="停止投稿", command=self.stop_worker).pack(side="left", padx=6)
        self.runtime_summary = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.runtime_summary, justify="left").pack(fill="x", padx=10, pady=(0, 6))
        self.runtime_projects = ttk.Treeview(tab, columns=("project", "account", "limit", "used", "remaining", "status"), show="headings", height=8)
        for column, text, width in (
            ("project", "\u9879\u76ee", 280),
            ("account", "\u8d26\u6237", 150),
            ("limit", "\u6bcf\u65e5\u989d\u5ea6", 90),
            ("used", "\u4eca\u65e5\u5df2\u5360\u7528", 100),
            ("remaining", "\u5269\u4f59", 80),
            ("status", "\u72b6\u6001", 130),
        ):
            self.runtime_projects.heading(column, text=text); self.runtime_projects.column(column, width=width, anchor="center")
        self.runtime_projects.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(tab, text="\u8fd0\u884c\u65e5\u5fd7").pack(anchor="w", padx=10)
        self.event_log = tk.Text(tab, height=10, state="disabled"); self.event_log.pack(fill="both", expand=True, padx=10, pady=(0, 10)); self.worker = PostingWorker(self.base_dir, self.worker_event)
        self._refresh_runtime_status()

    def _refresh_runtime_status(self):
        try:
            today = date.today().isoformat()
            changed_plan_ids = sync_auto_proxy_plans(self.store, today)
            if self.active_plan_id in changed_plan_ids:
                self.refresh_entries()
            plan_id = int(self.store.get_state("active_plan_id", "0") or 0)
            current_book = self.store.get_state("runtime_current_book", "")
            current_account = self.store.get_state("runtime_current_advertiser_id", "")
            current_project = self.store.get_state("runtime_current_project", "")
            current_project_id = self.store.get_state("runtime_current_project_id", "")
            current_status = self.store.get_state("runtime_current_status", "idle")
            status_text = {
                "selecting_target": "\u6b63\u5728\u9009\u62e9\u9879\u76ee",
                "searching_material": "\u6b63\u5728\u67e5\u627e\u7d20\u6750",
                "creating_promotion": "\u6b63\u5728\u521b\u5efa\u5355\u5143",
                "idle": "\u7a7a\u95f2",
            }.get(current_status, current_status or "\u7a7a\u95f2")
            plan_name = self.store.plan_name(plan_id) if plan_id else ""
            current_line = "\u65e0"
            if current_book:
                current_line = f"{current_book} | {current_account} | {current_project or '\u5f85\u9009\u9879\u76ee'}"
            last_result = self.store.get_state("runtime_last_result", "")
            last_book = self.store.get_state("runtime_last_book", "")
            last_time = self.store.get_state("runtime_last_updated_at", "")
            speed = self.store.get_state("runtime_posting_speed", self.store.plan_speed(plan_id) if plan_id else "fast")
            speed_text = "\u6700\u6162\uff08\u6bcf\u6761\u95f460\u79d2\uff09" if speed == "slow" else ("\u6700\u5feb\uff08\u6bcf\u6761\u95f43\u79d2\uff09" if speed == "fast" else "\u65e0\u4efb\u52a1\u68c0\u67e5\uff0830\u79d2\uff09")
            next_task_at = int(self.store.get_state("runtime_next_task_at", "0") or 0)
            remaining_seconds = max(0, next_task_at - int(time.time()))
            speed_summary = f"\u5f53\u524d\u6295\u7a3f\u901f\u5ea6\uff1a{speed_text}\uff0c\u4e0b\u6b21\u9886\u53d6\uff1a{remaining_seconds}\u79d2\u540e\n"
            self.runtime_summary.set(
                speed_summary +
                f"\u5f53\u524d\u8fd0\u884c\u65b9\u6848\uff1a{plan_name or '\u672a\u9009\u62e9'}\n"
                f"\u5f53\u524d\u4efb\u52a1\uff1a{current_line}\n"
                f"\u5f53\u524d\u9636\u6bb5\uff1a{status_text}\n"
                f"\u6700\u8fd1\u7ed3\u679c\uff1a{last_book or '\u65e0'} | {last_result or '\u65e0'} | {last_time or '\u65e0'}"
            )
            self.runtime_projects.delete(*self.runtime_projects.get_children())
            if plan_id:
                for item in self.store.plan_status(plan_id, today):
                    row_status = "\u5df2\u6ee1" if item["status"] == "full" else "\u53ef\u7528"
                    if current_book and str(item["project_id"]) == str(current_project_id):
                        row_status = "\u6267\u884c\u4e2d"
                    self.runtime_projects.insert("", "end", values=(item["project_name"], item["advertiser_id"], item["daily_limit"], item["used"], item["remaining"], row_status))
        finally:
            self.root.after(3000, self._refresh_runtime_status)

    def start_worker(self):
        if not self.active_plan_id: return messagebox.showerror("无法启动", "请先选择投稿方案")
        self.worker.start(); self.worker_event("worker_started")

    def stop_worker(self): self.worker.stop(); self.worker_event("worker_stop_requested")

    def worker_event(self, text):
        self.root.after(0, lambda: self._append_event(text))
        if str(text).startswith(("worker_error:", "retry:", "terminal:")):
            self.root.after(0, lambda: self.on_alert(f"API 投稿异常：{text}"))

    def _append_event(self, text):
        self.event_log.configure(state="normal"); self.event_log.insert("end", str(text) + "\n"); self.event_log.see("end"); self.event_log.configure(state="disabled")
