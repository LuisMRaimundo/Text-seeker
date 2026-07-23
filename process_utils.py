# process_utils.py — hide Windows console windows and limit external tool concurrency
"""
On Windows, pytesseract and pdf2image spawn tesseract.exe / pdftoppm via subprocess.
Without CREATE_NO_WINDOW each spawn flashes a CMD window; with parallel search many
windows pile up and can overload the machine.

Call configure_hidden_subprocess_windows() once at startup (before OCR/PDF imports).
Use limit_external_processes() around Tesseract/Poppler calls.
"""
from __future__ import annotations

import os
import sys
import threading
from contextlib import contextmanager
from typing import Optional

_CONFIGURED = False
_external_sem: Optional[threading.Semaphore] = None


def configure_hidden_subprocess_windows() -> None:
    """Patch subprocess.Popen so child processes do not open console windows."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    if sys.platform != "win32":
        return

    import subprocess

    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    _orig_popen = subprocess.Popen

    class _HiddenWindowPopen(_orig_popen):  # type: ignore[misc, valid-type]
        def __init__(self, *args, **kwargs):
            flags = kwargs.pop("creationflags", 0)
            kwargs["creationflags"] = flags | create_no_window

            startupinfo = kwargs.get("startupinfo")
            if startupinfo is None:
                startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            kwargs["startupinfo"] = startupinfo

            super().__init__(*args, **kwargs)

    subprocess.Popen = _HiddenWindowPopen  # type: ignore[misc, assignment]


def _external_process_limit() -> int:
    try:
        n = int(os.environ.get("TEXT_SEEKER_MAX_EXTERNAL_PROCESSES", "3"))
    except ValueError:
        n = 3
    return max(1, min(n, 8))


def resolve_poppler_path() -> Optional[str]:
    """Return Poppler bin dir if found (PATH, POPPLER_PATH, or common installs)."""
    env = os.environ.get("POPPLER_PATH") or ""
    if env and os.path.isdir(env):
        return env
    import shutil
    which = shutil.which("pdftoppm") or shutil.which("pdftoppm.exe")
    if which:
        return os.path.dirname(os.path.abspath(which))
    for cand in (
        r"D:\poppler-24.08.0\Library\bin",
        r"D:\poppler\Library\bin",
        r"C:\poppler\Library\bin",
        r"C:\Program Files\poppler\Library\bin",
        r"C:\Program Files\poppler\bin",
    ):
        exe = os.path.join(cand, "pdftoppm.exe" if sys.platform == "win32" else "pdftoppm")
        if os.path.isfile(exe):
            return cand
    return None


def _get_external_sem() -> threading.Semaphore:
    global _external_sem
    if _external_sem is None:
        _external_sem = threading.Semaphore(_external_process_limit())
    return _external_sem


@contextmanager
def limit_external_processes():
    """Cap concurrent Tesseract / Poppler subprocesses across worker threads."""
    sem = _get_external_sem()
    sem.acquire()
    try:
        yield
    finally:
        sem.release()
