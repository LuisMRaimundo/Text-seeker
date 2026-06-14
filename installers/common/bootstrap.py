#!/usr/bin/env python3
"""Bootstrap portable Python + text-seeker dependencies, then launch the GUI."""

from __future__ import annotations

import argparse
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
    PROJECT_ROOT,
    REQUIREMENTS,
    RUNTIME_DIR,
    STAMP_FILE,
    assert_official_windows_python_installer_url,
    machine_key,
    ocr_tools_stamp,
    pbs_download_url,
    platform_key,
    runtime_python_dir,
    runtime_python_exe,
    stamp_payload,
    windows_install_log,
    windows_poppler_bin,
    windows_python_installer_url,
    windows_tesseract_dir,
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


def ensure_portable_python() -> Path:
    plat = platform_key()
    existing = runtime_python_exe(plat)
    if existing.is_file():
        return existing
    if plat == "windows":
        assert_official_windows_python_installer_url(windows_python_installer_url())
        raise RuntimeError(
            "Private Python is not installed. Run installers\\windows\\Install and Run.bat "
            "to install the official local Python runtime (not embed ZIP)."
        )
    _log(f"Setting up portable Python for {plat} …")
    return _setup_pbs(plat)


def _tool_status() -> tuple[bool, bool]:
    tess_ok = windows_tesseract_exe().is_file()
    poppler_ok = (windows_poppler_bin() / "pdftotext.exe").is_file()
    return tess_ok, poppler_ok


def _stamp_matches() -> bool:
    if not STAMP_FILE.is_file():
        return False
    tess_ok, poppler_ok = _tool_status()
    expected = stamp_payload(tesseract_ok=tess_ok, poppler_ok=poppler_ok)
    try:
        return STAMP_FILE.read_text(encoding="utf-8").strip() == expected.strip()
    except OSError:
        return False


