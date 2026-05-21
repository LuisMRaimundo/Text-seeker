# How to Start text-seeker

## Quick Start (no Python required)

Use the **one-click installer** — see [installers/README.md](installers/README.md):

| Platform | Action |
|----------|--------|
| Windows 10/11 | `installers\windows\Install and Run.bat` |
| macOS | `installers/macos/Install and Run.command` |
| Linux | `./installers/linux/install-and-run.sh` |

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

2. **Check all modules are present:**
   - `boolean_parser.py`
   - `text_search.py`
   - `search_pdf.py`
   - `html_search.py`
   - `search_markdown.py`
   - `search_excel.py`
   - `search_csv.py`
   - `ocr_utils.py`
   - `save_results.py`
   - `indexing.py`
   - `performance_optimizer.py`
   - `main.py`

## Main Entry Point

**`app.py`** is the main orchestrator script. It:
- Launches GUI automatically if run without arguments
- Accepts `--gui` flag to explicitly launch GUI
- Handles command-line search operations
- Imports and uses `main.py` for GUI interface

## File Structure

```
text-seeker/
├── app.py                    # Main entry point (orchestrator)
├── main.py                   # GUI interface (run_interface function)
├── start_gui.bat             # GUI launcher
├── brand.py                  # App name and paths
├── nlp_utils.py              # Stemming, tokenization
├── text_extract.py           # Document text extraction
├── indexing.py               # Full-text indexing
├── performance_optimizer.py  # Parallel processing, BM25
├── boolean_parser.py          # Boolean search parser
├── search_pdf.py             # PDF search
├── text_search.py            # Text/DOCX search
├── html_search.py            # HTML search
├── search_markdown.py        # Markdown search
├── search_excel.py           # Excel search
├── search_csv.py              # CSV search
├── ocr_utils.py               # OCR utilities
└── save_results.py           # Result export
```

## Quick Test

To verify everything works:

```bash
python app.py --dir "." --query "test" --types "txt" --out test_results.html
```

This should search the current directory for "test" in text files and save results to `test_results.html`.
