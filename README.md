# text-seeker

**Repository:** [github.com/LuisMRaimundo/Text-seeker](https://github.com/LuisMRaimundo/Text-seeker)

Multi-format **boolean full-text search** for local documents (PDF, DOCX, HTML, TXT, Markdown, Excel, CSV, images via OCR). Runs **offline** on your machine; indexes and caches live under your home directory.

**Supported formats:** TXT, PDF, DOCX, HTML, Markdown, Excel (`.xlsx`/`.xls`), CSV, common image formats (OCR).

## Requirements

- **Python 3.10+** with **tkinter** (the GUI) and **pip**.
- The Python packages in `requirements.txt`.
- **Optional** for OCR of scanned PDFs / images: **Tesseract OCR** and **Poppler** as system tools. See [README_STARTING.md](README_STARTING.md).

## Install and run

```bash
pip install -r requirements.txt
python app.py --gui
```

On Windows you can also double-click **`start_gui.bat`** once Python is installed and on PATH.

**Windows users:** there is **no automatic installer** — see **[INSTALL_WINDOWS.md](INSTALL_WINDOWS.md)** for step-by-step manual setup of Python, Tesseract and Poppler, with verification and troubleshooting.

> Tip: use a virtual environment if you prefer to keep dependencies isolated:
> ```bash
> python -m venv .venv
> .venv\Scripts\activate      # Windows  (or: source .venv/bin/activate)
> pip install -r requirements.txt
> python app.py --gui
> ```

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
| `tests/` | Unit and integration tests |

## Documentation

| File | Contents |
|------|----------|
| [INSTALL_WINDOWS.md](INSTALL_WINDOWS.md) | Manual Windows 10/11 setup (Python, Tesseract, Poppler) |
| [README_STARTING.md](README_STARTING.md) | Install, launch, optional Tesseract & Poppler |
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
