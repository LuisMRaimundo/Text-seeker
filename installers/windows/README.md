# text-seeker - Windows installation

**Repository:** https://github.com/LuisMRaimundo/Text-seeker

## Files in this folder

| File | Purpose |
|------|---------|
| `Install and Run.bat` | Main launcher — opens installer wizard if needed, then starts the app |
| `INSTALL.bat` | Short alias for `Install and Run.bat` |
| `installer_ui.ps1` | Installer wizard (Windows Forms; console fallback) |
| `installer_config.ps1` | Detection, downloads, install logic (used by the wizard) |
| `installer_wizard_logic.ps1` | Wizard step/navigation helpers (testable) |
| `tests/InstallWizard.Tests.ps1` | Installer navigation unit tests |
| `tests/Run-InstallerTests.bat` | Run installer tests |

Runtime data (not in Git): `installers\runtime\windows\` — Python, tools, `install_state.json`, `install.log`.

## Standard installation (no Python required)

1. Download the repo (**Code → Download ZIP**) from [main](https://github.com/LuisMRaimundo/Text-seeker/archive/refs/heads/main.zip) or clone it.
2. Open **`installers\windows`**.
3. Double-click **`INSTALL.bat`** or **`Install and Run.bat`**.
4. The **text-seeker installer** opens (Windows Forms wizard; console fallback if WinForms is unavailable).
5. Choose Python, packages, Tesseract, Poppler, and PATH options, then click **Install**.
6. The search window opens when setup finishes.

## Installer choices

| Component | Options |
|-----------|---------|
| **Python** | Use detected system Python (venv for packages), install private Python (official amd64 + Tcl/Tk), or custom `python.exe` path |
| **Packages** | Install `requirements.txt` into the chosen environment |
| **Tesseract** | Install private, use detected, custom path, or skip |
| **Poppler** | Install private, use detected, custom bin folder, or skip |
| **PATH** | Process-local only (default), or opt-in user PATH for tools and/or Python Scripts |

Configuration is saved to **`installers\runtime\windows\install_state.json`**.

**Supported:** Windows 10/11 **x64 only** (ARM64 is rejected with a clear message).

## Default PATH policy

**Process-local PATH only** — Text-seeker prepends runtime paths when launching the app. Windows user/system PATH is **not** modified unless you explicitly choose that in the installer wizard (PATH step).

## Install log

`installers\runtime\windows\install.log`

## Installer tests

From this folder:

```bat
tests\Run-InstallerTests.bat
```

Or:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests\InstallWizard.Tests.ps1
```

Project-wide tests also include wizard policy checks in `tests/test_windows_installer_runtime.py`.

## Diagnostics

Use the Python path from `install_state.json`, or the default private runtime:

```bat
installers\runtime\windows\python\python.exe installers\common\bootstrap.py doctor
```

## Troubleshooting

| Issue | Action |
|-------|--------|
| Installer cancelled | Re-run **Install and Run.bat** |
| Setup failed on Python/packages | Check log; Python/tkinter/pip/packages are hard requirements |
| "Custom Python is not usable" | Point Custom Python at a real `python.exe` (or the folder containing it) with Python 3.10+, pip, and tkinter |
| Tesseract/Poppler failed | Warning only — GUI still runs; OCR features limited |
| OCR disabled | Re-run installer; install private tools or point to existing copies |
| ARM64 PC | Not supported — use x64 Windows |
| Old ZIP / embed Python errors | Download a fresh ZIP from **main**; delete `installers\runtime\` and reinstall |
| `Unexpected token` / parse errors in `installer_ui.ps1` | Caused by non-ASCII characters in a `.ps1` file read by Windows PowerShell 5.1. Re-download a fresh ZIP from **main**. |

## Developers

If Python 3.10+ with tkinter is already installed:

```bat
pip install -r requirements.txt
python app.py --gui
```

**Installer scripts must be pure ASCII.** Windows PowerShell 5.1 reads BOM-less
`.ps1` files as Windows-1252, so non-ASCII characters (e.g. `—`) corrupt parsing.
Use plain `-` instead. This is enforced by `tests/InstallWizard.Tests.ps1` and
`tests/test_windows_installer_runtime.py`.
