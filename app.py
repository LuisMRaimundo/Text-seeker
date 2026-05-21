# app.py — orquestrador text-seeker
from __future__ import annotations

import os
import sys
import re
import unicodedata
import argparse
import time
import inspect
import threading
from typing import List, Dict, Any, Optional, Tuple, Callable, Set

from brand import CLI_PROG, APP_NAME
from boolean_parser import BooleanSearchParser
from text_search import search_in_text_file, search_in_docx_file
from search_pdf import search_in_pdf_file
from html_search import search_in_html_file
from search_markdown import search_in_markdown_file
from search_excel import search_in_excel_file
from search_csv import search_in_csv_file
from ocr_utils import extract_text_from_image, resolve_tesseract_cmd
from save_results import save_results
from indexing import IndexManager, index_prefilter_allowed, index_operator_for_tokens
from performance_optimizer import ParallelProcessor, calculate_bm25_score
from text_extract import extract_document_text, should_index_extension
from nlp_utils import stem_token, normalize_token

# --- GUI (main.py) ---
run_gui = None
_gui_import_errors: List[str] = []
try:
    from main import run_interface as run_gui
except Exception as e:
    _gui_import_errors.append(f"main import failed: {e}")

# =========================
# Normalização + highlight
# =========================
ACCENT_FOLD = True
USE_STEMMING = True
NORMALIZE_JOIN_LINEBREAKED_WORDS = True


def _safe_print(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))

def _strip_accents(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", s)
                   if unicodedata.category(ch) != "Mn")

