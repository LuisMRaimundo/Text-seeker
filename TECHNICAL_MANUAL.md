# text-seeker — Technical Manual
## Complete Reference

---

# Table of Contents
1. [Introduction](#1-introduction)
2. [System Architecture](#2-system-architecture)
3. [Installation and Dependencies](#3-installation-and-dependencies)
4. [Module Reference](#4-module-reference)
5. [Mathematical Algorithms and Formulas](#5-mathematical-algorithms-and-formulas)
6. [Tutorial](#6-tutorial)
7. [Bibliography](#7-bibliography)

---

# 1. Introduction

**text-seeker** is a multi-format document search application that performs full-text Boolean search across local files. It supports:

- **Boolean queries** with operators: AND, OR, NOT, NEAR/x
- **Wildcards**: `*` (zero or more chars), `?` (exactly one char)
- **Phrases** in double or single quotes
- **File formats**: TXT, PDF, DOCX, HTML, Markdown, Excel (XLSX/XLS), CSV, Images (OCR)
- **Output formats**: HTML, TXT, CSV, Excel
- **Performance features**: Inverted-index search, parallel processing, file caching, BM25 ranking

The system uses a **shunting-yard** algorithm for query parsing and **RPN** (Reverse Polish Notation) for evaluation. OCR fallback is available for PDFs and images via Tesseract.

---

# 2. System Architecture

```
text-seeker/
├── app.py                   # Orchestrator; CLI entry
├── main.py                  # Tkinter GUI
├── brand.py                 # App name and data paths (~/.text-seeker_*)
├── boolean_parser.py        # BooleanSearchParser (shunting-yard, NEAR)
├── nlp_utils.py             # Stemming, CJK tokenization
├── text_extract.py          # Full-document extraction (index + BM25)
├── text_search.py           # TXT, DOCX
├── search_pdf.py            # PDF (multi-extractor + OCR)
├── html_search.py           # HTML
├── search_markdown.py       # Markdown
├── search_excel.py          # Excel
├── search_csv.py            # CSV
├── ocr_utils.py             # Tesseract OCR
├── save_results.py          # HTML/TXT/CSV/Excel export
├── indexing.py              # Inverted index (JSON; migrates .docseeker_index)
├── performance_optimizer.py # ParallelProcessor, BM25
├── start_gui.bat            # Windows launcher (Python on PATH)
├── run_tests.bat            # unittest runner
├── requirements.txt
├── tests/                   # Unit + integration tests
└── .github/workflows/       # CI
```

**Data flow:**
1. **Input** → Directory + Boolean query + file types
2. **Query parsing** → BooleanSearchParser → RPN tokens
3. **File discovery** → `os.walk` or `os.listdir` (optionally pre-filtered by index)
4. **Per-file processing** → Format-specific extractors → Normalized text → Parser.evaluate()
5. **Post-processing** → BM25 re-ranking, relevance filter
6. **Output** → save_results (HTML/TXT/CSV/Excel), optionally chunked or per-folder

---

# 3. Installation and Dependencies

## 3.1 Core Requirements

| Package | Purpose |
|---------|---------|
| Python 3.8+ | Runtime |
| tkinter | GUI (usually bundled) |
| PyPDF2 | PDF text extraction |
| PyMuPDF (fitz) | PDF blocks + text extraction |
| pytesseract | OCR (Tesseract engine required) |
| Pillow | Image handling for OCR |
| python-docx | DOCX parsing |
| beautifulsoup4 | HTML parsing |
| openpyxl | Excel read |
| pdf2image | PDF → PNG for OCR (requires poppler) |
| pdfminer.six | PDF fallback extraction |

## 3.2 Optional

| Package | Purpose |
|---------|---------|
| lxml | Faster HTML parsing |
| html5lib | Tolerant HTML5 parsing |
| chardet | Encoding detection (HTML) |

## 3.3 External Dependencies

- **Tesseract OCR**: Optional but required for image OCR and scanned PDFs. Install on PATH or set `TESSERACT_PATH` (Windows default paths are tried automatically).
- **Poppler**: Optional; required for `pdf2image` when rendering PDF pages for OCR. On Windows, add Poppler `bin` to PATH or set `POPPLER_PATH`.

See [README_STARTING.md](README_STARTING.md) for platform-specific install steps.

## 3.4 Installation Commands

Use your own Python 3.10+ (with tkinter and pip). Optionally in a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (or: source .venv/bin/activate)
pip install -r requirements.txt
python app.py --gui
```

OCR of scanned PDFs/images additionally requires the system tools **Tesseract**
(with the relevant language packs, e.g. `por`, `eng`) and **Poppler**. See
[README_STARTING.md](README_STARTING.md).

---

# 4. Module Reference

## 4.1 app.py — Main Orchestrator

**Purpose:** Coordinates search across all file types, manages indexing, caching, parallel processing, BM25 re-ranking.

**Key functions:**
- `search_in_files()` — Main entry; collects files, dispatches per format, applies BM25, saves results
- `normalize_extracted_text()` — NFKC, line-break join, whitespace collapse, accent-fold
- Highlighting is handled in `save_results.py` (`_highlight_context_html`)
- `_evaluate_text()` — Wrapper around parser.evaluate; extracts context snippets
- `scan_ocr_candidates()` — Pre-scan for PDFs/images likely needing OCR

## 4.2 main.py — GUI (Tkinter)

**Purpose:** Graphical interface; `run_interface(search_fn)` injects `search_in_files` as backend.

**Features:** Directory picker, query input, file-type checkboxes, OCR mode, min relevance, context size, output path, performance options (indexing, parallel, cache), split output, pre-scan OCR.

## 4.3 boolean_parser.py — BooleanSearchParser

**Purpose:** Parse and evaluate Boolean queries.

**API:**
- `evaluate(text)` → `(matched: bool, score: float)`
- `find_all_term_occurrences(text)` → `List[(start, end)]`
- `extract_context_at_span(text, s, e, window_size)` → `(snippet, start, end)`
- `is_simple_query()` → `bool`

**Operators:** AND, OR, NOT, NEAR/x. Synonyms: `&&`, `||`, `!`, `~`.

## 4.4 search_pdf.py — PDF Search

**Purpose:** Multi-extractor strategy (PyMuPDF blocks/text, PyPDF2, pdfminer) with quality scoring; OCR fallback; header/footer stripping; caching (PNG renders, OCR text).

## 4.5 html_search.py — HTML Search

**Purpose:** Grove-like HTML mining; encoding detection; symbol image mapping (♭, ♯, etc.); block extraction (h1–h6, p, li, table, div, ...); deduplication by content hash.

## 4.6 text_search.py — TXT and DOCX

**Purpose:** Plain text (multi-encoding) and DOCX paragraph-by-paragraph search.

## 4.7 search_csv.py, search_excel.py, search_markdown.py

**Purpose:** CSV (delimiter auto-detect), Excel (all cells), Markdown (blocks) search.

## 4.8 ocr_utils.py — OCR

**Purpose:** `extract_text_from_image()`, `resolve_tesseract_cmd()`; grayscale, autocontrast, median filter; multi-PSM autopilot.

## 4.9 indexing.py — Inverted Index

**Purpose:** `DocumentIndex` (term → doc_id → positions); `IndexManager` (persistence, change detection via file hash); AND/OR term search.

## 4.10 performance_optimizer.py — Cache, Parallel, BM25

**Purpose:** `ParallelProcessor` (ThreadPoolExecutor); `calculate_bm25_score()`.

## 4.11 save_results.py — Output Writers

**Purpose:** HTML (dark-mode, highlight, file links), TXT, CSV, Excel; `save_results_per_folder()`, `save_results_chunked()`, `save_index_html()`.

---

# 5. Mathematical Algorithms and Formulas

## 5.1 Shunting-Yard Algorithm (Query Parsing)

Converts infix tokens to RPN (postfix). Precedence (highest first):

| Operator | Precedence |
|----------|------------|
| NOT | 4 |
| NEAR/x | 3 |
| AND | 2 |
| OR | 1 |

**Rules:**
- Push operands to output
- Push `(` to operator stack
- On `)`: pop operators to output until `(`
- On operator: pop operators with precedence ≥ current to output, then push current
- End: pop all remaining operators to output

---

## 5.2 RPN Evaluation

**Stack-based evaluation:**
- Operand: push `(matched, spans, is_leaf)`
- NOT: pop one; push `(¬a, None, False)`
- AND: pop two; push `(a ∧ b, merge(a.spans, b.spans), False)`
- OR: pop two; push `(a ∨ b, merge(a.spans, b.spans), False)`
- NEAR/x: pop two; push `(near_match(a.spans, b.spans, x), None, False)`

---

## 5.3 Relevance Score (Boolean Parser)

Heuristic score based on term occurrences:

$$\text{score} = \frac{\text{leaf\_occ\_count}}{\text{len(words)} + 10^{-6}}$$

Where `leaf_occ_count` is the total number of term/phrase matches, and `len(words)` is the token count of the document.

---

## 5.4 NEAR Match (Proximity)

Given spans $A = [(a_0^s, a_0^e), \ldots]$, $B = [(b_0^s, b_0^e), \ldots]$ (word indices inclusive):

$$\text{gap}(a, b) = \begin{cases}
\max(0, b_0^s - a_1^e - 1) & \text{if } a_1^e < b_0^s \\
\max(0, a_0^s - b_1^e - 1) & \text{if } b_1^e < a_0^s \\
0 & \text{otherwise (overlap)}
\end{cases}$$

Match if any pair satisfies $\text{gap} \leq x$ (distance parameter).

---

## 5.5 Wildcard Regex

- `*` → `\w*` (zero or more word characters)
- `?` → `\w` (exactly one word character)

Terms: word boundaries `\b...\b`. Phrases: flexible spaces `\s+` or `(?:\s+|[-/])`.

---

## 5.6 Text Quality Metrics (PDF Extractor Selection)

For text $s$:

$$\text{alpha\_ratio} = \frac{|\{\text{alpha chars}\}|}{n}, \quad \text{uniq\_ratio} = \frac{|\text{unique tokens}|}{|\text{tokens}|}$$

**Garbage heuristic:**
- $n < 60$ → garbage
- $\text{alpha\_ratio} < 0.15$ → garbage
- $\text{uniq\_ratio} < 0.10$ → garbage

**Selection score:**
$$\text{score} = n \cdot (0.7 \cdot \text{alpha\_ratio} + 0.3 \cdot \text{uniq\_ratio})$$

---

## 5.7 OCR Pre-Scan (PDF) — Poor Text Detection

$$\text{poor} = \begin{cases}
\text{True} & \text{if } n < 120 \\
\text{True} & \text{if } \frac{\text{alpha}}{n} < 0.15 \\
\text{False} & \text{otherwise}
\end{cases}$$

---

## 5.8 Header/Footer Detection (PDF)

For each page, consider first and last non-empty lines. With fraction $\alpha = 0.7$:

$$\text{header} = \{\text{line} : \text{count(line at top)} \geq \lfloor \alpha \cdot N_{\text{pages}} \rfloor\}$$
$$\text{footer} = \{\text{line} : \text{count(line at bottom)} \geq \lfloor \alpha \cdot N_{\text{pages}} \rfloor\}$$

Digits normalized to `#` for matching.

---

## 5.9 TF-IDF (performance_optimizer)

$$\text{tf}(t, d) = \frac{\text{count}(t \text{ in } d)}{\text{total\_terms}(d)}$$

$$\text{idf}(t) = \log\frac{N}{\text{df}(t)}$$

$$\text{TF-IDF}(t, d) = \text{tf}(t, d) \cdot \text{idf}(t)$$

Where $N$ = total documents, $\text{df}(t)$ = documents containing $t$.

---

## 5.10 BM25 (performance_optimizer)

$$\text{IDF} = \log\left(\frac{N - \text{df} + 0.5}{\text{df} + 0.5} + 1\right)$$

$$\text{score}_{\text{BM25}} = \text{IDF} \cdot \frac{\text{tf} \cdot (k_1 + 1)}{\text{tf} + k_1 \cdot \left(1 - b + b \cdot \frac{|d|}{\text{avgdl}}\right)}$$

**Parameters:** $k_1 = 1.5$, $b = 0.75$. $|d|$ = document length (words), $\text{avgdl}$ = average document length.

---

## 5.11 BM25-Informed Relevance (app.py)

Combined score after BM25 re-ranking:

$$\text{combined} = 0.6 \cdot \text{original\_score} + 0.4 \cdot \text{bm25\_norm}$$

Where $\text{bm25\_norm} = \min(1, \text{bm25\_total} / (2 \cdot |\text{terms}|))$.

---

## 5.12 Inverted Index (indexing.py)

**Structure:** $\text{term} \mapsto \{\text{doc\_id} \mapsto [\text{positions}]\}$

**AND:** Intersection of document sets per term.
**OR:** Union of document sets per term.

**Change detection:** MD5 of file content; skip reindex if hash unchanged.

---

## 5.13 Context Extraction

For span $(s, e)$ and window $w$:

$$\text{center} = \lfloor (s + e) / 2 \rfloor$$
$$\text{start} = \max(0, \text{center} - w)$$
$$\text{end} = \min(n, \text{center} + w)$$

Returns `text[start:end]`.

---

## 5.14 ETA (Progress Callback)

$$\text{elapsed} = t_{\text{now}} - t_{\text{start}}$$
$$\text{rate} = \text{processed} / \text{elapsed}$$
$$\text{remaining} = (\text{total} - \text{processed}) / \text{rate} \quad \text{if rate} > 0$$

---

## 5.15 Unicode Normalization

- **NFKC**: Compatibility decomposition + compatibility composition
- **NFD**: Canonical decomposition (for accent removal)
- **Accent-fold**: Remove combining characters (category Mn)

---

## 5.16 Hyphenated Line-Break Join

Regex: `(\w+)-\s*\n\s*(\w+)` → `\1\2`

Joins words split across lines with hyphen (e.g. "spec-\ntral" → "spectral").

---

## 5.17 Variant Hyphen/Space

Regex: `(?<=\w)[\-/](?=\w)` → ` ` (space)

Tolerates "scientific-method" ~ "scientific method", "musica/ficta" ~ "musica ficta".

---

## 5.18 HTML Encoding Detection

Order: BOM → `<meta charset=...>` → chardet → default (e.g. cp1252).

---

## 5.19 CSV Delimiter Detection

Count occurrences of `,`, `;`, `\t`, `|` in sample; choose maximum.

---

## 5.20 MD5 for Caching / Deduplication

$$\text{hash} = \text{MD5}(\text{bytes})$$

Used for: file signature (path|size|mtime), content deduplication (HTML blocks), OCR cache keys.

---

# 6. Tutorial

## 6.1 Quick Start: GUI

**Step 1 — Launch**
```bash
python app.py
# Or double-click start_gui.bat / run app.py with no args
```

**Step 2 — Configure**
- Choose directory (or multiple if supported)
- Enter Boolean query (e.g. `piano AND cello`, `"spectral centroid"`, `textur* OR uniform*`)
- Enable file types (TXT, PDF, DOCX, etc.)
- Set Min Relevance (0.0–1.0), Context Size (chars)
- Optional: OCR mode (auto/force/never), split output, max results per file

**Step 3 — Search**
- Click **START SEARCH**
- Optionally choose output file (HTML/CSV/Excel/TXT)
- Results open or save to selected path

---

## 6.2 CLI Usage

```bash
python app.py --dir "C:\Documents" --query "texture AND uniform" --types "txt,pdf,docx" --out results.html --fmt html
```

**Options:**
- `--dir` : Base directory
- `--query` : Boolean query
- `--types` : Comma list (txt, pdf, docx, html, image, md, excel, csv)
- `--minrel` : Min relevance (default 0.1)
- `--ctx` : Context window size (default 150)
- `--ocr` : auto | force | never
- `--out` : Output path
- `--fmt` : html | txt
- `--occ` : page | all (snippets per page vs per occurrence)
- `--max-occ` : Limit snippets per page when `--occ all`
- `--no-subfolders` : Only top-level folder
- `--max-ocr-pages` : Max PDF pages for OCR (default 150)
- `--gui` : Launch GUI
- `--stem` / `--no-stem` : Enable or disable Porter stemming (default: on in typical GUI use)
- `--accent-sensitive` : Do not fold accents when matching

**Copyright and acknowledgements** appear in [README.md](README.md) only (not in the GUI or exported HTML).

---

## 6.3 Query Examples

| Query | Meaning |
|-------|---------|
| `spectral` | Single term |
| `textur*` | Wildcard (texture, textural, …) |
| `colo?r` | Single-char wildcard (color, colour) |
| `"spectral density"` | Exact phrase |
| `piano AND cello` | Both terms |
| `clar* OR bass?` | Either term |
| `texture NEAR/5 uniform` | Within 5 words |
| `texture NEAR/4 (uniform OR homogeneous)` | Grouped |
| `texture AND NOT noise` | Exclude noise |

---

## 6.4 Pre-Scan OCR

Before search, click **Pre-scan OCR** to list PDFs/images likely needing OCR. Select files to skip OCR (e.g. to avoid slow scans). Counter shows "OCR skip: N".

---

## 6.5 Output Formats

- **HTML**: Dark/light mode, highlighted terms, file links, copy path
- **TXT**: Plain text with path, score, context
- **CSV**: Structured rows (File #, Filename, Match #, Score, Position, Query, Context)
- **Excel**: Same as CSV with styling

---

## 6.6 Split Output

When "Guardar em vários ficheiros" is enabled and "Máx. resultados por ficheiro" is set (e.g. 100):
- Results split into `output_1.html`, `output_2.html`, …
- Index file `output_INDEX.html` links to all parts

---

## 6.7 Performance Options

- **Use Indexing**: Pre-filters files via inverted index (for simple queries)
- **Parallel Processing**: Multi-core file processing
- **File Caching**: Avoid re-reading unchanged files (LRU eviction)

---

# 7. Bibliography

## 7.1 Boolean Logic and Query Parsing

- **Dijkstra, E. W.** (1961). Algorithm 65: Find. *Communications of the ACM*, 4(7), 355. (Shunting-yard algorithm)

- **Pratt, V. R.** (1973). Top down operator precedence. In *Proceedings of the 1st Annual ACM SIGACT-SIGPLAN Symposium on Principles of Programming Languages* (pp. 41–51). ACM. https://doi.org/10.1145/512927.512931

## 7.2 Information Retrieval and Ranking

- **Robertson, S. E., & Zaragoza, H.** (2009). The probabilistic relevance framework: BM25 and beyond. *Foundations and Trends in Information Retrieval*, 3(4), 333–389. https://doi.org/10.1561/1500000019

- **Jones, K. S.** (1972). A statistical interpretation of term specificity and its application in retrieval. *Journal of Documentation*, 28(1), 11–21. https://doi.org/10.1108/eb026526

- **Salton, G., & Buckley, C.** (1988). Term-weighting approaches in automatic text retrieval. *Information Processing & Management*, 24(5), 513–523. https://doi.org/10.1016/0306-4573(88)90021-0

## 7.3 Inverted Index

- **Zobel, J., & Moffat, A.** (2006). Inverted files for text search engines. *ACM Computing Surveys*, 38(2), 6. https://doi.org/10.1145/1132956.1132959

- **Witten, I. H., Moffat, A., & Bell, T. C.** (1999). *Managing Gigabytes: Compressing and Indexing Documents and Images* (2nd ed.). Morgan Kaufmann. https://doi.org/10.1016/B978-0-553-09610-4.X5000-7

## 7.4 PDF Extraction and OCR

- **Smith, R.** (2007). An overview of the Tesseract OCR engine. In *Ninth International Conference on Document Analysis and Recognition (ICDAR 2007)* (Vol. 2, pp. 629–633). IEEE. https://doi.org/10.1109/ICDAR.2007.4376991

- **Krämer, M.** (2016). PyMuPDF: Python bindings for MuPDF. https://pymupdf.readthedocs.io/

- **Rosebrock, A.** (2015). *Practical Python and OpenCV* (3rd ed.). PyImageSearch. (Image preprocessing for OCR)

## 7.5 HTML Parsing and Web Mining

- **Richardson, L.** (2024). *Beautiful Soup Documentation*. https://www.crummy.com/software/BeautifulSoup/bs4/doc/

- **Kohlschütter, C., Fankhauser, P., & Nejdl, W.** (2010). Boilerplate detection using shallow text features. In *Proceedings of the Third ACM International Conference on Web Search and Data Mining* (pp. 441–450). ACM. https://doi.org/10.1145/1718487.1718542

## 7.6 Unicode and Text Normalization

- **Unicode Consortium.** (2024). Unicode Standard Annex #15: Unicode Normalization Forms. https://unicode.org/reports/tr15/

- **Davis, M., & Whistler, K.** (2024). Unicode Standard Annex #44: Unicode Character Database. https://unicode.org/reports/tr44/

## 7.7 Python Libraries

- **Harris, C. R., et al.** (2020). Array programming with NumPy. *Nature*, 585(7825), 357–362. https://doi.org/10.1038/s41586-020-2649-2

- **Reitz, K.** (2024). *Requests: HTTP for Humans*. https://requests.readthedocs.io/

## 7.8 Caching and Parallelism

- **Herlihy, M. P., & Wing, J. M.** (1990). Linearizability: A correctness condition for concurrent objects. *ACM Transactions on Programming Languages and Systems*, 12(3), 463–492. https://doi.org/10.1145/78969.78972

- **Python Software Foundation.** (2024). `concurrent.futures` — Launching parallel tasks. https://docs.python.org/3/library/concurrent.futures.html

## 7.9 Cryptography (Hashing)

- **Rivest, R.** (1992). The MD5 message-digest algorithm. *RFC 1321*. https://tools.ietf.org/html/rfc1321

- **Note:** MD5 is used here for non-security purposes (cache keys, change detection). For security, use SHA-256 or stronger.

## 7.10 Document Formats

- **Adobe Systems.** (2008). PDF Reference, Sixth Edition: Adobe Portable Document Format. Adobe.

- **ECMA International.** (2016). Office Open XML File Formats. ECMA-376. https://www.ecma-international.org/publications-and-standards/standards/ecma-376/

- **IETF.** (2005). The text/csv MIME type. *RFC 4180*. https://tools.ietf.org/html/rfc4180

---

**Document version:** 1.0  
**Last updated:** March 2025  
**Project:** text-seeker v4 (text-seeker)
