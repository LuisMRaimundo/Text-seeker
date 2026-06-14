# text-seeker - Windows installation

**Repository:** https://github.com/LuisMRaimundo/Text-seeker

## Standard installation (no Python required)

1. Download the repo (**Code -> Download ZIP**) or clone it.
2. Open **`installers\windows`**.
3. Double-click **`INSTALL.bat`** or **`START-HERE.bat`** (same as **Install and Run.bat**).
4. Wait for the console window (**20-40 minutes** on first run is normal).
5. The **text-seeker** search window opens when setup finishes.

**First run installs privately (no admin, no system PATH):**

| Component | Location |
|-----------|----------|
| Python 3.11 + Tcl/Tk + pip | `installers\runtime\windows\python\` |
| Tesseract OCR (UB Mannheim build) | `installers\runtime\windows\tesseract\` |
| Poppler utilities | `installers\runtime\windows\poppler\bin\` |
| Python packages | private pip into the runtime above |

Tesseract is downloaded from the **UB-Mannheim GitHub release** first; the Mannheim university mirror is tried as fallback. If all mirrors fail (403/404/timeout), setup **continues** with a warning — text search and the GUI still work; only OCR/scanned-PDF features are disabled.

The launcher prepends these folders to **process PATH** when starting the app.

**Supported:** Windows 10/11 **x64 only** (ARM64 is rejected with a clear message).

**Do not** use an old ZIP saved before 2026. Download fresh from GitHub.

## Install log

`installers\runtime\windows\install.log`

## Diagnostics

After setup (or with system Python from project root):

```bat
python installers\common\bootstrap.py doctor
```

Or with the private runtime:

```bat
installers\runtime\windows\python\python.exe installers\common\bootstrap.py doctor
```

## Troubleshooting

| Issue | Action |
|-------|--------|
| No window / closes instantly | Run **`INSTALL.bat`** from a fresh GitHub download. |
| Setup failed | Open `install.log`, check Internet/firewall, delete `installers\runtime\` and retry. |
| ARM64 PC | Not supported yet — use x64 Windows or install Python manually. |
| OCR/scanned PDF disabled | Setup warns if Tesseract/Poppler failed; text search still works. |
| PowerShell parse error | Re-download from GitHub; old copies may contain broken Unicode. |

## Optional: add tools to user PATH

**Not required.** Double-click **`Add-Tools-To-User-Path.bat`** only if you want `tesseract` / `pdftotext` in new terminals without the launcher.

## Developers

If Python is already installed: `pip install -r requirements.txt` then `python app.py --gui`