def normalize_extracted_text(text: str) -> str:
    """Normalização única para TODO o pipeline."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    # junta palavras quebradas por newline com hífen: "spec-\ntral" -> "spectral"
    if NORMALIZE_JOIN_LINEBREAKED_WORDS:
        t = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', t)
    # normaliza quebras
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    # colapsa espaços
    t = re.sub(r"[ \t]+", " ", t)
    # remove múltiplas linhas vazias
    t = re.sub(r"\n{3,}", "\n\n", t)
    if ACCENT_FOLD:
        t = _strip_accents(t)
    return t.strip()

# =========================
# Avaliação de texto (núcleo)
# =========================
def _evaluate_text(
    text: str,
    filepath: str,
    parser: BooleanSearchParser,
    context_size: int,
    *,
    location: Optional[int] = None,
    location_type: Optional[str] = None,  # accepted from format modules; unused
    occurrence_mode: str = "page",          # "page" | "all"
    max_snippets_per_page: int = 0          # 0 = sem limite
) -> List[dict]:
    """Devolve matches (dict). Em 'all', devolve 1 snippet por ocorrência para queries simples."""
    matched, score = parser.evaluate(text)
    if not matched:
        return []

    # tenta localizar todas as ocorrências para queries simples
    spans = parser.find_all_term_occurrences(text) if parser.is_simple_query() else []
    hits_on_page = len(spans)

    def _mk(snippet: str) -> dict:
        return {
            "filepath": filepath,
            "location": location if location is not None else 1,
            "query": parser.original_query,
            "relevance_score": float(score),
            "context": snippet,
            "hits_on_page": hits_on_page,
        }

    if occurrence_mode == "all" and spans:
        out: List[dict] = []
        lim_spans = spans if max_snippets_per_page in (None, 0) else spans[:max_snippets_per_page]
        for (s, e) in lim_spans:
            snippet, _, _ = parser.extract_context_at_span(text, s, e, context_size)
            out.append(_mk(snippet))
        return out

    # modo “page”: 1 snippet “representativo”
    if spans:
        s, e = spans[0]
        snippet, _, _ = parser.extract_context_at_span(text, s, e, context_size)
    else:
        snippet, _, _ = parser.extract_context(text, window_size=context_size)

    return [_mk(snippet)]

# =========================
# Pesquisa em imagens (OCR)
# =========================
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}

def _search_in_image_file(filepath: str, parser: BooleanSearchParser, context_size: int) -> List[dict]:
    try:
        text = extract_text_from_image(
            filepath,
            lang="por+eng",
            tess_config="--oem 3 --psm 6",
            try_psm=True
        )
    except Exception as e:
        print(f"OCR image error {filepath}: {e}")
        return []
    if not text:
        return []
    norm = normalize_extracted_text(text)
    return _evaluate_text(norm, filepath, parser, context_size, location=1)


# =========================
# OCR pre-scan (quick)
# =========================
def _text_quality_is_poor(text: str) -> bool:
    if not text:
        return True
    n = len(text)
    if n < 120:
        return True
    alpha = sum(ch.isalpha() for ch in text)
    return (alpha / max(1, n)) < 0.15


def scan_ocr_candidates(directory: str, file_types: Dict[str, bool], max_pages: int = 2, *, include_subfolders: bool = True) -> List[str]:
    """
    Quick scan to identify files likely needing OCR (no OCR performed).
    Returns list of file paths.
    """
    candidates: List[str] = []
    # Images always require OCR
    if file_types.get("image"):
        if include_subfolders:
            for root, _, files in os.walk(directory):
                for name in files:
                    if os.path.splitext(name.lower())[1] in _IMAGE_EXTS:
                        candidates.append(os.path.join(root, name))
        else:
            for name in os.listdir(directory):
                if os.path.splitext(name.lower())[1] in _IMAGE_EXTS:
                    candidates.append(os.path.join(directory, name))

    if file_types.get("pdf"):
        if include_subfolders:
            for root, _, files in os.walk(directory):
                for name in files:
                    if name.lower().endswith(".pdf"):
                        path = os.path.join(root, name)
                        text = ""
                        # Try PyMuPDF first
                        try:
                            import fitz
                            doc = fitz.open(path)
                            for i in range(min(max_pages, doc.page_count)):
                                text += doc.load_page(i).get_text("text") or ""
                            doc.close()
                        except Exception:
                            # Fallback to PyPDF2
                            try:
                                from PyPDF2 import PdfReader
                                reader = PdfReader(path)
                                for i in range(min(max_pages, len(reader.pages))):
                                    text += reader.pages[i].extract_text() or ""
                            except Exception:
                                text = ""
                        if _text_quality_is_poor(text):
                            candidates.append(path)
        else:
            for name in os.listdir(directory):
                if name.lower().endswith(".pdf"):
                    path = os.path.join(directory, name)
                    text = ""
                    # Try PyMuPDF first
                    try:
                        import fitz
                        doc = fitz.open(path)
                        for i in range(min(max_pages, doc.page_count)):
                            text += doc.load_page(i).get_text("text") or ""
                        doc.close()
                    except Exception:
                        # Fallback to PyPDF2
                        try:
                            from PyPDF2 import PdfReader
                            reader = PdfReader(path)
                            for i in range(min(max_pages, len(reader.pages))):
                                text += reader.pages[i].extract_text() or ""
                        except Exception:
                            text = ""
                    if _text_quality_is_poor(text):
                        candidates.append(path)
    return candidates

# =========================
# Orquestrador principal
# =========================
def search_in_files(
    directory: Optional[str] = None,
    boolean_query: str = "",
    file_types: Optional[Dict[str, bool]] = None,
    min_relevance: float = 0.1,
    context_size: int = 150,
    ocr_mode: str = "auto",
    output_path: Optional[str] = None,
    output_format: str = "html",
    *,
    directories: Optional[List[str]] = None,  # Múltiplas pastas (prioridade sobre directory)
    output_per_folder: bool = False,          # Um ficheiro por pasta
    max_results_per_file: int = 0,           # Se >0, divide por chunks (ex.: 100 por ficheiro)
    occurrence_mode: str = "page",
    max_snippets_per_page: int = 0,
    use_indexing: bool = True,
    use_parallel: bool = True,
    use_stemming: Optional[bool] = None,
    accent_fold: Optional[bool] = None,
    progress_callback: Optional[Callable[[int, int, float], None]] = None,
    ocr_skip_paths: Optional[Set[str]] = None,
    include_subfolders: bool = True,
    max_ocr_pages: int = 150,   # Max pages to run OCR on (0 = unlimited)
) -> List[dict]:
    # Resolver lista de pastas (suporta directory único ou directories)
    roots: List[str] = []
    if directories and len(directories) > 0:
        roots = [d.strip() for d in directories if d and os.path.isdir(d.strip())]
    if not roots and directory:
        roots = [directory]
    if not roots:
        return []
    if file_types is None:
        file_types = {}

    stem_on = USE_STEMMING if use_stemming is None else use_stemming
    fold_on = ACCENT_FOLD if accent_fold is None else accent_fold

    parser = BooleanSearchParser(
        boolean_query, accent_fold=fold_on, use_stemming=stem_on
    )
    for warn in getattr(parser, "warnings", []) or []:
        _safe_print(f"[WARN] {warn}")
    results: List[dict] = []

    parallel_processor = ParallelProcessor() if use_parallel else None
    index_manager = (
        IndexManager(accent_fold=fold_on, use_stemming=stem_on)
        if use_indexing else None
    )
    cache_lock = threading.Lock()

    try:
        found = resolve_tesseract_cmd()
        if found:
            _safe_print(f"[OK] Tesseract: {found}")
        else:
            if file_types.get("image") or (file_types.get("pdf") and ocr_mode in ("auto", "force")):
                _safe_print("[WARN] Tesseract nao encontrado; OCR pode ficar indisponivel.")
    except Exception:
        pass

    # Colecionar ficheiros de TODAS as pastas, tag com root_folder
    all_files: List[Tuple[str, str, str]] = []  # (path, ext, root_folder)
    for root_dir in roots:
        if include_subfolders:
            for root, _, files in os.walk(root_dir):
                for name in files:
                    path = os.path.join(root, name)
                    lower = name.lower()
                    ext = os.path.splitext(lower)[1]
                    all_files.append((path, ext, root_dir))
        else:
            for name in os.listdir(root_dir):
                path = os.path.join(root_dir, name)
                if not os.path.isfile(path):
                    continue
                lower = name.lower()
                ext = os.path.splitext(lower)[1]
                all_files.append((path, ext, root_dir))
    
    document_text_cache: Dict[str, str] = {}

    # Build / refresh inverted index for this corpus, then prefilter when safe
    if use_indexing and index_manager:
        indexed_count = 0
        for path, ext, _root in all_files:
            if not should_index_extension(ext, file_types):
                continue
            try:
                doc_text = extract_document_text(
                    path, ext, file_types,
                    normalize=normalize_extracted_text,
                    ocr_image_fn=extract_text_from_image if file_types.get("image") else None,
                )
                if doc_text:
                    with cache_lock:
                        document_text_cache[path] = doc_text
                    if index_manager.index_file(path, doc_text):
                        indexed_count += 1
            except Exception as e:
                print(f"Index skip {path}: {e}")
        if indexed_count:
            _safe_print(f"[OK] Indexed/updated {indexed_count} file(s)")
        index_manager.save()

        if index_prefilter_allowed(parser.tokens, parser.search_terms):
            op = index_operator_for_tokens(parser.tokens)
            indexed_paths = index_manager.search(parser.search_terms, operator=op)
            if indexed_paths:
                _safe_print(f"[OK] Index prefilter ({op}): {len(indexed_paths)} candidate file(s)")
                indexed_set = set(indexed_paths)
                all_files = [(p, e, r) for p, e, r in all_files if p in indexed_set]
    
    def _report_progress(processed: int, total: int, start_time: float,
                         cb: Optional[Callable[[int, int, float], None]]):
        if not cb or total <= 0:
            return
        elapsed = max(0.001, time.time() - start_time)
        rate = processed / elapsed if processed else 0.0
        remaining = (total - processed) / rate if rate > 0 else 0.0
        cb(processed, total, remaining)

    ocr_skip_paths = set(ocr_skip_paths or [])

    # Process files (with or without parallel processing)
    if use_parallel and parallel_processor and len(all_files) > 10:
        _safe_print(f"[...] Processing {len(all_files)} files in parallel...")
        def process_file_wrapper(file_info: Tuple[str, str, str]) -> List[dict]:
            path, ext, root_folder = file_info
            return _process_single_file(
                path, ext, root_folder, parser, context_size, file_types, ocr_mode,
                occurrence_mode, max_snippets_per_page, ocr_skip_paths,
                max_ocr_pages=max_ocr_pages,
                document_text_cache=document_text_cache,
                cache_lock=cache_lock,
            )
        start_time = time.time()
        file_results = parallel_processor.process_files_parallel(
            all_files,
            process_file_wrapper,
            progress_callback=lambda p, t: _report_progress(p, t, start_time, progress_callback)
        )
        for file_result_list in file_results:
            results.extend(file_result_list)
    else:
        start_time = time.time()
        processed = 0
        for path, ext, root_folder in all_files:
            try:
                file_results = _process_single_file(
                    path, ext, root_folder, parser, context_size, file_types, ocr_mode,
                    occurrence_mode, max_snippets_per_page, ocr_skip_paths,
                    max_ocr_pages=max_ocr_pages,
                    document_text_cache=document_text_cache,
                    cache_lock=cache_lock,
                )
                results.extend(file_results)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"Search error {path}: {e}")
            finally:
                processed += 1
                _report_progress(processed, len(all_files), start_time, progress_callback)

    # Apply BM25 ranking improvement if multiple results
    if len(results) > 1:
        results = _improve_ranking_with_bm25(results, parser)

    # Filtro por relevância
    if min_relevance and min_relevance > 0:
        results = [r for r in results if float(r.get("relevance_score", 0.0)) >= float(min_relevance)]

    for r in results:
        r.pop("document_text", None)

    # Guardar resultados
    if output_path:
        if not output_format or output_format.lower() not in ("html", "txt", "csv", "xlsx"):
            ext = os.path.splitext(output_path)[1].lower()
            if ext == '.csv':
                output_format = 'csv'
            elif ext == '.xlsx':
                output_format = 'xlsx'
            elif ext == '.txt':
                output_format = 'txt'
            else:
                output_format = 'html'
        fmt = output_format.lower()

        if output_per_folder and len(roots) > 1:
            from save_results import save_results_per_folder, save_index_html
            out_dir = os.path.dirname(output_path)
            out_stem = os.path.splitext(os.path.basename(output_path))[0]
            saved = save_results_per_folder(
                output_dir=out_dir or ".",
                output_stem=out_stem,
                results=results,
                output_format=fmt,
            )
            if saved:
                save_index_html(
                    os.path.join(out_dir or ".", f"{out_stem}_INDEX.html"),
                    saved, roots
                )
        elif max_results_per_file > 0 and len(results) > max_results_per_file:
            from save_results import save_results_chunked
            save_results_chunked(
                output_path, results,
                max_per_file=max_results_per_file,
                output_format=fmt,
            )
        else:
            save_results(
                output_path, results,
                show_duplicates=False,
                output_format=fmt
            )

    return results


def _improve_ranking_with_bm25(results: List[dict], parser: BooleanSearchParser) -> List[dict]:
    """
    Re-rank using BM25 on full document text when available (corpus = matched files).
    """
    if not results or len(results) < 2:
        return results

    search_terms = parser.search_terms
    if not search_terms:
        return results

    def _term_core(t: str) -> str:
        t = (t or "").strip()
        if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
            t = t[1:-1]
        core = normalize_token(t, accent_fold=parser.accent_fold)
        if parser.use_stemming and "*" not in core and "?" not in core:
            core = stem_token(core)
        return core

    cores = [_term_core(t) for t in search_terms if _term_core(t)]

    # One representative row per file; corpus = unique document texts
    by_path: Dict[str, dict] = {}
    for r in results:
        fp = r.get("filepath") or ""
        if fp not in by_path:
            by_path[fp] = r

    corpus_paths = list(by_path.keys())
    corpus_texts = [
        by_path[p].get("document_text") or by_path[p].get("context", "") or ""
        for p in corpus_paths
    ]
    doc_lengths = [max(1, len(t.split())) for t in corpus_texts]
    avg_doc_length = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 1.0
    total_docs = len(corpus_texts)

    path_bm25: Dict[str, float] = {}
    for idx, path in enumerate(corpus_paths):
        doc_text = corpus_texts[idx]
        doc_length = doc_lengths[idx]
        bm25_total = 0.0
        for term, core in zip(search_terms, cores):
            if not core:
                continue
            df = sum(1 for ct in corpus_texts if core in ct.lower())
            bm25_total += calculate_bm25_score(
                core, doc_text, avg_doc_length, total_docs, df
            )
        path_bm25[path] = bm25_total

    max_bm25 = max(path_bm25.values()) if path_bm25 else 1.0
    if max_bm25 <= 0:
        max_bm25 = 1.0

    for r in results:
        fp = r.get("filepath") or ""
        bm25_total = path_bm25.get(fp, 0.0)
        bm25_normalized = min(1.0, bm25_total / max_bm25)
        original_score = float(r.get("relevance_score", 0.0))
        r["relevance_score"] = 0.5 * original_score + 0.5 * bm25_normalized
        r["bm25_score"] = bm25_total

    results.sort(key=lambda x: float(x.get("relevance_score", 0.0)), reverse=True)
    return results


def _process_single_file(
    path: str,
    ext: str,
    root_folder: str,
    parser: BooleanSearchParser,
    context_size: int,
    file_types: Dict[str, bool],
    ocr_mode: str,
    occurrence_mode: str,
    max_snippets_per_page: int,
    ocr_skip_paths: Set[str],
    *,
    max_ocr_pages: int = 150,
    document_text_cache: Optional[Dict[str, str]] = None,
    cache_lock: Optional[threading.Lock] = None,
) -> List[dict]:
    """Process a single file and return results (cada dict inclui root_folder)."""
    results = []
    doc_text = ""
    if document_text_cache is not None and path in document_text_cache:
        doc_text = document_text_cache[path]
    elif should_index_extension(ext, file_types):
        try:
            doc_text = extract_document_text(
                path, ext, file_types,
                normalize=normalize_extracted_text,
                ocr_image_fn=extract_text_from_image if file_types.get("image") else None,
            )
            if document_text_cache is not None:
                if cache_lock:
                    with cache_lock:
                        document_text_cache[path] = doc_text
                else:
                    document_text_cache[path] = doc_text
        except Exception:
            doc_text = ""

    try:
        # Markdown files
        if file_types.get("md") and ext == ".md":
            results.extend(
                search_in_markdown_file(
                    path, parser, context_size,
                    normalize=normalize_extracted_text,
                    evaluate_text=_evaluate_text
                )
            )
        # Excel files
        elif file_types.get("excel") and ext in {".xlsx", ".xls"}:
            results.extend(
                search_in_excel_file(
                    path, parser, context_size,
                    normalize=normalize_extracted_text,
                    evaluate_text=_evaluate_text
                )
            )
        # CSV files
        elif file_types.get("csv") and ext == ".csv":
            results.extend(
                search_in_csv_file(
                    path, parser, context_size,
                    normalize=normalize_extracted_text,
                    evaluate_text=_evaluate_text
                )
            )
        # Text files (txt, log)
        elif file_types.get("txt") and ext in {".txt", ".log"}:
            results.extend(
                search_in_text_file(
                    path, parser, context_size,
                    normalize=normalize_extracted_text,
                    evaluate_text=_evaluate_text
                )
            )
        elif file_types.get("docx") and ext == ".docx":
            results.extend(
                search_in_docx_file(
                    path, parser, context_size,
                    normalize=normalize_extracted_text,
                    evaluate_text=_evaluate_text
                )
            )
        elif file_types.get("html") and ext in {".html", ".htm"}:
            results.extend(
                search_in_html_file(
                    path, parser, context_size,
                    normalize=normalize_extracted_text,
                    evaluate_text=_evaluate_text
                )
            )
        elif file_types.get("pdf") and ext == ".pdf":
            if path in ocr_skip_paths:
                ocr_mode = "never"
            # passa o modo de ocorrência para o módulo PDF
            eval_kwargs = {
                "occurrence_mode": occurrence_mode,
                "max_snippets_per_page": max_snippets_per_page,
            }
            results.extend(
                search_in_pdf_file(
                    path, parser, context_size,
                    ocr_mode=ocr_mode,                          # "auto" | "force" | "never"
                    normalize=normalize_extracted_text,         # função única de normalização
                    evaluate_text=_evaluate_text,               # função única de avaliação
                    ocr_image_fn=extract_text_from_image,       # OCR de imagem
                    pdfminer_fn=None,                           # auto-resolve no módulo
                    pdf2image_kwargs={"dpi": 300},
                    ocr_image_kwargs={"lang": "por+eng", "tess_config": "--oem 3 --psm 6"},
                    eval_kwargs=eval_kwargs,
                    max_ocr_pages=max_ocr_pages
                )
            )
        elif file_types.get("image") and ext in _IMAGE_EXTS:
            if path in ocr_skip_paths:
                return results
            results.extend(_search_in_image_file(path, parser, context_size))

    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"Search error {path}: {e}")

    for r in results:
        r["root_folder"] = root_folder
        if doc_text:
            r["document_text"] = doc_text
    return results

# =========================
# CLI / GUI entry
# =========================
def _parse_args():
    ap = argparse.ArgumentParser(prog=CLI_PROG, description=f"{APP_NAME} — pesquisa booleana multi-formato")
    ap.add_argument("--dir", dest="directory", required=False, help="Base directory")
    ap.add_argument("--query", dest="query", required=False, help="Boolean query")
    ap.add_argument("--types", default="txt,pdf,docx,html,image", help="Comma list of types to enable")
    ap.add_argument("--minrel", type=float, default=0.1, help="Min relevance score")
    ap.add_argument("--ctx", type=int, default=150, help="Context window size (chars)")
    ap.add_argument("--ocr", choices=["auto", "force", "never"], default="auto", help="OCR mode for PDFs")
    ap.add_argument("--out", dest="output", default=None, help="Output file (.html or .txt)")
    ap.add_argument("--fmt", dest="fmt", default="html", choices=["html", "txt"], help="Output format")

    # novo: modo de ocorrência
    ap.add_argument("--occ", choices=["page", "all"], default="page",
                    help="page = 1 snippet por página; all = 1 snippet por ocorrência (queries simples)")

    # opcional: limitar nº de snippets por página em --occ all
    ap.add_argument("--max-occ", dest="max_occ", type=int, default=0,
                    help="Limite de snippets por página quando --occ all (0 = sem limite)")
    ap.add_argument("--no-subfolders", action="store_true",
                    help="Do not search in subfolders (only the selected folder)")
    ap.add_argument("--max-ocr-pages", dest="max_ocr_pages", type=int, default=150,
                    help="Max PDF pages to run OCR on (0=unlimited). Default 150 to avoid freezes.")

    ap.add_argument("--gui", action="store_true", help="Launch GUI instead of CLI")
    ap.add_argument("--stem", dest="stem", action="store_true", default=None,
                    help="Enable PT/EN stemming (default: on)")
    ap.add_argument("--no-stem", dest="stem", action="store_false",
                    help="Disable stemming")
    ap.add_argument("--accent-sensitive", action="store_true",
                    help="Do not fold accents (ação != acao)")
    return ap.parse_args()

def _launch_gui_with_fallback():
    """Tenta invocar a GUI aceitando assinaturas (0 args) ou (1 arg = backend)."""
    if run_gui is None:
        print("GUI indisponível (run_interface não encontrado).")
        if _gui_import_errors:
            print("Detalhes de import:")
            for err in _gui_import_errors:
                print(f"  - {err}")
        sys.exit(2)
    try:
        sig = inspect.signature(run_gui)
        if len(sig.parameters) == 1:
            return run_gui(search_in_files)  # GUI que injeta o backend
        return run_gui()                    # GUI que usa import direto
    except Exception as e:
        print(f"Falha ao iniciar GUI: {e}")
        try:
            import traceback
            log_path = os.path.join(os.path.dirname(__file__), "gui_start_error.log")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
            print(f"Detalhes gravados em: {log_path}")
        except Exception:
            pass
        sys.exit(2)

if __name__ == "__main__":
    # Se foi “duplo-clique” (sem argumentos), tente GUI
    if len(sys.argv) == 1:
        _launch_gui_with_fallback()
        sys.exit(0)

    args = _parse_args()

    if args.gui:
        _launch_gui_with_fallback()
        sys.exit(0)

    if not args.directory or not args.query:
        print("Use --dir e --query, ou então passe --gui.")
        sys.exit(2)

    # Tipos ativos
    enabled = {k: False for k in ("txt", "pdf", "docx", "html", "image", "md", "excel", "csv")}
    for t in (args.types or "").split(","):
        t = t.strip().lower()
        if t in enabled:
            enabled[t] = True

    # Mensagem útil: Tesseract no PATH (apenas uma vez)
    try:
        found = resolve_tesseract_cmd()
        if found:
            _safe_print(f"[OK] Tesseract: {found}")
    except Exception:
        pass

    res = search_in_files(
        directory=args.directory,
        boolean_query=args.query,
        file_types=enabled,
        min_relevance=args.minrel,
        context_size=args.ctx,
        ocr_mode=args.ocr,
        output_path=args.output,
        output_format=args.fmt,
        occurrence_mode=args.occ,
        max_snippets_per_page=args.max_occ,
        use_indexing=True,  # Enable by default
        use_parallel=True,
        use_stemming=args.stem,
        accent_fold=not args.accent_sensitive,
        include_subfolders=not args.no_subfolders,
        max_ocr_pages=args.max_ocr_pages,
    )
    _safe_print(f"[OK] {len(res)} matches")
