# Manual installation on Windows 10 / 11

**text-seeker** is a local/offline text-search tool. After its dependencies are
installed it needs **no internet connection** to run.

There is **no automatic installer**. The previous one-click installer was removed
because Python, Tesseract and Poppler are independent Windows programs with their
own installers, PATH behaviour, permissions, architecture and download quirks —
auto-installing them proved unreliable. Install the three dependencies **manually**
(once), then install the Python packages and run the app.

> **OCR note:** Tesseract and Poppler are **only** needed for OCR of **scanned PDFs
> and images**. Plain text files and text-based PDFs/DOCX/HTML/etc. work **without**
> them. If you do not need OCR, you can skip steps 2 and 3.

---

## 1. Python 3.10 (64-bit)

Download the official installer:

- Release page: <https://www.python.org/downloads/release/python-31011/>
- On that page, download **"Windows installer (64-bit)"**.

> **Do NOT use the "Windows embeddable package".** It lacks tkinter and pip and will
> not work. Use the normal **Windows installer (64-bit)**.

During installation:

- Tick **"Add python.exe to PATH"** on the first screen.
- Use the default options so **pip** and **tcl/tk and IDLE (tkinter)** are installed.
- Finish the install, then **close and reopen** any open terminal/PowerShell window
  (PATH changes only apply to new terminals).

Verify (open a new terminal):

```bat
python --version
python -m pip --version
python -c "import tkinter; print('tkinter OK')"
```

All three must succeed (a version line, a pip version line, and `tkinter OK`).

Python 3.11 or 3.12 (64-bit) also work; 3.10+ is the minimum.

---

## 2. Tesseract OCR (optional — for scanned PDFs / image OCR)

Use the UB Mannheim build:

- Documentation: <https://ub-mannheim.github.io/Tesseract_Dokumentation/Tesseract_Doku_Windows.html>
- Downloads (releases): <https://github.com/UB-Mannheim/tesseract/releases>

Steps:

- Download the **64-bit Windows installer**.
- Install normally.
- Include **English** language data at minimum.
- Optionally include **Portuguese** (`por`) and any other languages you need to OCR.
  (text-seeker's OCR uses `por+eng` by default.)
- If the installer offers to **add Tesseract to PATH**, accept it. If not, manually
  add the folder that contains `tesseract.exe` to your PATH — typically
  `C:\Program Files\Tesseract-OCR`.
- **Close and reopen** the terminal.

Verify:

```bat
tesseract --version
```

To add a folder to PATH manually: Start → search **"Edit environment variables for
your account"** → **Environment Variables** → under **User variables** select
**Path** → **Edit** → **New** → paste the folder → **OK**, then reopen the terminal.

---

## 3. Poppler (optional — required to render PDF pages for OCR)

Use the Windows Poppler binaries:

- Project: <https://github.com/oschwartz10612/poppler-windows>
- Releases: <https://github.com/oschwartz10612/poppler-windows/releases>

Steps:

- Download the latest Windows release **ZIP**.
- Extract it, for example to `C:\Tools\poppler`.
- Find the **`bin`** folder inside the extracted files. It is usually:
  - `C:\Tools\poppler\Library\bin`, or
  - `C:\Tools\poppler\bin`
- Add **that `bin` folder** to your PATH (same steps as above).
- **Close and reopen** the terminal.

Verify:

```bat
pdftotext -v
pdftoppm -v
```

If Poppler is missing, text-based PDF search still works; only OCR of scanned PDF
pages may fail.

---

## 4. Install the Python packages

Get the code (download the repo ZIP and extract it, or `git clone`), then in a new
terminal:

```bat
cd C:\path\to\Text-seeker
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Prefer to keep dependencies isolated? Use a virtual environment first:

```bat
cd C:\path\to\Text-seeker
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## 5. Run text-seeker

```bat
cd C:\path\to\Text-seeker
python app.py --gui
```

On Windows you can also double-click **`start_gui.bat`** (it just launches the GUI
with your installed Python — it does **not** install anything).

---

## 6. Verification checklist

Run each line in a **new** terminal from the project folder:

```bat
python --version
python -m pip --version
python -c "import tkinter; print('tkinter OK')"
tesseract --version
pdftotext -v
pdftoppm -v
python -m unittest discover -s tests -v
python app.py --gui
```

- The first three are **required** (Python, pip, tkinter).
- `tesseract`, `pdftotext`, `pdftoppm` are **only** needed for OCR / scanned PDFs.
- `python -m unittest ...` should end with `OK`.
- `python app.py --gui` should open the search window.

---

## 7. Troubleshooting

**`'python' is not recognized`**
Python is not on PATH. Reinstall Python with **"Add python.exe to PATH"** ticked, or
add the Python folder (e.g. `C:\Users\<you>\AppData\Local\Programs\Python\Python311`
and its `Scripts` subfolder) to PATH, then reopen the terminal.

**Typing `python` opens the Microsoft Store**
Windows ships a "Store alias" stub. Turn it off: Start → **"Manage app execution
aliases"** → switch **OFF** "python.exe" and "python3.exe". Then use the real Python
you installed (reopen the terminal).

**`pip` not found**
Use `python -m pip ...` instead of `pip ...`. If still missing, repair the Python
install and ensure **pip** is selected.

**`tkinter` missing (`ModuleNotFoundError: No module named 'tkinter'`)**
Your Python was installed without Tcl/Tk. Re-run the Python installer → **Modify** →
ensure **"tcl/tk and IDLE"** is checked. (The embeddable package never has tkinter —
use the normal installer.)

**`'tesseract' is not recognized`**
Tesseract isn't on PATH. Add the folder containing `tesseract.exe` (e.g.
`C:\Program Files\Tesseract-OCR`) to PATH and reopen the terminal. You can also set
the environment variable `TESSERACT_PATH` to the full path of `tesseract.exe`.

**`'pdftotext'` / `'pdftoppm'` not recognized**
Poppler's `bin` folder isn't on PATH. Add the correct `bin` folder (`...\Library\bin`
or `...\bin`) to PATH, or set `POPPLER_PATH` to that folder, then reopen the terminal.

**PATH changes don't take effect**
PATH is only read by **new** terminals. Close all terminal windows and open a new one
after changing PATH.

**OCR finds nothing in scanned PDFs**
Make sure both Tesseract **and** Poppler are installed and on PATH, and that the
Tesseract **language pack** for your documents is installed (e.g. Portuguese `por`).
OCR is still slower than text extraction. Defaults limit OCR to the first **150**
pages per PDF (like older builds). There is **no per-file skip by default**.
Use **OCR Mode = never** for text-layer PDFs, or **Pre-scan OCR** to skip heavy
files. Optional: `TEXT_SEEKER_FILE_TIMEOUT` / `--file-timeout` (seconds of active
work per file).

**Do I need Tesseract/Poppler at all?**
Only for OCR of **scanned** PDFs and images. Plain text, text-based PDFs, DOCX, HTML,
Markdown, Excel and CSV work without them.

---

See also: [README.md](README.md) · [README_STARTING.md](README_STARTING.md) ·
[QUICK_GUIDE.md](QUICK_GUIDE.md) (query syntax) · [TECHNICAL_MANUAL.md](TECHNICAL_MANUAL.md).
