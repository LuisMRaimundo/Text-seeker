# text-seeker - Windows installation



**Repository:** https://github.com/LuisMRaimundo/Text-seeker



## Standard installation (no Python required)



1. Download the repo (**Code -> Download ZIP**) or clone it.

2. Open **`installers\windows`**.

3. Double-click **`INSTALL.bat`** or **`Install and Run.bat`**.

4. The **text-seeker installer** opens (Windows Forms wizard; console fallback if WinForms unavailable).

5. Choose Python, packages, Tesseract, Poppler, and PATH options, then click **Install**.

6. The search window opens when setup finishes.



## Installer choices



| Component | Options |

|-----------|---------|

| **Python** | Use detected system Python (venv for packages), install private Python (official amd64 + Tcl/Tk), or custom `python.exe` path |

| **Packages** | Install `requirements.txt` into chosen environment |

| **Tesseract** | Install private, use detected, custom path, or skip |

| **Poppler** | Install private, use detected, custom bin folder, or skip |

| **PATH** | Process-local only (default), or opt-in user PATH for tools and/or Python Scripts |



Configuration is saved to **`installers\runtime\windows\install_state.json`**.



**Supported:** Windows 10/11 **x64 only** (ARM64 rejected).



**Do not** use an old ZIP from before the installer redesign. Download fresh from the PR branch or GitHub after merge.



## Default PATH policy



**Process-local PATH only** — Text-seeker prepends runtime paths when launching. Windows user/system PATH is **not** modified unless you explicitly choose that in the installer wizard (PATH step).



## Install log



`installers\runtime\windows\install.log`



## Diagnostics



```bat

installers\runtime\windows\python\python.exe installers\common\bootstrap.py doctor

```



(or the Python path recorded in `install_state.json`)



## Troubleshooting



| Issue | Action |

|-------|--------|

| Installer cancelled | Re-run **Install and Run.bat** |

| Setup failed on Python/packages | Check log; fix Python/tkinter/pip — hard requirements |

| Tesseract/Poppler failed | Warning only — GUI still runs; OCR features limited |

| OCR disabled | Re-run installer; choose install private or point to existing tools |

| ARM64 PC | Not supported — use x64 Windows |



## Developers



If Python is already installed: `pip install -r requirements.txt` then `python app.py --gui`

