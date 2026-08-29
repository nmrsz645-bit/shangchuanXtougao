from dataclasses import dataclass
import logging
from logging.handlers import RotatingFileHandler
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .automation import AutoUploadCoordinator
from .config import JsonSettingsStore, RetryStore, SecretStore, Settings, app_data_dir
from .models import PreviewItem
from .service import OfficialFeishuGateway, PreviewResult, TaskService, mark_uploaded_names
from .startup import set_auto_start
from .tracking import DailyStatsStore, FeishuWriteQueue
from .uploader import OceanEngineUploader


@dataclass
class AppState:
    preview_token: str = ""

    @property
    def can_execute(self) -> bool:
        return bool(self.preview_token)

    def invalidate_preview(self) -> None:
        self.preview_token = ""


def preview_row_values(item: PreviewItem) -> tuple[str, str, str, str, str, str, str]:
    return (item.source.name, item.outer_folder, str(item.source), item.status, "", "", "")


def configure_logging() -> None:
    log_dir = app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_dir / "video-feishu.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[handler])


class VideoFeishuApp:
    def __init__(self, root: tk.Tk, embedded: bool = False, on_alert=None):
        self.root = root
        self.on_alert = on_alert or (lambda _: None)
        if not embedded:
            self.root.title("视频提取与飞书同步工具")
            self.root.geometry("1100x700")
        self.settings_store = JsonSettingsStore()
        self.secret_store = SecretStore()
        self.retry_store = RetryStore()
        self.stats_store = DailyStatsStore()
        self.feishu_write_queue = FeishuWriteQueue()
        self.gateway = OfficialFeishuGateway()
        self.service = TaskService(self.gateway, self.retry_store)
        self.state = AppState()
        self.preview: PreviewResult | None = None
        self.vars = {name: tk.StringVar() for name in ("app_id", "secret", "copy_url", "paste_url", "source_dir", "destination_dir", "material_url", "check_interval_minutes", "upload_stall_timeout_minutes", "upload_confirmation_timeout_minutes")}
        self.auto_start_var = tk.BooleanVar(value=False)
        self.auto_execute_var = tk.BooleanVar(value=False)
        self.write_upload_success_var = tk.BooleanVar(value=False)
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.uploader: OceanEngineUploader | None = None
        self.login_uploader: OceanEngineUploader | None = None
        self.status = tk.StringVar(value="就绪")
        self.stats_text = tk.StringVar()
        self._build()
        self._load()
        for var in self.vars.values():
            var.trace_add("write", self._settings_changed)
        self.auto_start_var.trace_add("write", self._settings_changed)
        self.auto_execute_var.trace_add("write", self._settings_changed)
        self.write_upload_success_var.trace_add("write", self._settings_changed)
        self._refresh_stats()
        self.root.after(60_000, self._stats_tick)
        if self.auto_execute_var.get():
            self.root.after(3000, self.start_auto_upload)
        if not embedded:
            self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build(self):
        settings = ttk.LabelFrame(self.root, text="连接与文件设置", padding=10)
        settings.pack(fill="x", padx=10, pady=10)
        labels = [
            ("源文件夹", "source_dir"),
            ("目标文件夹", "destination_dir"),
            ("巨量素材库网址", "material_url"),
            ("无视频检查间隔(分钟)", "check_interval_minutes"),
            ("上传无进度超时(分钟)", "upload_stall_timeout_minutes"),
            ("上传后确认超时(分钟)", "upload_confirmation_timeout_minutes"),
        ]
        for row, (label, key) in enumerate(labels):
            ttk.Label(settings, text=label, width=18).grid(row=row, column=0, sticky="w", pady=3)
            entry = ttk.Entry(settings, textvariable=self.vars[key], show="*" if key == "secret" else "")
            entry.grid(row=row, column=1, sticky="ew", pady=3)
            if key in {"source_dir", "destination_dir"}:
                ttk.Button(settings, text="选择...", command=lambda k=key: self._choose(k)).grid(row=row, column=2, padx=5)
        ttk.Checkbutton(settings, text="开机自动启动程序", variable=self.auto_start_var).grid(row=10, column=1, sticky="w", pady=3)
        ttk.Checkbutton(settings, text="启动后自动提取并上传", variable=self.auto_execute_var).grid(row=11, column=1, sticky="w", pady=3)
        ttk.Checkbutton(settings, text="上传成功后写入飞书 E 列", variable=self.write_upload_success_var).grid(row=12, column=1, sticky="w", pady=3)
        settings.columnconfigure(1, weight=1)

        buttons = ttk.Frame(self.root)
        buttons.pack(fill="x", padx=10)
        ttk.Button(buttons, text="保存设置", command=self.save).pack(side="left", padx=3)
        ttk.Button(buttons, text="测试连接", command=self.test_connection).pack(side="left", padx=3)
        ttk.Button(buttons, text="扫描预览", command=self.scan).pack(side="left", padx=3)
        self.execute_button = ttk.Button(buttons, text="开始执行", command=self.execute, state="disabled")
        self.execute_button.pack(side="left", padx=3)
        self.retry_button = ttk.Button(buttons, text="重试写表失败项", command=self.retry)
        self.retry_button.pack(side="left", padx=3)
        self.login_button = ttk.Button(buttons, text="打开巨量登录页面", command=self.open_login_page)
        self.login_button.pack(side="left", padx=3)
        self.auto_button = ttk.Button(buttons, text="启动自动上传", command=self.start_auto_upload)
        self.auto_button.pack(side="left", padx=3)
        self.stop_button = ttk.Button(buttons, text="停止自动上传", command=self.stop_auto_upload, state="disabled")
        self.stop_button.pack(side="left", padx=3)

        ttk.Label(self.root, textvariable=self.stats_text).pack(fill="x", padx=12, pady=(8, 0))

        columns = ("video", "outer", "source", "status", "move", "write", "error")
        self.table = ttk.Treeview(self.root, columns=columns, show="headings")
        headings = ("视频名", "外层文件夹", "原路径", "预览状态", "移动状态", "写表状态", "错误")
        widths = (150, 150, 300, 120, 100, 100, 180)
        for key, title, width in zip(columns, headings, widths):
            self.table.heading(key, text=title)
            self.table.column(key, width=width)
        self.table.pack(fill="both", expand=True, padx=10, pady=10)
        ttk.Label(self.root, textvariable=self.status).pack(fill="x", padx=10, pady=(0, 10))

    def _choose(self, key):
        path = filedialog.askdirectory()
        if path:
            self.vars[key].set(path)

    def _settings(self) -> Settings:
        interval = int(self.vars["check_interval_minutes"].get() or "30")
        stall_timeout = int(self.vars["upload_stall_timeout_minutes"].get() or "45")
        confirmation_timeout = int(self.vars["upload_confirmation_timeout_minutes"].get() or "6")
        if interval < 1:
            raise ValueError("无视频检查间隔必须大于 0 分钟")
        if stall_timeout < 1:
            raise ValueError("上传无进度超时必须大于 0 分钟")
        if confirmation_timeout < 1:
            raise ValueError("上传后确认超时必须大于 0 分钟")
        return Settings(
            app_id=self.vars["app_id"].get().strip(),
            copy_url=self.vars["copy_url"].get().strip(),
            paste_url=self.vars["paste_url"].get().strip(),
            source_dir=self.vars["source_dir"].get().strip(),
            destination_dir=self.vars["destination_dir"].get().strip(),
            auto_start=self.auto_start_var.get(),
            auto_execute=self.auto_execute_var.get(),
            write_upload_success_to_feishu=self.write_upload_success_var.get(),
            material_url=self.vars["material_url"].get().strip(),
            check_interval_minutes=interval,
            upload_stall_timeout_minutes=stall_timeout,
            upload_confirmation_timeout_minutes=confirmation_timeout,
        )

    def _load(self):
        value = self.settings_store.load()
        for key in ("app_id", "copy_url", "paste_url", "source_dir", "destination_dir", "material_url", "check_interval_minutes", "upload_stall_timeout_minutes", "upload_confirmation_timeout_minutes"):
            self.vars[key].set(getattr(value, key))
        self.auto_start_var.set(value.auto_start)
        self.auto_execute_var.set(value.auto_execute)
        self.write_upload_success_var.set(value.write_upload_success_to_feishu)
        if value.app_id:
            try:
                self.vars["secret"].set(self.secret_store.get(value.app_id))
            except Exception:
                pass

    def _settings_changed(self, *_):
        self.state.invalidate_preview()
        self.preview = None
        self.execute_button.configure(state="disabled")

    def set_shared_feishu(self, app_id, secret, task_sheet_url, copy_sheet_url):
        self.vars["app_id"].set(app_id)
        self.vars["secret"].set(secret)
        self.vars["paste_url"].set(task_sheet_url)
        self.vars["copy_url"].set(copy_sheet_url)
        self.settings_store.save(self._settings())
        if app_id and secret:
            self.secret_store.set(app_id, secret)

    def _refresh_stats(self):
        stats = self.stats_store.snapshot()
        self.stats_text.set(
            f"统计日期：{stats['date']}    今日成功：{stats['success']}    "
            f"今日失败：{stats['failure']}    飞书待补写：{self.feishu_write_queue.count()}"
        )

    def _stats_tick(self):
        self._refresh_stats()
        self.root.after(60_000, self._stats_tick)

    def save(self):
        settings = self._settings()
        self.settings_store.save(settings)
        set_auto_start(settings.auto_start)
        if settings.app_id and self.vars["secret"].get():
            self.secret_store.set(settings.app_id, self.vars["secret"].get())
        self.status.set("设置已保存")

    def _worker(self, action, success):
        self.status.set("处理中...")

        def run():
            try:
                result = action()
            except Exception as exc:
                logging.exception("任务失败")
                self.root.after(0, lambda: messagebox.showerror("错误", str(exc)))
                self.root.after(0, lambda: self.status.set("失败"))
            else:
                self.root.after(0, lambda: success(result))

        threading.Thread(target=run, daemon=True).start()

    def test_connection(self):
        settings, secret = self._settings(), self.vars["secret"].get()
        self._worker(lambda: self.gateway.connect(settings, secret), lambda _: (self.status.set("连接和表头验证成功"), messagebox.showinfo("成功", "飞书连接及表头验证成功")))

    def scan(self):
        settings, secret = self._settings(), self.vars["secret"].get()
        self._worker(lambda: self.service.preview(settings, secret), self._show_preview)

    def _show_preview(self, preview):
        self.preview = preview
        self.state.preview_token = preview.token
        self.table.delete(*self.table.get_children())
        for item in preview.items:
            self.table.insert("", "end", values=preview_row_values(item))
        self.execute_button.configure(state="normal")
        self.status.set(f"预览完成：{len(preview.items)} 个视频")

    def execute(self):
        if not self.preview or not messagebox.askyesno("确认执行", f"将处理 {len(self.preview.items)} 个视频。确定移动文件、写入飞书并删除空文件夹吗？"):
            return
        self._execute_preview(self.preview)

    def auto_execute(self):
        self.start_auto_upload()

    def open_login_page(self):
        if self.uploader is not None:
            messagebox.showinfo("提示", "自动上传正在运行，浏览器已经由程序管理。")
            return
        if self.login_uploader is not None:
            messagebox.showinfo("提示", "登录页面已经打开。")
            return
        try:
            settings = self._settings()
            login_uploader = OceanEngineUploader(settings)
            login_uploader.ensure_browser_available()
        except Exception as exc:
            messagebox.showerror("设置错误", str(exc))
            return
        if not settings.material_url:
            messagebox.showerror("设置错误", "请先填写巨量素材库网址。")
            return
        self.settings_store.save(settings)
        self.login_uploader = login_uploader
        self.login_button.configure(state="disabled")
        self.auto_button.configure(state="disabled")
        self.status.set("请在独立 Chrome 中登录，完成后关闭浏览器")

        def run():
            try:
                self.login_uploader.open_login_page()
            except Exception as exc:
                logging.exception("打开巨量登录页面失败")
                self.root.after(0, lambda: messagebox.showerror("打开登录页面失败", str(exc)))
            finally:
                if self.login_uploader:
                    self.login_uploader.close()
                self.login_uploader = None
                self.root.after(0, self.login_button.configure, {"state": "normal"})
                self.root.after(0, self.auto_button.configure, {"state": "normal"})
                self.root.after(0, self.status.set, "登录浏览器已关闭，登录状态已保存")

        threading.Thread(target=run, daemon=True).start()

    def start_auto_upload(self):
        if self.uploader is not None:
            logging.info("自动上传已在运行，收到立即检查请求")
            self.status.set("自动上传已在运行，正在立即检查")
            self.wake_event.set()
            return
        try:
            settings, secret = self._settings(), self.vars["secret"].get()
            uploader = OceanEngineUploader(settings)
            uploader.ensure_browser_available()
        except Exception as exc:
            messagebox.showerror("设置错误", str(exc))
            return
        self.settings_store.save(settings)
        self.stop_event.clear()
        self.wake_event.clear()
        self.uploader = uploader
        self.auto_button.configure(text="立即检查")
        self.stop_button.configure(state="normal")
        self.status.set("自动上传已启动，正在检查视频")
        logging.info("自动上传启动：源文件夹=%s 目标文件夹=%s", settings.source_dir, settings.destination_dir)

        def extract():
            logging.info("开始扫描并提取视频")
            preview = self.service.preview(settings, secret)
            results = self.service.execute(preview, preview.token)
            logging.info("视频提取完成：扫描=%d 处理=%d", len(preview.items), len(results))

        def flush_feishu():
            if not settings.write_upload_success_to_feishu:
                return
            names = self.feishu_write_queue.load()
            if not names:
                return
            try:
                completed = mark_uploaded_names(settings, secret, names)
            except Exception:
                logging.exception("上传成功记录写入飞书失败，稍后重试")
                return
            self.feishu_write_queue.remove(completed)
            if missing := set(names) - completed:
                logging.warning("粘贴表 A 列未匹配，保留待补写：%s", "、".join(sorted(missing)))
            self.root.after(0, self._refresh_stats)

        def on_succeeded(videos):
            self.stats_store.record("success", videos)
            if settings.write_upload_success_to_feishu:
                self.feishu_write_queue.add([video.stem for video in videos])
                flush_feishu()
            self.root.after(0, self._refresh_stats)

        def on_failed(videos):
            self.stats_store.record("failure", videos)
            if videos:
                self.root.after(0, self.on_alert, "视频上传失败：" + "、".join(video.name for video in videos))
            self.root.after(0, self._refresh_stats)

        coordinator = AutoUploadCoordinator(
            settings,
            extract,
            self.uploader,
            lambda text: self.root.after(0, self.status.set, text),
            on_succeeded=on_succeeded,
            on_failed=on_failed,
            maintenance=flush_feishu,
        )

        def run():
            try:
                coordinator.run_forever(self.stop_event, self.wake_event)
            except Exception as exc:
                logging.exception("自动上传失败")
                self.root.after(0, messagebox.showerror, "自动上传失败", str(exc))
            finally:
                if self.uploader:
                    self.uploader.close()
                self.uploader = None
                self.root.after(0, self.auto_button.configure, {"state": "normal", "text": "启动自动上传"})
                self.root.after(0, self.stop_button.configure, {"state": "disabled"})
                self.root.after(0, self.status.set, "自动上传已停止")

        threading.Thread(target=run, daemon=True).start()

    def stop_auto_upload(self):
        self.stop_event.set()
        self.wake_event.set()
        if self.uploader:
            self.uploader.cancel()
        self.status.set("正在停止自动上传...")

    def close(self, destroy: bool = True):
        self.stop_event.set()
        if self.uploader:
            self.uploader.cancel()
        if self.login_uploader:
            self.login_uploader.cancel()
        if destroy:
            self.root.destroy()

    def _execute_preview(self, preview: PreviewResult):
        self.execute_button.configure(state="disabled")
        self._worker(lambda: self.service.execute(preview, preview.token), self._show_results)

    def _show_results(self, results):
        self.table.delete(*self.table.get_children())
        for result in results:
            item = result.preview
            self.table.insert("", "end", values=(item.source.name, item.outer_folder, str(item.source), item.status, result.move_status, result.write_status, result.error))
        self.state.invalidate_preview()
        self.preview = None
        self.status.set(f"执行完成：{len(results)} 项")

    def retry(self):
        settings, secret = self._settings(), self.vars["secret"].get()

        def action():
            _, token, sheet = self.gateway.connect(settings, secret)
            self.service.retry_failed_writes(token, sheet)

        self._worker(action, lambda _: self.status.set("失败写表项重试完成"))


def main() -> None:
    configure_logging()
    root = tk.Tk()
    VideoFeishuApp(root)
    root.mainloop()
