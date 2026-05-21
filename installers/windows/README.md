# text-seeker - Windows installation

**Repository:** https://github.com/LuisMRaimundo/Text-seeker

## Standard installation (no Python required)

1. Download the repo (**Code -> Download ZIP**) or clone it.
2. Open **`installers\windows`**.
3. Double-click **`INSTALL.bat`** or **`START-HERE.bat`** (same as **Install and Run.bat**).
4. Wait for the console window (**10-25 minutes** on first run is normal).
5. The **text-seeker** search window opens when setup finishes.

**Do not** use an old ZIP saved before May 2026. Download fresh from GitHub.

## Install log

`installers\runtime\windows\install.log`

## Troubleshooting

| Issue | Action |
|-------|--------|
| No window / closes instantly | Run **`INSTALL.bat`** from a fresh GitHub download. Never use `>>>` in batch files. |
| Setup failed | Open `install.log`, check Internet/firewall, delete `installers\runtime\` and retry. |
| PowerShell parse error | Re-download from GitHub; old copies may contain Unicode characters that break Windows PowerShell. |

## Developers

If Python is already installed: `pip install -r requirements.txt` then `python app.py --gui`
