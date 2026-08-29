import hashlib
import os
from pathlib import Path


class _WindowsMutex:
    def __init__(self, handle):
        self.handle = handle

    def close(self):
        if self.handle:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None

    def __del__(self):
        self.close()


class _FileLock:
    def __init__(self, path, fd):
        self.path = path
        self.fd = fd

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        try:
            self.path.unlink()
        except OSError:
            pass

    def __del__(self):
        self.close()


def _lock_name(base_dir):
    resolved = str(Path(base_dir).resolve()).lower()
    digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()
    return "Local\\ApiPosting20_" + digest


def acquire_instance_lock(base_dir):
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = kernel32.CreateMutexW(None, False, _lock_name(base_dir))
        if not handle:
            return None
        if kernel32.GetLastError() == 183:
            kernel32.CloseHandle(handle)
            return None
        return _WindowsMutex(handle)

    lock_path = Path(base_dir) / "data" / "desktop_app.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
    except FileExistsError:
        return None
    return _FileLock(lock_path, fd)
