# text-seeker

**Repository:** [github.com/LuisMRaimundo/Text-seeker](https://github.com/LuisMRaimundo/Text-seeker)

Multi-format **boolean full-text search** for local documents (PDF, DOCX, HTML, TXT, Markdown, Excel, CSV, images via OCR). Runs **offline** on your machine; indexes and caches live under your home directory.

**Supported formats:** TXT, PDF, DOCX, HTML, Markdown, Excel (`.xlsx`/`.xls`), CSV, common image formats (OCR).

## No Python installed? (one-click)

See **[installers/README.md](installers/README.md)**:

| Platform | Launcher |
|----------|----------|
| **Windows 10/11 (x64)** | `installers\windows\Install and Run.bat` or `INSTALL.bat` — opens an installer wizard on first run |
| **macOS** | Double-click `installers/macos/Install and Run.command` (after `chmod +x`) |
| **Linux** | `./installers/linux/install-and-run.sh` |

First run downloads a private runtime and libraries (~200–400 MB). No system Python required on Windows/macOS/Linux installers. On Windows, choices are saved to `installers/runtime/windows/install_state.json`. See [installers/README.md](installers/README.md).

## Developers (Python already installed)

```bash
pip install -r requirements.txt
python app.py --gui
```

Or: `start_gui.bat` (Windows, if Python is on PATH).

## Tests

```bat
run_tests.bat
```

Or: `python -m unittest discover -s tests -v`

Continuous integration runs the same test suite on push (see `.github/workflows/test.yml`).

## Repository layout

| Path | Role |
|------|------|
| `app.py`, `main.py` | CLI orchestrator and Tkinter GUI |
| `boolean_parser.py`, `nlp_utils.py` | Query parsing, stemming, tokenization |
| `indexing.py`, `text_extract.py` | Inverted index and full-document extraction |
| `search_*.py`, `html_search.py`, `text_search.py` | Per-format search |
| `installers/` | One-click setup (Windows wizard + private runtime on first run) |
| `tests/` | Unit and integration tests |

## Documentation

| File | Contents |
|------|----------|
| [README_STARTING.md](README_STARTING.md) | Launch, optional Tesseract & Poppler |
| [QUICK_GUIDE.md](QUICK_GUIDE.md) | Boolean query syntax |
| [TECHNICAL_MANUAL.md](TECHNICAL_MANUAL.md) | Architecture |

## Data directories

| Purpose | Path |
|---------|------|
| Search index | `~/.text-seeker_index/` |
| PDF/OCR cache | `~/.text-seeker_cache/` |

## Copyright and use

Copyright © 2026 Luís Raimundo. All rights reserved.

This repository and its contents are proprietary research material. **No open-source licence is granted.** No permission to copy, redistribute, modify, publish, or derive works without prior written permission from the copyright holder.

**Contact:** lmr.2020@outlook.pt

## Acknowledgements

This project was developed by **Luís Raimundo** with the support and funding of the **Fundação para a Ciência e a Tecnologia (FCT)** and **Universidade NOVA de Lisboa**.

**Funding DOI:** [https://doi.org/10.54499/2020.08817.BD](https://doi.org/10.54499/2020.08817.BD)

The author also gratefully acknowledges **Isabel Pires** for her support throughout the development of this work.