def ensure_app_installed(py: Path) -> None:
    if _stamp_matches():
        return

    if platform_key() == "windows" and not runtime_python_exe("windows").is_file():
        raise RuntimeError(
            "Windows runtime is incomplete. Re-run installers\\windows\\setup.ps1 "
            "(Install and Run.bat)."
        )

    if platform_key() == "windows" and STAMP_FILE.is_file():
        _log(
            "Install stamp is outdated (requirements or runtime changed). "
            "Re-run installers\\windows\\Install and Run.bat to refresh."
        )
        return

    _log("Installing text-seeker and libraries (first run may take several minutes) …")
    _run([str(py), "-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools"])
    _run([str(py), "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    tess_ok, poppler_ok = _tool_status()
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    STAMP_FILE.write_text(
        stamp_payload(tesseract_ok=tess_ok, poppler_ok=poppler_ok),
        encoding="utf-8",
    )
    _log("Install complete.")


def windows_process_path_parts(py: Path) -> list[str]:
    """Process-local PATH entries prepended at launch (does not modify global/user PATH)."""
    py_dir = py.parent
    return [
        str(py_dir),
        str(py_dir / "Scripts"),
        str(windows_tesseract_dir()),
        str(windows_poppler_bin()),
    ]


def windows_process_env(py: Path) -> dict[str, str]:
    env = os.environ.copy()
    path_parts = windows_process_path_parts(py)
    env["PATH"] = os.pathsep.join(path_parts) + os.pathsep + env.get("PATH", "")

    tess_exe = windows_tesseract_exe()
    if tess_exe.is_file():
        env["TESSERACT_PATH"] = str(tess_exe)

    tessdata = windows_tesseract_tessdata_dir()
    if tessdata.is_dir():
        env["TESSDATA_PREFIX"] = str(tessdata)

    poppler_bin = windows_poppler_bin()
    if poppler_bin.is_dir():
        env["POPPLER_PATH"] = str(poppler_bin)

    env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def launch_gui(py: Path) -> int:
    env = windows_process_env(py) if platform_key() == "windows" else os.environ.copy()
    if platform_key() != "windows":
        env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    tess_ok, poppler_ok = _tool_status()
    if platform_key() == "windows":
        if not tess_ok:
            _log("WARNING: Tesseract OCR not found — OCR and scanned PDF features disabled.")
            _append_install_log("Launch warning: Tesseract missing", "WARN")
        if not poppler_ok:
            _log("WARNING: Poppler not found — PDF page rendering for OCR may fail.")
            _append_install_log("Launch warning: Poppler missing", "WARN")

    try:
        import tkinter  # noqa: F401
    except ImportError as exc:
        msg = f"Tkinter is unavailable in the private Python runtime: {exc}"
        _log(f"ERROR: {msg}")
        _append_install_log(msg, "ERROR")
        _log(f"See log: {windows_install_log()}")
        return 2

    cmd = [str(py), str(PROJECT_ROOT / "app.py"), "--gui"]
    _log("Starting text-seeker …")
    try:
        return subprocess.call(cmd, cwd=PROJECT_ROOT, env=env)
    except OSError as exc:
        _log(f"ERROR: Failed to launch app: {exc}")
        _append_install_log(f"Launch failed: {exc}", "ERROR")
        if platform_key() == "windows":
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
    py = ensure_portable_python()
    ensure_app_installed(py)
    _log(f"Ready. Python: {py}")
    return 0


def cmd_launch(_: argparse.Namespace) -> int:
    try:
        py = ensure_portable_python()
    except RuntimeError as exc:
        _log(f"ERROR: {exc}")
        if platform_key() == "windows":
            _log(f"See log: {windows_install_log()}")
        return 1
    ensure_app_installed(py)
    return launch_gui(py)


def cmd_doctor(_: argparse.Namespace) -> int:
    _append_install_log("=== bootstrap doctor ===")
    plat = platform_key()
    arch = machine_key()
    _doctor_line("Project root", str(PROJECT_ROOT))
    _doctor_line("OS", f"{platform.system()} {platform.release()} ({platform.version()})")
    _doctor_line("Architecture", f"{platform.machine()} / {arch}")

    if plat == "windows" and arch != "x86_64":
        _doctor_line("Windows support", "x64 only — current architecture may be unsupported", ok=False)

    py = runtime_python_exe(plat)
    py_found = py.is_file()
    _doctor_line("Python executable", str(py), ok=py_found)

    if py_found:
        code, out = _run_capture([str(py), "--version"])
        _doctor_line("Python version", out.splitlines()[0] if out else f"exit {code}", ok=code == 0)

        code, out = _run_capture([str(py), "-m", "pip", "--version"])
        _doctor_line("pip", out.splitlines()[0] if out else f"exit {code}", ok=code == 0)

        code, _ = _run_capture([str(py), "-c", "import tkinter; tkinter.Tk().destroy()"])
        _doctor_line("tkinter", "available" if code == 0 else "not available", ok=code == 0)
    else:
        _doctor_line("pip", "n/a (Python missing)", ok=False)
        _doctor_line("tkinter", "n/a (Python missing)", ok=False)

    stamp_ok = _stamp_matches()
    _doctor_line("Install stamp", str(STAMP_FILE), ok=stamp_ok)

    app_py = PROJECT_ROOT / "app.py"
    _doctor_line("app.py", str(app_py), ok=app_py.is_file())

    if plat == "windows":
        env = windows_process_env(py) if py_found else os.environ.copy()
        tess_exe = windows_tesseract_exe()
        tess_ok = tess_exe.is_file()
        tess_warn = bool(py_found and not tess_ok)
        _doctor_line(
            "Tesseract executable",
            str(tess_exe),
            ok=True if tess_ok else (False if not py_found else None),
            warn=tess_warn,
        )
        if tess_ok:
            code, out = _run_capture([str(tess_exe), "--version"], env=env)
            _doctor_line("Tesseract version", out.splitlines()[0] if out else f"exit {code}", ok=code == 0)

        pop_bin = windows_poppler_bin()
        pdftotext = pop_bin / "pdftotext.exe"
        pop_ok = pdftotext.is_file()
        pop_warn = bool(py_found and not pop_ok)
        _doctor_line("Poppler bin", str(pop_bin), ok=True if pop_ok else (False if not py_found else None), warn=pop_warn)
        _doctor_line(
            "pdftotext",
            str(pdftotext),
            ok=True if pop_ok else (False if not py_found else None),
            warn=pop_warn,
        )
        if pop_ok:
            code, out = _run_capture([str(pdftotext), "-v"], env=env)
            _doctor_line("pdftotext version", out.splitlines()[0] if out else f"exit {code}", ok=code == 0)
            pdftoppm = pop_bin / "pdftoppm.exe"
            if pdftoppm.is_file():
                code, out = _run_capture([str(pdftoppm), "-v"], env=env)
                _doctor_line("pdftoppm version", out.splitlines()[0] if out else f"exit {code}", ok=code == 0)
            else:
                _doctor_line("pdftoppm", str(pdftoppm), warn=bool(py_found))

        ocr_tag = ocr_tools_stamp(tesseract_ok=tess_ok, poppler_ok=pop_ok)
        if ocr_tag == "ok":
            _doctor_line("OCR capability", "ok (Tesseract and Poppler available)", ok=True)
        elif ocr_tag == "partial":
            detail = []
            if not tess_ok:
                detail.append("Tesseract missing")
            if not pop_ok:
                detail.append("Poppler missing")
            _doctor_line(
                "OCR capability",
                f"partial ({', '.join(detail)})",
                warn=bool(py_found),
            )
        else:
            _doctor_line(
                "OCR capability",
                "missing (Tesseract and Poppler unavailable)",
                warn=bool(py_found),
            )
        _doctor_line("Install log", str(windows_install_log()), ok=windows_install_log().is_file())

    _append_install_log("=== bootstrap doctor end ===")

    if plat == "windows" and not py_found:
        return 1
    if py_found:
        code, _ = _run_capture([str(py), "-c", "import tkinter"])
        if code != 0:
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
