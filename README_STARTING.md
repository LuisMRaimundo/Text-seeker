# How to Start text-seeker

**See also:** [README.md](README.md) · [QUICK_GUIDE.md](QUICK_GUIDE.md) (query syntax) · [TECHNICAL_MANUAL.md](TECHNICAL_MANUAL.md) (architecture)

## Quick Start (no Python required)

Use the **one-click installer** — see [installers/README.md](installers/README.md):

| Platform | Action |
|----------|--------|
| Windows 10/11 (x64) | `installers\windows\Install and Run.bat` or `INSTALL.bat` |
| macOS | `installers/macos/Install and Run.command` |
| Linux | `./installers/linux/install-and-run.sh` |

On **Windows**, the first run opens an installer wizard where you choose Python, packages, Tesseract, Poppler, and PATH handling. Settings are stored in `installers\runtime\windows\install_state.json`.

## If Python is already installed

### Option 1: Double-click the batch file
- **`start_gui.bat`** — launches the GUI (uses `pythonw` when available)

### Option 2: Run from command line

```bash
# Launch GUI (automatic if no arguments)
python app.py

# Or explicitly with --gui flag
python app.py --gui
```

### Option 3: Run from Python directly

```python
from app import _launch_gui_with_fallback
_launch_gui_with_fallback()
```

## Command Line Usage

```bash
# Search with command line
python app.py --dir "C:\path\to\docs" --query "textur* AND uniform*" --types "pdf,txt,docx"

# With output file
python app.py --dir "C:\path\to\docs" --query "search terms" --out results.html

# Full options
python app.py --dir "C:\docs" --query "query" --types "pdf,txt" --minrel 0.5 --ctx 200 --ocr auto --out results.html --fmt html
```

## Troubleshooting

### Batch file not working?

1. **Check Python is installed:**
   ```bash
   python --version
   ```

2. **Try running directly:**
   ```bash
   python app.py
   ```

3. **Check for errors:**
   - Open command prompt in the folder
   - Run: `python app.py --gui`
   - Check error messages

### GUI not starting?

1. **Check Tkinter is available:**
   ```python
   python -c "import tkinter; print('Tkinter OK')"
   ```

2. **Install Tkinter if missing:**
   - Windows: Usually included with Python
   - Linux: `sudo apt-get install python3-tk`
   - Mac: Usually included

### Import errors?

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Check core modules are present** (project root): `app.py`, `main.py`, `brand.py`, `boolean_parser.py`, `nlp_utils.py`, `text_extract.py`, `indexing.py`, `performance_optimizer.py`, and the `search_*.py` / `html_search.py` / `text_search.py` / `ocr_utils.py` / `save_results.py` files.

## Optional: Tesseract and Poppler

These are **system tools**, not Python packages. **text-seeker works without them** for text-based PDFs and non-OCR formats. Install them when you need **scanned PDFs** or **image OCR**.

### Tesseract OCR

| Platform | Install |
|----------|---------|
| **Windows** | Use the installer wizard (private download or point to existing), or [UB Mannheim builds](https://github.com/UB-Mannheim/tesseract/wiki). The app also checks `TESSERACT_PATH` and common install paths. |
| **macOS** | `brew install tesseract` |
| **Linux** | `sudo apt install tesseract-ocr` (Debian/Ubuntu) or your distro equivalent |

**Custom path:** set environment variable `TESSERACT_PATH` to the full path of `tesseract.exe` (Windows) or the `tesseract` binary.

On startup, the app prints `[OK] Tesseract: …` when found, or a warning if OCR may be unavailable.

### Poppler (PDF → image for OCR)

Required by `pdf2image` when OCR must render PDF pages to images.

| Platform | Install |
|----------|---------|
| **Windows** | Installer wizard (private Poppler zip), [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases), or set `POPPLER_PATH` to the `bin` folder |
| **macOS** | `brew install poppler` |
| **Linux** | `sudo apt install poppler-utils` |

If Poppler is missing, text-based PDF search still works; only OCR on scanned pages may fail.

## User data folders

| Purpose | Default path |
|---------|----------------|
| Search index | `~/.text-seeker_index/` |
| PDF/OCR cache | `~/.text-seeker_cache/` |

If you used an older **DocSeeker** build, indexes under `~/.docseeker_index/` are migrated automatically on first run.

## Main Entry Point

**`app.py`** is the main orchestrator script. It:
- Launches GUI automatically if run without arguments
- Accepts `--gui` flag to explicitly launch GUI
- Handles command-line search operations
- Imports and uses `main.py` for GUI interface

## File Structure

```
text-seeker/
├── app.py                    # Main entry (CLI + GUI launcher)
├── main.py                   # Tkinter GUI
├── start_gui.bat             # Windows GUI shortcut (Python on PATH)
├── run_tests.bat             # Run unit tests
├── requirements.txt
├── brand.py                  # App name and data paths
├── boolean_parser.py         # Boolean query parser
├── nlp_utils.py              # Stemming, tokenization
├── text_extract.py           # Full-document extraction (index)
├── indexing.py               # Inverted index (JSON under ~/.text-seeker_index/)
├── performance_optimizer.py  # Parallel search, BM25
├── search_pdf.py             # PDF search (+ OCR path)
├── text_search.py            # TXT / DOCX
├── html_search.py            # HTML
├── search_markdown.py        # Markdown
├── search_excel.py           # Excel
├── search_csv.py             # CSV
├── ocr_utils.py              # Tesseract integration
├── save_results.py           # Export HTML / TXT / CSV / Excel
├── installers/               # One-click installers (no system Python)
├── tests/                    # unittest suite
└── .github/workflows/        # CI (tests on push)
```

## Quick Test

To verify everything works:

```bash
python app.py --dir "." --query "test" --types "txt" --out test_results.html
```

This searches the current directory for `test` in `.txt` files and writes `test_results.html` (gitignored if you commit from a dev tree).
