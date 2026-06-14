#!/usr/bin/env python3
"""Bootstrap text-seeker: launch GUI using install_state.json on Windows."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path

from config import (
    INSTALL_STATE_FILE,
    PROJECT_ROOT,
    REQUIREMENTS,
    RUNTIME_DIR,
    STATE_GUI_CAN_LAUNCH,
    STATE_OCR_CAPABILITY,
    STATE_PACKAGES_INSTALLED,
    STATE_PATH_POLICY,
    STATE_POPPLER_BIN,
    STATE_POPPLER_MODE,
    STATE_PYTHON_PATH,
    STATE_PYTHON_SCRIPTS_PATH,
    STATE_TESSERACT_PATH,
    STATE_TEXT_SEARCH_AVAILABLE,
    STATE_VENV_PATH,
    TOOL_MODE_SKIP,
    assert_official_windows_python_installer_url,
    load_install_state,
    machine_key,
    ocr_tools_stamp,
    pbs_download_url,
    platform_key,
    process_path_parts_from_state,
    resolve_poppler_bin_from_state,
    resolve_python_exe_from_state,
    resolve_tesseract_exe_from_state,
    runtime_python_dir,
    runtime_python_exe,
    windows_install_log,
    windows_install_state_path,
    windows_poppler_bin,
    windows_python_installer_url,
    windows_runtime_root,
    windows_tesseract_exe,
    windows_tesseract_tessdata_dir,
)


def _log(msg: str) -> None:
    print(msg, flush=True)


def _append_install_log(message: str, level: str = "INFO") -> None:
    if platform_key() != "windows":
        return
    log_path = windows_install_log()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {message}"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _log(f"Downloading: {url}")
    urllib.request.urlretrieve(url, dest)


def _run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    _log("Running: " + " ".join(cmd))
    subprocess.run(cmd, cwd=cwd or PROJECT_ROOT, env=env, check=True)


def _run_capture(cmd: list[str], *, env: dict[str, str] | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return 1, str(exc)
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out.strip()


def _setup_pbs(platform_name: str) -> Path:
    py_exe = runtime_python_exe(platform_name)
    if py_exe.is_file():
        return py_exe

    arch = machine_key()
    url = pbs_download_url(platform_name, arch)
    runtime_dir = runtime_python_dir(platform_name)
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        archive = tmp_path / "python.tar.gz"
        _download(url, archive)
        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(tmp_path)
        extracted = next(p for p in tmp_path.iterdir() if p.is_dir() and p.name.startswith("python"))
        shutil.move(str(extracted), str(runtime_dir))

    if not py_exe.is_file():
        raise RuntimeError(f"Portable Python not found after extract: {py_exe}")
    return py_exe


def resolve_windows_python() -> Path:
    state = load_install_state()
    py = resolve_python_exe_from_state(state)
    if py:
        return py
    if platform_key() == "windows":
        assert_official_windows_python_installer_url(windows_python_installer_url())
        raise RuntimeError(
            "Python is not configured. Run installers\\windows\\Install and Run.bat "
            "to open the text-seeker installer."
        )
    _log(f"Setting up portable Python for {platform_key()} …")
    return _setup_pbs(platform_key())


def _tool_status(state: dict | None = None) -> tuple[bool, bool]:
    state = state if state is not None else load_install_state()
    tess = resolve_tesseract_exe_from_state(state)
    pop = resolve_poppler_bin_from_state(state)
    tess_ok = bool(tess and tess.is_file())
    pop_ok = bool(pop and (pop / "pdftotext.exe").is_file())
    return tess_ok, pop_ok


def windows_process_env(py: Path, state: dict | None = None) -> dict[str, str]:
    state = state if state is not None else load_install_state() or {}
    env = os.environ.copy()
    path_parts = process_path_parts_from_state(state, py)
    if path_parts:
        env["PATH"] = os.pathsep.join(path_parts) + os.pathsep + env.get("PATH", "")

    tess_exe = resolve_tesseract_exe_from_state(state)
    if tess_exe and tess_exe.is_file():
        env["TESSERACT_PATH"] = str(tess_exe)
        tessdata = tess_exe.parent / "tessdata"
        if not tessdata.is_dir():
            tessdata = windows_tesseract_tessdata_dir()
        if tessdata.is_dir():
            env["TESSDATA_PREFIX"] = str(tessdata)

    pop_bin = resolve_poppler_bin_from_state(state)
    if pop_bin and pop_bin.is_dir():
        env["POPPLER_PATH"] = str(pop_bin)

    env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _python_ready(py: Path) -> tuple[bool, bool, bool]:
    code, out = _run_capture([str(py), "--version"])
    py_ok = code == 0
    code, _ = _run_capture([str(py), "-m", "pip", "--version"])
    pip_ok = code == 0
    code, _ = _run_capture([str(py), "-c", "import tkinter; tkinter.Tk().destroy()"])
    tk_ok = code == 0
    return py_ok, pip_ok, tk_ok


def launch_gui(py: Path) -> int:
    state = load_install_state() or {}
    env = windows_process_env(py, state) if platform_key() == "windows" else os.environ.copy()
    if platform_key() != "windows":
        env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    tess_ok, poppler_ok = _tool_status(state)
    if platform_key() == "windows":
        if not tess_ok:
            _log("WARNING: Tesseract unavailable — OCR for scanned images may not work.")
            _append_install_log("Launch warning: Tesseract missing", "WARN")
        if not poppler_ok:
            _log("WARNING: Poppler unavailable — scanned-PDF conversion may not work.")
            _append_install_log("Launch warning: Poppler missing", "WARN")

    _, pip_ok, tk_ok = _python_ready(py)
    if not tk_ok:
        msg = "Tkinter is unavailable — GUI cannot start."
        _log(f"ERROR: {msg}")
        _append_install_log(msg, "ERROR")
        _log(f"See log: {windows_install_log()}")
        return 2
    if not pip_ok:
        msg = "pip is unavailable — reinstall Python packages via the installer."
        _log(f"ERROR: {msg}")
        _append_install_log(msg, "ERROR")
        return 2

    cmd = [str(py), str(PROJECT_ROOT / "app.py"), "--gui"]
    _log("Starting text-seeker …")
    try:
        return subprocess.call(cmd, cwd=PROJECT_ROOT, env=env)
    except OSError as exc:
        _log(f"ERROR: Failed to launch app: {exc}")
        _append_install_log(f"Launch failed: {exc}", "ERROR")
        _log(f"See log: {windows_install_log()}")
        return 1


def _doctor_line(label: str, value: str, *, ok: bool | None = None, warn: bool = False) -> None:
    suffix = ""
    if ok is True:
        suffix = " [OK]"
    elif warn:
        suffix = " [WARNING]"
    elif ok is False:
        suffix = " [MISSING]"
    line = f"{label}: {value}{suffix}"
    _log(line)
    _append_install_log(line)


def cmd_setup(_: argparse.Namespace) -> int:
    py = resolve_windows_python()
    _log(f"Ready. Python: {py}")
    return 0


def cmd_launch(_: argparse.Namespace) -> int:
    try:
        py = resolve_windows_python()
    except RuntimeError as exc:
        _log(f"ERROR: {exc}")
        _log(f"See log: {windows_install_log()}")
        return 1
    return launch_gui(py)


def cmd_doctor(_: argparse.Namespace) -> int:
    _append_install_log("=== bootstrap doctor ===")
    plat = platform_key()
    arch = machine_key()
    _doctor_line("Project root", str(PROJECT_ROOT))
    _doctor_line("OS", f"{platform.system()} {platform.release()} ({platform.version()})")
    _doctor_line("Architecture", f"{platform.machine()} / {arch}")

    if plat == "windows" and arch != "x86_64":
        _doctor_line("Windows support", "x64 only", ok=False)

    state = load_install_state()
    _doctor_line("Install state file", str(windows_install_state_path()), ok=bool(state))

    py = resolve_python_exe_from_state(state) if state else runtime_python_exe(plat)
    py_found = py.is_file() if py else False
    _doctor_line("Python executable", str(py) if py else "n/a", ok=py_found)

    pip_ok = tk_ok = False
    if py_found and py:
        code, out = _run_capture([str(py), "--version"])
        _doctor_line("Python version", out.splitlines()[0] if out else f"exit {code}", ok=code == 0)
        code, out = _run_capture([str(py), "-m", "pip", "--version"])
        pip_ok = code == 0
        _doctor_line("pip", out.splitlines()[0] if out else f"exit {code}", ok=pip_ok)
        code, _ = _run_capture([str(py), "-c", "import tkinter; tkinter.Tk().destroy()"])
        tk_ok = code == 0
        _doctor_line("tkinter", "available" if tk_ok else "not available", ok=tk_ok)
    else:
        _doctor_line("pip", "n/a (Python missing)", ok=False)
        _doctor_line("tkinter", "n/a (Python missing)", ok=False)

    if state:
        _doctor_line("Python mode", str(state.get("python_mode", "n/a")))
        _doctor_line("Packages installed", str(state.get(STATE_PACKAGES_INSTALLED, False)), ok=bool(state.get(STATE_PACKAGES_INSTALLED)))
        _doctor_line("PATH policy", str(state.get(STATE_PATH_POLICY, "process_local")))
        _doctor_line("User PATH modified", str(state.get("user_path_modified", False)))

    app_py = PROJECT_ROOT / "app.py"
    _doctor_line("app.py", str(app_py), ok=app_py.is_file())

    if plat == "windows" and py_found and py:
        env = windows_process_env(py, state)
        _doctor_line("Process-local PATH", os.pathsep.join(process_path_parts_from_state(state, py)))

        tess_exe = resolve_tesseract_exe_from_state(state)
        tess_ok = bool(tess_exe and tess_exe.is_file())
        tess_warn = not tess_ok and py_found
        _doctor_line("Tesseract executable", str(tess_exe) if tess_exe else "n/a", ok=True if tess_ok else None, warn=tess_warn)
        if tess_ok and tess_exe:
            code, out = _run_capture([str(tess_exe), "--version"], env=env)
            _doctor_line("Tesseract version", out.splitlines()[0] if out else f"exit {code}", ok=code == 0)

        pop_bin = resolve_poppler_bin_from_state(state)
        pop_ok = bool(pop_bin and (pop_bin / "pdftotext.exe").is_file())
        pop_warn = not pop_ok and py_found
        _doctor_line("Poppler bin", str(pop_bin) if pop_bin else "n/a", ok=True if pop_ok else None, warn=pop_warn)
        if pop_ok and pop_bin:
            code, out = _run_capture([str(pop_bin / "pdftotext.exe"), "-v"], env=env)
            _doctor_line("pdftotext version", out.splitlines()[0] if out else f"exit {code}", ok=code == 0)

        ocr_tag = state.get(STATE_OCR_CAPABILITY) if state else ocr_tools_stamp(tesseract_ok=tess_ok, poppler_ok=pop_ok)
        if ocr_tag == "ok":
            _doctor_line("OCR capability", "ok", ok=True)
        elif ocr_tag == "partial":
            _doctor_line("OCR capability", "partial", warn=True)
        else:
            _doctor_line("OCR capability", "missing", warn=bool(py_found and tk_ok))

        gui_ok = bool(state.get(STATE_GUI_CAN_LAUNCH, py_found and tk_ok and pip_ok)) if state else (py_found and tk_ok and pip_ok)
        _doctor_line("GUI can launch", str(gui_ok), ok=gui_ok)
        search_ok = bool(state.get(STATE_TEXT_SEARCH_AVAILABLE, True)) if state else True
        _doctor_line("Text search available", str(search_ok), ok=search_ok)
        _doctor_line("Install log", str(windows_install_log()), ok=windows_install_log().is_file())

    _append_install_log("=== bootstrap doctor end ===")
    if plat == "windows" and not py_found:
        return 1
    if py_found and not tk_ok:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="text-seeker bootstrap")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup").set_defaults(func=cmd_setup)
    sub.add_parser("launch").set_defaults(func=cmd_launch)
    sub.add_parser("doctor").set_defaults(func=cmd_doctor)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except subprocess.CalledProcessError as exc:
        msg = f"Command failed with exit code {exc.returncode}."
        _log(msg)
        _append_install_log(msg, "ERROR")
        return exc.returncode or 1
    except Exception as exc:
        _log(f"Error: {exc}")
        _append_install_log(f"Error: {exc}", "ERROR")
        return 1


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    if len(sys.argv) == 1:
        sys.argv.append("launch")
    raise SystemExit(main())
