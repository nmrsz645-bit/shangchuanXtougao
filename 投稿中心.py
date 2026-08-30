from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import date


ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "API投稿2.0" / "app"), str(ROOT / "自动上传" / "src")]

from desktop_posting.desktop_app import DesktopApp
from desktop_posting.single_instance import acquire_instance_lock
from video_feishu.app import VideoFeishuApp, configure_logging
from shared_feishu import SharedFeishuSettings, load, save
from center_startup import set_enabled
from daily_restart import needs_daily_check


def main() -> None:
    instance_lock = acquire_instance_lock(ROOT)
    if not instance_lock:
        notice = tk.Tk()
        notice.withdraw()
        messagebox.showinfo("上传 + 投稿中心", "程序已经在运行。")
        notice.destroy()
        return
    root = tk.Tk()
    root.title("上传 + 投稿中心（本地版）")
    root.geometry("1120x760")

    api_dir = ROOT / "API投稿2.0"
    upload_dir = ROOT / "自动上传"

    configure_logging()
    alert = tk.StringVar(value="运行正常")
    ttk.Label(root, textvariable=alert, foreground="#167d2a", anchor="w").pack(fill="x", padx=12, pady=(8, 0))

    def push_alert(text):
        alert.set(text)
    tabs = ttk.Notebook(root)
    tabs.pack(fill="both", expand=True, padx=8, pady=8)
    shared_tab, api_tab, upload_tab = ttk.Frame(tabs), ttk.Frame(tabs), ttk.Frame(tabs)
    tabs.add(shared_tab, text="飞书设置")
    tabs.add(api_tab, text="API 投稿")
    tabs.add(upload_tab, text="视频上传")
    api = DesktopApp(api_tab, api_dir, embedded=True, on_alert=push_alert)
    upload = VideoFeishuApp(upload_tab, embedded=True, on_alert=push_alert)

    config_path = ROOT / "共享飞书设置.json"
    settings = load(config_path)
    if not settings.app_id:
        settings.app_id = api.settings.feishu_app_id or upload.vars["app_id"].get()
    if not settings.secret:
        settings.secret = api.settings.feishu_secret or upload.vars["secret"].get() or upload.secret_store.get(settings.app_id)
    if not settings.task_sheet_url:
        settings.task_sheet_url = api.settings.submission_sheet_url or upload.vars["paste_url"].get()
    if not settings.copy_sheet_url:
        settings.copy_sheet_url = upload.vars["copy_url"].get()

    fields = {key: tk.StringVar(value=getattr(settings, key)) for key in ("app_id", "secret", "task_sheet_url", "copy_sheet_url")}
    start_with_windows = tk.BooleanVar(value=settings.start_with_windows)
    start_tasks_automatically = tk.BooleanVar(value=settings.start_tasks_automatically)
    daily_restart_enabled = tk.BooleanVar(value=settings.daily_restart_enabled)
    form = ttk.Frame(shared_tab, padding=24)
    form.pack(fill="x", anchor="n")
    labels = (("飞书 App ID", "app_id"), ("飞书 Secret", "secret"), ("上传/投稿表格链接", "task_sheet_url"), ("复制表格链接", "copy_sheet_url"))
    for row, (label, key) in enumerate(labels):
        ttk.Label(form, text=label, width=20).grid(row=row, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=fields[key], width=95, show="*" if key == "secret" else "").grid(row=row, column=1, sticky="ew", pady=6)
    form.columnconfigure(1, weight=1)

    def apply_shared(show_message=False, update_startup=False):
        nonlocal settings
        settings = SharedFeishuSettings(
            **{key: fields[key].get().strip() for key in fields},
            start_with_windows=start_with_windows.get(),
            start_tasks_automatically=start_tasks_automatically.get(),
            daily_restart_enabled=daily_restart_enabled.get(),
            last_daily_restart_check=settings.last_daily_restart_check,
        )
        save(config_path, settings)
        api.set_shared_feishu(settings.app_id, settings.secret, settings.task_sheet_url)
        upload.set_shared_feishu(settings.app_id, settings.secret, settings.task_sheet_url, settings.copy_sheet_url)
        if update_startup:
            runner = None if getattr(sys, "frozen", False) else ROOT / "start_center.py"
            set_enabled(settings.start_with_windows, sys.executable, runner)
        if show_message:
            ttk.Label(form, text="已保存并同步到两个功能页。", foreground="#167d2a").grid(row=5, column=1, sticky="w")

    ttk.Checkbutton(form, text="随 Windows 启动；程序退出后 60 秒自动重启", variable=start_with_windows).grid(row=4, column=1, sticky="w", pady=(12, 2))
    ttk.Checkbutton(form, text="启动中心后自动开始投稿和视频上传", variable=start_tasks_automatically).grid(row=5, column=1, sticky="w", pady=2)
    ttk.Checkbutton(form, text="每天凌晨 00:00 检查；已停止的任务自动启动", variable=daily_restart_enabled).grid(row=6, column=1, sticky="w", pady=2)
    ttk.Button(form, text="保存共享飞书设置", command=lambda: apply_shared(True, True)).grid(row=7, column=1, sticky="w", pady=10)
    apply_shared()

    def start_workers():
        if api.active_plan_id:
            api.start_worker()
        else:
            push_alert("未启动 API 投稿：请先选择投稿方案。")
        settings_ready = all(upload.vars[key].get().strip() for key in ("app_id", "secret", "copy_url", "paste_url", "source_dir", "destination_dir", "material_url"))
        if settings_ready:
            upload.start_auto_upload()
        else:
            push_alert("未启动视频上传：请先完成视频上传配置。")

    def daily_restart_check():
        today = date.today().isoformat()
        if settings.daily_restart_enabled and needs_daily_check(settings.last_daily_restart_check, today):
            restarted = []
            if not (api.worker.thread and api.worker.thread.is_alive()):
                if api.active_plan_id:
                    api.start_worker()
                    restarted.append("API 投稿")
                else:
                    push_alert("凌晨检查：未启动 API 投稿，请先选择投稿方案。")
            video_settings_ready = all(upload.vars[key].get().strip() for key in ("app_id", "secret", "copy_url", "paste_url", "source_dir", "destination_dir", "material_url"))
            if upload.uploader is None:
                if video_settings_ready:
                    upload.start_auto_upload()
                    restarted.append("视频上传")
                else:
                    push_alert("凌晨检查：未启动视频上传，请先完成视频上传配置。")
            settings.last_daily_restart_check = today
            save(config_path, settings)
            if restarted:
                push_alert("凌晨检查已自动启动：" + "、".join(restarted))
        root.after(10_000, daily_restart_check)

    root.after(0, daily_restart_check)

    if settings.start_tasks_automatically:
        root.after(1200, start_workers)

    def close():
        api.stop_worker()
        upload.close(destroy=False)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    root.mainloop()


if __name__ == "__main__":
    main()
