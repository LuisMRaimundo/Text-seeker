# Autonomous installers (no Python required)

These launchers set up **text-seeker** and open the desktop search window. You do **not** need Python, pip, or conda installed beforehand (Windows wizard can also use an existing system Python).

**Requirements:** Internet on first run (~300–600 MB download). Disk space ~1 GB after install. Windows 10/11 **x64**, macOS 11+, or recent Linux (x86_64 or arm64).

---

## Windows 10 / 11

1. Open the project folder (or your ZIP after unpacking).
2. Double-click **`installers\windows\Install and Run.bat`** (or **`INSTALL.bat`** — same launcher).
3. The **installer wizard** opens on first run. Choose:
   - **Python** — private official installer (Tcl/Tk + pip), detected system Python (venv for packages), or custom path
   - **Packages** — `requirements.txt`
   - **Tesseract** / **Poppler** — install private, use detected, custom path, or skip
   - **PATH** — process-local only (default) or opt-in user PATH
4. The **text-seeker** window opens after a successful install.

**Configuration:** `installers\runtime\windows\install_state.json`  
**Log:** `installers\runtime\windows\install.log`  
**Details:** [installers/windows/README.md](windows/README.md)

The launcher uses **process-local PATH** by default — it does **not** modify system PATH unless you choose that in the wizard.

**OCR tools:** Tesseract and Poppler are optional. Text search and the GUI work without them; OCR/scanned-PDF features need both (or your own installs pointed to in the wizard).

---

## macOS

1. In Terminal, make the launcher executable (once):

   ```bash
   chmod +x "installers/macos/Install and Run.command"
   chmod +x installers/macos/setup-runtime.sh
   ```

2. Double-click **`installers/macos/Install and Run.command`**  
   (If blocked: **System Settings → Privacy & Security → Open Anyway**.)

---

## Linux

```bash
chmod +x installers/linux/install-and-run.sh installers/linux/setup-runtime.sh
./installers/linux/install-and-run.sh
```

---

## What gets installed?

| Location | Contents |
|----------|----------|
| `installers/runtime/` | Private Python, pip packages, Windows Tesseract/Poppler (gitignored) |
| `installers/runtime/windows/install_state.json` | Windows install choices (gitignored) |
| GUI | **text-seeker** Tkinter window |

**Diagnostics** (Windows — use Python path from `install_state.json`):

```bat
installers\runtime\windows\python\python.exe installers\common\bootstrap.py doctor
```

**Reinstall:** delete `installers/runtime/` and run the launcher again.

---

## Troubleshooting

| Problem | What to try |
|---------|-------------|
| Setup failed (Python/packages) | Check `install.log`; Python/tkinter/pip are required on Windows |
| Tesseract/Poppler failed (Windows) | Warning only — re-run wizard or install tools manually |
| GUI does not open | Run `doctor`; re-run **Install and Run.bat** |
| OCR missing | Re-run wizard; install or point to Tesseract + Poppler |

See also [README_STARTING.md](../README_STARTING.md) for manual Tesseract/Poppler install on dev machines.
