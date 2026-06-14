"""Paths and download URLs for text-seeker autonomous installers."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

PYTHON_VERSION = "3.11.9"
PYTHON_MIN_VERSION = (3, 10)
INSTALLER_VERSION = "3"
STAMP_VERSION = "2"

# Pinned third-party Windows runtimes (keep in sync with installers/windows/setup.ps1)
WINDOWS_TESSERACT_VERSION = "5.4.0.20240606"
_TESSERACT_SETUP_NAME = f"tesseract-ocr-w64-setup-{WINDOWS_TESSERACT_VERSION}.exe"
# Primary: GitHub release asset (Mannheim direct URL often returns HTTP 403).
WINDOWS_TESSERACT_INSTALLER_URLS: tuple[str, ...] = (
    (
        "https://github.com/UB-Mannheim/tesseract/releases/download/"
        f"v{WINDOWS_TESSERACT_VERSION}/{_TESSERACT_SETUP_NAME}"
    ),
    (
        "https://digi.bib.uni-mannheim.de/tesseract/"
        f"{_TESSERACT_SETUP_NAME}"
    ),
)
# Back-compat alias — first (preferred) URL.
WINDOWS_TESSERACT_INSTALLER = WINDOWS_TESSERACT_INSTALLER_URLS[0]
WINDOWS_POPPLER_VERSION = "24.08.0-0"
WINDOWS_POPPLER_ZIP = (
    "https://github.com/oschwartz10612/poppler-windows/releases/download/"
    f"v{WINDOWS_POPPLER_VERSION}/Release-{WINDOWS_POPPLER_VERSION}.zip"
)

INSTALLERS_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = INSTALLERS_DIR.parent
RUNTIME_DIR = INSTALLERS_DIR / "runtime"
STAMP_FILE = RUNTIME_DIR / ".install_ok"
INSTALL_STATE_FILE = RUNTIME_DIR / "windows" / "install_state.json"
REQUIREMENTS = PROJECT_ROOT / "requirements.txt"

# install_state.json field names (keep in sync with installers/windows/installer_config.ps1)
STATE_INSTALLER_VERSION = "installer_version"
STATE_INSTALL_TIMESTAMP = "install_timestamp"
STATE_PYTHON_MODE = "python_mode"
STATE_PYTHON_PATH = "python_path"
STATE_PYTHON_SCRIPTS_PATH = "python_scripts_path"
STATE_VENV_PATH = "venv_path"
STATE_PACKAGES_INSTALLED = "packages_installed"
STATE_TESSERACT_MODE = "tesseract_mode"
STATE_TESSERACT_PATH = "tesseract_path"
STATE_POPPLER_MODE = "poppler_mode"
STATE_POPPLER_BIN = "poppler_bin"
STATE_PATH_POLICY = "path_policy"
STATE_USER_PATH_MODIFIED = "user_path_modified"
STATE_USER_PATH_ENTRIES = "user_path_entries_added"
STATE_PRIVATE_PYTHON_DIR = "private_python_dir"
STATE_PRIVATE_TESSERACT_DIR = "private_tesseract_dir"
STATE_PRIVATE_POPPLER_DIR = "private_poppler_dir"
STATE_RUNTIME_ROOT = "runtime_root"
STATE_OCR_CAPABILITY = "ocr_capability"
STATE_GUI_CAN_LAUNCH = "gui_can_launch"
STATE_TEXT_SEARCH_AVAILABLE = "text_search_available"

PATH_POLICY_PROCESS_LOCAL = "process_local"
PATH_POLICY_USER_TOOLS = "user_tools"
PATH_POLICY_USER_TOOLS_PYTHON = "user_tools_python"

PYTHON_MODE_SYSTEM = "system"
PYTHON_MODE_PRIVATE = "private"
PYTHON_MODE_CUSTOM = "custom"
PYTHON_MODE_VENV = "venv"

TOOL_MODE_DETECTED = "detected"
TOOL_MODE_PRIVATE = "private"
TOOL_MODE_CUSTOM = "custom"
TOOL_MODE_SKIP = "skip"

PBS_TAG = "20240415"


def windows_runtime_root() -> Path:
    return RUNTIME_DIR / "windows"


def platform_key() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    raise RuntimeError(f"Unsupported OS: {sys.platform}")


def machine_key() -> str:
    m = platform.machine().lower()
    if m in {"amd64", "x86_64", "x64"}:
        return "x86_64"
    if m in {"arm64", "aarch64"}:
        return "aarch64"
    raise RuntimeError(f"Unsupported CPU architecture: {platform.machine()}")


def windows_install_state_path() -> Path:
    return INSTALL_STATE_FILE


def load_install_state() -> dict | None:
    """Load Windows install_state.json; return None if missing or invalid."""
    path = windows_install_state_path()
    if not path.is_file():
        return None
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def default_private_venv_dir() -> Path:
    return windows_runtime_root() / "venv"


def resolve_python_exe_from_state(state: dict | None = None) -> Path | None:
    """Return configured Python executable from install state."""
    state = state if state is not None else load_install_state()
    if not state:
        legacy = runtime_python_exe("windows")
        return legacy if legacy.is_file() else None
    raw = state.get(STATE_PYTHON_PATH) or ""
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_file() else None


def resolve_tesseract_exe_from_state(state: dict | None = None) -> Path | None:
    state = state if state is not None else load_install_state()
    if state and state.get(STATE_TESSERACT_MODE) == TOOL_MODE_SKIP:
        return None
    raw = (state or {}).get(STATE_TESSERACT_PATH) or ""
    if raw:
        path = Path(raw)
        if path.is_file():
            return path
    legacy = windows_tesseract_exe()
    return legacy if legacy.is_file() else None


def resolve_poppler_bin_from_state(state: dict | None = None) -> Path | None:
    state = state if state is not None else load_install_state()
    if state and state.get(STATE_POPPLER_MODE) == TOOL_MODE_SKIP:
        return None
    raw = (state or {}).get(STATE_POPPLER_BIN) or ""
    if raw:
        path = Path(raw)
        if path.is_dir():
            return path
    legacy = windows_poppler_bin()
    return legacy if legacy.is_dir() else None


def process_path_parts_from_state(state: dict | None, py: Path) -> list[str]:
    """Build process-local PATH prepend list from install state."""
    state = state or {}
    parts: list[str] = []
    py_dir = py.parent
    scripts = state.get(STATE_PYTHON_SCRIPTS_PATH) or str(py_dir / "Scripts")
    venv = state.get(STATE_VENV_PATH) or ""
    if venv:
        vpath = Path(venv)
        if (vpath / "Scripts").is_dir():
            parts.extend([str(vpath / "Scripts"), str(vpath)])
        elif vpath.is_dir():
            parts.append(str(vpath))
    parts.extend([str(py_dir), scripts])

    tess_raw = state.get(STATE_TESSERACT_PATH) or ""
    if tess_raw and state.get(STATE_TESSERACT_MODE) != TOOL_MODE_SKIP:
        parts.append(str(Path(tess_raw).parent))

    pop_raw = state.get(STATE_POPPLER_BIN) or ""
    if pop_raw and state.get(STATE_POPPLER_MODE) != TOOL_MODE_SKIP:
        parts.append(str(Path(pop_raw)))

    # De-duplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for item in parts:
        norm = str(Path(item))
        if norm not in seen:
            seen.add(norm)
            unique.append(norm)
    return unique


def windows_install_log() -> Path:
    return windows_runtime_root() / "install.log"


def runtime_python_dir(platform_name: str) -> Path:
    return RUNTIME_DIR / platform_name / "python"


def runtime_python_exe(platform_name: str) -> Path:
    base = runtime_python_dir(platform_name)
    if platform_name == "windows":
        return base / "python.exe"
    return base / "bin" / "python3"


def windows_python_installer_url() -> str:
    return (
        f"https://www.python.org/ftp/python/{PYTHON_VERSION}/"
        f"python-{PYTHON_VERSION}-amd64.exe"
    )


FORBIDDEN_WINDOWS_PYTHON_URL_PARTS = (
    "embed-amd64",
    "embed-win32",
    "embed-arm64",
    "get-pip.py",
)


def assert_official_windows_python_installer_url(url: str) -> None:
    """Reject legacy embeddable-Python URLs — GUI requires full Tcl/Tk runtime."""
    lower = url.lower()
    for part in FORBIDDEN_WINDOWS_PYTHON_URL_PARTS:
        if part in lower:
            raise ValueError(
                f"Forbidden Windows Python URL (embed/get-pip not allowed): {url!r}"
            )
    if not lower.endswith("-amd64.exe"):
        raise ValueError(f"Windows Python URL must be official amd64 .exe installer: {url!r}")


def windows_tesseract_installer_urls() -> tuple[str, ...]:
    """Return Tesseract installer URLs in try order (GitHub first, Mannheim fallback)."""
    return WINDOWS_TESSERACT_INSTALLER_URLS


def windows_tesseract_dir() -> Path:
    return windows_runtime_root() / "tesseract"


def windows_tesseract_exe() -> Path:
    return windows_tesseract_dir() / "tesseract.exe"


def windows_tesseract_tessdata_dir() -> Path:
    return windows_tesseract_dir() / "tessdata"


def windows_poppler_root() -> Path:
    return windows_runtime_root() / "poppler"


def windows_poppler_bin() -> Path:
    """Return Poppler bin directory (normalized after setup extract)."""
    direct = windows_poppler_root() / "bin"
    if direct.is_dir():
        return direct
    library = windows_poppler_root() / "Library" / "bin"
    if library.is_dir():
        return library
    for candidate in windows_poppler_root().rglob("pdftotext.exe"):
        return candidate.parent
    return direct


def pbs_artifact(platform_name: str, arch: str) -> str:
    triples = {
        ("windows", "x86_64"): "x86_64-pc-windows-msvc",
        ("macos", "x86_64"): "x86_64-apple-darwin",
        ("macos", "aarch64"): "aarch64-apple-darwin",
        ("linux", "x86_64"): "x86_64-unknown-linux-gnu",
        ("linux", "aarch64"): "aarch64-unknown-linux-gnu",
    }
    triple = triples.get((platform_name, arch))
    if not triple:
        raise RuntimeError(f"No portable Python build for {platform_name} / {arch}")
    return f"cpython-{PYTHON_VERSION}+{PBS_TAG}-{triple}-install_only.tar.gz"


def pbs_download_url(platform_name: str, arch: str) -> str:
    name = pbs_artifact(platform_name, arch)
    return (
        "https://github.com/astral-sh/python-build-standalone/releases/download/"
        f"{PBS_TAG}/{name}"
    )


def ocr_tools_stamp(*, tesseract_ok: bool, poppler_ok: bool) -> str:
    """Stamp value: ok (both tools), partial (one), missing (neither)."""
    if tesseract_ok and poppler_ok:
        return "ok"
    if tesseract_ok or poppler_ok:
        return "partial"
    return "missing"


def stamp_payload(
    *,
    tesseract_ok: bool = False,
    poppler_ok: bool = False,
) -> str:
    req = REQUIREMENTS.stat().st_mtime_ns if REQUIREMENTS.is_file() else 0
    ocr = ocr_tools_stamp(tesseract_ok=tesseract_ok, poppler_ok=poppler_ok)
    return (
        f"v={STAMP_VERSION}\n"
        f"root={PROJECT_ROOT.resolve()}\n"
        f"requirements={req}\n"
        f"python={PYTHON_VERSION}\n"
        f"tesseract={WINDOWS_TESSERACT_VERSION if tesseract_ok else 'missing'}\n"
        f"poppler={WINDOWS_POPPLER_VERSION if poppler_ok else 'missing'}\n"
        f"ocr_tools={ocr}\n"
    )
