import argparse
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from .desktop_app import DesktopApp
from .single_instance import acquire_instance_lock


def default_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--auto-start", action="store_true")
    args = parser.parse_args()

    base_dir = Path(args.base_dir) if args.base_dir else default_base_dir()
    instance_lock = acquire_instance_lock(base_dir)
    if not instance_lock:
        if not args.auto_start:
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("Already running", "API Posting 2.0 is already running.")
            root.destroy()
        return

    root = tk.Tk()
    DesktopApp(root, base_dir, auto_start=args.auto_start)
    root.mainloop()


if __name__ == "__main__":
    main()
