# search_pdf.py — robust PDF search (multi-extractor + OCR/OSD + header/footer strip + caching)
from __future__ import annotations
from typing import Callable, List, Optional, Any, Dict, Tuple
import os, re, unicodedata, hashlib, inspect, logging, warnings
from pathlib import Path

from process_utils import (
    configure_hidden_subprocess_windows,
    limit_external_processes,
    resolve_poppler_path,
)

configure_hidden_subprocess_windows()
_POPPLER_PATH = resolve_poppler_path()

# Suppress PyPDF2 warnings for malformed PDFs (e.g. "Multiple definitions in dictionary")
warnings.filterwarnings("ignore", message=".*Multiple definitions.*", category=UserWarning)

# ---- callables injected by orchestrator (app.py) ----
Normalizer   = Callable[[str], str]
Evaluator    = Callable[..., List[dict]]
OCRImageFn   = Callable[..., str]
PDFMinerFn   = Callable[..., str]
MiningHookFn = Callable[[str, List[str]], None]

__all__ = ["search_in_pdf_file"]

# =============================================================================
# logging
# =============================================================================
_log = logging.getLogger("text_seeker.search_pdf")
if not _log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    _log.addHandler(h)
    _log.setLevel(logging.INFO)

# =============================================================================
# helpers: text cleanup / quality
# =============================================================================
_LIG_MAP = str.maketrans({
    "\u00AD": "",   # soft hyphen
    "\u00A0": " ",  # NBSP
    "ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl",
    "—": "-", "–": "-", "‒": "-", "−": "-",
    "\u200B": "", "\u200C": "", "\u200D": "", "\u200E": "", "\u200F": "", "\u2060": "",
})

def _clean_pdf_text(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(_LIG_MAP)
    # de-hyphenation across newlines (conservative)
    s = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def _variant_hyphen_space(s: str) -> str:
    # tolerate “scientific-method” ~ “scientific method”
    return re.sub(r"(?<=\w)[\-/](?=\w)", " ", s) if s else s

# quality metrics (used to pick best extractor)
from typing import cast

def _text_quality_metrics(s: str) -> Tuple[int, float, float]:
    if not s:
        return (0, 0.0, 0.0)
    n = len(s)
    alpha = sum(ch.isalpha() for ch in s)
    toks = re.findall(r"\w+", s, flags=re.UNICODE)
    uniq = len(set(toks))
    return (n, (alpha / n) if n else 0.0, (uniq / max(1, len(toks))) if toks else 0.0)

def _is_garbage(s: str) -> bool:
    if not s:
        return True
    n, ar, ur = _text_quality_metrics(s)
    if n < 60:
        return True
    if ar < 0.15:
        return True
    if ur < 0.10:
        return True
    return False

def _score_for_pick(s: str) -> float:
    n, ar, ur = _text_quality_metrics(s)
    return n * (0.7 * ar + 0.3 * ur)

# =============================================================================
# cache (PNG renders and OCR texts)
# =============================================================================
try:
    from PIL import Image
except Exception:
    Image = Any  # type: ignore


def _cache_dir() -> Path:
    from brand import default_cache_dir, legacy_cache_dirs
    p = default_cache_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p

def _md5_hex(b: bytes) -> str:
    try:
        return hashlib.md5(b, usedforsecurity=False).hexdigest()
    except TypeError:  # Python <3.9
        return hashlib.md5(b).hexdigest()

def _file_sig(path: str) -> str:
    try:
        st = os.stat(path)
        base = f"{Path(path).resolve()}|{st.st_size}|{int(st.st_mtime)}"
    except Exception:
        base = f"{Path(path).resolve()}|0|0"
    return _md5_hex(base.encode("utf-8"))

def _cache_path(sig: str, page: int, kind: str, ext: str) -> Path:
    return _cache_dir() / f"{sig}.p{page:05d}.{kind}.{ext}"

def _cache_get_png(sig: str, page: int) -> Optional["Image.Image"]:
    p = _cache_path(sig, page, "png", "png")
    if not p.exists():
        return None
    try:
        return Image.open(str(p))  # type: ignore[arg-type]
    except Exception:
        return None

def _cache_set_png(sig: str, page: int, im: "Image.Image") -> None:
    try:
        p = _cache_path(sig, page, "png", "png")
        im.save(str(p), format="PNG")
    except Exception:
        pass

def _cache_get_text(sig: str, page: int, kind: str) -> Optional[str]:
    p = _cache_path(sig, page, kind, "txt")
    if p.exists():
        try:
            return p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None
    return None

def _cache_set_text(sig: str, page: int, kind: str, text: str) -> None:
    try:
        _cache_path(sig, page, kind, "txt").write_text(text or "", encoding="utf-8")
    except Exception:
        pass

# =============================================================================
# extraction backends
# =============================================================================

def _extract_pypdf2(reader, i: int) -> str:
    try:
        return reader.pages[i].extract_text() or ""
    except Exception:
        return ""


def _extract_pymupdf_page(doc, i: int, mode: str = "text") -> str:
    try:
        page = doc.load_page(i)
        if mode == "blocks":
            blocks = page.get_text("blocks")  # (x0,y0,x1,y1,text, block_no, ...)
            if not blocks:
                return ""
            # ordering: grid columns then Y
            blocks.sort(key=lambda b: (int(b[0] // 50), b[1]))
            return "\n\n".join(
                b[4] for b in blocks if isinstance(b[4], str) and b[4].strip()
            )
        return page.get_text("text") or ""
    except Exception:
        return ""


def _resolve_pdfminer_fn(pdfminer_fn: Optional[PDFMinerFn]) -> Optional[PDFMinerFn]:
    if pdfminer_fn is not None:
        return pdfminer_fn
    try:
        from pdfminer.high_level import extract_text as _extract_text
        return _extract_text
    except Exception:
        return None


def _extract_pdfminer_page(pdfminer_ex: Optional[PDFMinerFn], filepath: str, i: int) -> str:
    if pdfminer_ex is None:
        return ""
    try:
        sig = inspect.signature(pdfminer_ex)
        if "page_numbers" in sig.parameters:
            try:
                from pdfminer.layout import LAParams
                laparams = LAParams(char_margin=2.0, word_margin=0.1, line_margin=0.2, boxes_flow=0.5)
                return pdfminer_ex(filepath, page_numbers=[i], laparams=laparams) or ""
            except Exception:
                return pdfminer_ex(filepath, page_numbers=[i]) or ""
        # fallback: whole doc
        txt = pdfminer_ex(filepath) or ""
        parts = txt.split("\f")
        return parts[i] if i < len(parts) else txt
    except Exception:
        return ""

# =============================================================================
# header/footer detection (fuzzy)
# =============================================================================

def _normalize_digits(s: str) -> str:
    return re.sub(r"\d+", "#", (s or "").strip())


def _compute_header_footer_sets(page_texts: List[str], frac: float = 0.7) -> Tuple[set, set]:
    from collections import Counter
    top, bot = Counter(), Counter()
    for txt in page_texts:
        lines = [ln.strip() for ln in (txt or "").splitlines() if ln.strip()]
        if not lines:
            continue
        top[lines[0]] += 1
        bot[lines[-1]] += 1
        top[_normalize_digits(lines[0])] += 1
        bot[_normalize_digits(lines[-1])] += 1
    th = max(1, int(frac * max(1, len(page_texts))))
    header = {ln for ln, c in top.items() if c >= th}
    footer = {ln for ln, c in bot.items() if c >= th}
    # common patterns
    header.update({"page #", "#", "p #"})
    footer.update({"page #", "#", "p #"})
    return header, footer


def _strip_header_footer(text: str, header_set: set, footer_set: set) -> str:
    lines = (text or "").splitlines()
    if not lines:
        return text or ""
    def is_hdr(ln: str) -> bool:
        t = (ln or "").strip()
        return (
            (t in header_set)
            or (_normalize_digits(t) in header_set)
            or (re.fullmatch(r"(?:page\s+)?\d{1,4}(?:\s+of\s+\d{1,4})?", t, flags=re.I) is not None)
        )
    def is_ftr(ln: str) -> bool:
        t = (ln or "").strip()
        return (
            (t in footer_set)
            or (_normalize_digits(t) in footer_set)
            or (re.fullmatch(r"(?:page\s+)?\d{1,4}(?:\s+of\s+\d{1,4})?", t, flags=re.I) is not None)
        )
    if lines and is_hdr(lines[0]):
        lines = lines[1:]
    if lines and is_ftr(lines[-1]):
        lines = lines[:-1]
    return "\n".join(lines)

# =============================================================================
# OCR helpers (OSD + pdf2image render)
# =============================================================================

def _osd_rotate_pil(im: "Image.Image") -> "Image.Image":
    try:
        import pytesseract
        with limit_external_processes():
            try:
                osd = pytesseract.image_to_osd(
                    im, output_type=pytesseract.Output.DICT, timeout=30
                )
            except TypeError:
                osd = pytesseract.image_to_osd(im, output_type=pytesseract.Output.DICT)
        rot = int(osd.get("rotate", 0))
        if rot:
            return im.rotate(-rot, expand=True)
    except Exception:
        pass
    return im


def _render_page_png(filepath: str, page_num: int, dpi: int, sig: str) -> Optional["Image.Image"]:
    im = _cache_get_png(sig, page_num)
    if im is not None:
        return im
    try:
        from pdf2image import convert_from_path
        kwargs = dict(first_page=page_num, last_page=page_num, dpi=dpi)
        if _POPPLER_PATH:
            kwargs["poppler_path"] = _POPPLER_PATH
        with limit_external_processes():
            pages = convert_from_path(filepath, **kwargs)
        if pages:
            im = pages[0]
            _cache_set_png(sig, page_num, im)
            return im
    except Exception as e:
        _log.warning(f"pdf2image render failed on page {page_num}: {e}")
    return None

# =============================================================================
# MAIN
# =============================================================================

def search_in_pdf_file( 
    filepath: str,
    parser: Any,
    context_size: int,
    ocr_mode: str = "auto",
    *,
    normalize: Optional[Normalizer] = None,
    evaluate_text: Optional[Evaluator] = None,
    ocr_image_fn: Optional[OCRImageFn] = None,
    pdfminer_fn: Optional[PDFMinerFn] = None,
    pdf2image_kwargs: Optional[Dict[str, Any]] = None,
    ocr_image_kwargs: Optional[Dict[str, Any]] = None,
    mining_hook: Optional[MiningHookFn] = None,
    enable_cache: bool = True,
    eval_kwargs: Optional[Dict[str, Any]] = None,   # ← NOVO: kwargs para o evaluate_text (e.g., occurrence_mode)
    max_ocr_pages: int = 150,   # Limit OCR to first N pages; 0 = unlimited
    use_osd: bool = False,     # OSD rotation is slow (extra Tesseract call per page)
    page_callback: Optional[Callable[[str, int, int, str], None]] = None,
    should_abort: Optional[Callable[[], bool]] = None,
) -> List[dict]:
    """
    Two-phase strategy per page:
      1) Collect candidates from PyMuPDF (blocks + text), PyPDF2, pdfminer. Pick the best by quality.
         If ocr_mode=='force' or best looks like garbage, render + OCR; cache renders/OCR.
      2) Compute header/footer sets across pages, strip them. For each page evaluate both the cleaned text
         and the hyphen→space variant, keeping whichever yields higher (#hits, score). Avoid duplicates per page.

    If should_abort() returns True mid-file, stop OCR/extract early and still evaluate
    whatever pages were already collected (partial results).
    """
    if evaluate_text is None:
        raise ValueError("evaluate_text callable is required.")
    normalize = normalize or (lambda s: s)
    eval_kwargs = dict(eval_kwargs or {})  # garante dict

    pdf2image_kwargs = dict(pdf2image_kwargs or {})
    dpi = int(pdf2image_kwargs.get("dpi", 200))

    ocr_image_kwargs = dict(ocr_image_kwargs or {})
    # Multi-PSM autopilot is ~4x slower; batch PDF search uses a single PSM unless overridden.
    ocr_image_kwargs.setdefault("try_psm", False)

    def _aborted() -> bool:
        if should_abort is None:
            return False
        try:
            return bool(should_abort())
        except Exception:
            return False

    def _page_status(page_num: int, total: int, note: str) -> None:
        if page_callback is None:
            return
        try:
            page_callback(filepath, page_num, total, note)
        except Exception:
            pass

    # ---------- open PDF backends lazily ----------
    reader = None
    try:
        from PyPDF2 import PdfReader
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)  # Malformed PDF warnings
                reader = PdfReader(filepath)
        except Exception:
            reader = None
    except Exception:
        reader = None

    fitz_doc = None
    try:
        import fitz  # PyMuPDF
        try:
            fitz_doc = fitz.open(filepath)
        except Exception:
            fitz_doc = None
    except Exception:
        fitz_doc = None

    pm_extract = _resolve_pdfminer_fn(pdfminer_fn)

    # ---------- enumerate pages ----------
    try:
        if fitz_doc is not None:
            num_pages = fitz_doc.page_count
        elif reader is not None:
            num_pages = len(reader.pages)
        else:
            if pm_extract is not None:
                whole = pm_extract(filepath) or ""
                num_pages = max(1, whole.count("\f"))
            else:
                num_pages = 0
    except Exception:
        num_pages = 0

    if num_pages <= 0:
        _log.error(f"PDF Error opening {os.path.basename(filepath)}")
        return []

    _log.info(f"Processing PDF: {os.path.basename(filepath)} ({num_pages} pages) | Mode: {ocr_mode}")

    sig = _file_sig(filepath)
    log_every = 25 if num_pages >= 50 else 0  # Progress log every N pages for large PDFs

    # ---------- phase 1: get best raw text per page (optionally OCR) ----------
    raw_texts: List[str] = []
    origins:   List[str] = []
    aborted_early = False

    for i in range(num_pages):
        if _aborted():
            aborted_early = True
            _log.warning(
                f"  -> Stopping early after {len(raw_texts)}/{num_pages} pages "
                f"({os.path.basename(filepath)}); evaluating partial text"
            )
            break
        page_num = i + 1
        cands: List[Tuple[str, str]] = []

        # PyMuPDF (frequentemente melhor)
        if fitz_doc is not None:
            t_blocks = _extract_pymupdf_page(fitz_doc, i, mode="blocks")
            if t_blocks:
                cands.append((t_blocks, "pymupdf.blocks"))
            t_plain = _extract_pymupdf_page(fitz_doc, i, mode="text")
            if t_plain:
                cands.append((t_plain, "pymupdf.text"))

        # PyPDF2
        if reader is not None:
            t_pypdf2 = _extract_pypdf2(reader, i)
            if t_pypdf2:
                cands.append((t_pypdf2, "pypdf2"))

        # pdfminer (por página) — só se ainda não temos texto útil
        if cands:
            scored_pre = [_score_for_pick(_clean_pdf_text(t)) for (t, _) in cands]
            has_good = any(score > 200 and not _is_garbage(_clean_pdf_text(t)) for (t, _), score in zip(cands, scored_pre))
        else:
            has_good = False
        if not has_good:
            t_pm = _extract_pdfminer_page(pm_extract, filepath, i)
            if t_pm:
                cands.append((t_pm, "pdfminer"))

        # escolher melhor candidato textual
        if cands:
            scored = [(_score_for_pick(_clean_pdf_text(t)), _clean_pdf_text(t), src) for (t, src) in cands]
            scored.sort(key=lambda x: x[0], reverse=True)
            best_text, best_src = scored[0][1], scored[0][2]
        else:
            best_text, best_src = "", "none"

        need_ocr = (ocr_mode == "force") or (
            ocr_mode != "never" and ((best_src == "none") or _is_garbage(best_text))
        )
        # Limit OCR pages to prevent freeze on 400+ page scanned PDFs (0 = unlimited)
        if max_ocr_pages > 0 and need_ocr and page_num > max_ocr_pages:
            need_ocr = False
            if page_num == max_ocr_pages + 1:
                _log.info(f"  -> OCR limited to first {max_ocr_pages} pages (remaining use extracted text)")

        if need_ocr:
            ocr_cap = max_ocr_pages if max_ocr_pages > 0 else num_pages
            _page_status(page_num, ocr_cap, "ocr")
            if page_num == 1 or page_num % 5 == 0:
                _log.info(
                    f"  -> OCR page {page_num}/{min(num_pages, ocr_cap)} "
                    f"({os.path.basename(filepath)})"
                )
            im = _render_page_png(filepath, page_num, dpi=dpi, sig=sig)
            if im is not None:
                if enable_cache:
                    cached = _cache_get_text(sig, page_num, "ocr")
                else:
                    cached = None
                if cached:
                    ocr_text = cached
                else:
                    im_rot = _osd_rotate_pil(im) if use_osd else im
                    try:
                        if ocr_image_fn is not None:
                            ocr_text = ocr_image_fn(im_rot, **ocr_image_kwargs)
                        else:
                            try:
                                import pytesseract
                                with limit_external_processes():
                                    _kw = dict(
                                        lang=ocr_image_kwargs.get("lang", "por+eng"),
                                        config=ocr_image_kwargs.get(
                                            "tess_config", "--oem 3 --psm 6"
                                        ),
                                        timeout=int(ocr_image_kwargs.get("timeout", 45) or 45),
                                    )
                                    try:
                                        ocr_text = pytesseract.image_to_string(im_rot, **_kw)
                                    except TypeError:
                                        _kw.pop("timeout", None)
                                        ocr_text = pytesseract.image_to_string(im_rot, **_kw)
                            except Exception:
                                ocr_text = ""
                    except Exception:
                        ocr_text = ""
                    if enable_cache and ocr_text:
                        _cache_set_text(sig, page_num, "ocr", ocr_text)
                ocr_text = _clean_pdf_text(ocr_text)
                if not _is_garbage(ocr_text) and _score_for_pick(ocr_text) >= _score_for_pick(best_text):
                    best_text, best_src = ocr_text, "ocr"

        raw_texts.append(best_text)
        origins.append(best_src)

        # Progress log for large PDFs (avoids "appears frozen" when processing 400+ pages)
        if (not need_ocr) and log_every and page_num % log_every == 0:
            _page_status(page_num, num_pages, "extract")
            _log.info(f"  -> Page {page_num}/{num_pages}")

    # ---------- compute header/footer sets across pages ----------
    header_set, footer_set = _compute_header_footer_sets(raw_texts)

    # ---------- phase 2: normalize, strip h/f, evaluate per page ----------
    results: List[dict] = []

    for i, raw in enumerate(raw_texts):
        page_num = i + 1
        if mining_hook is not None:
            try:
                mining_hook(filepath, [raw])
            except Exception:
                pass

        clean = _clean_pdf_text(raw)
        clean = _strip_header_footer(clean, header_set, footer_set)
        vspace = _variant_hyphen_space(clean)

        # normalização única (orquestrador)
        n1 = normalize(clean)
        n2 = normalize(vspace)

        # avaliar AMBAS as variantes e escolher pela métrica (#hits, score)
        r1 = evaluate_text(n1, filepath, parser, context_size, location=page_num, **eval_kwargs)
        r2 = evaluate_text(n2, filepath, parser, context_size, location=page_num, **eval_kwargs)

        def _metrics(lst: List[dict]) -> Tuple[int, float]:
            if not lst:
                return (0, 0.0)
            # soma hits_on_page (se presente) e max score
            try:
                hits = sum(int(x.get("hits_on_page", 0)) for x in lst if isinstance(x, dict))
            except Exception:
                hits = 0
            try:
                mx = max(float(x.get("relevance_score", 0.0)) for x in lst if isinstance(x, dict))
            except Exception:
                mx = 0.0
            return (hits, mx)

        m1 = _metrics(r1)
        m2 = _metrics(r2)
        pick = r2 if (m2 > m1) else r1

        # deduplicar contextos por página
        seen_ctx = set()
        dedup: List[dict] = []
        for r in pick:
            ctx = r.get("context", "") if isinstance(r, dict) else getattr(r, "context", "")
            key = (ctx or "").strip()
            if key in seen_ctx:
                continue
            seen_ctx.add(key)
            dedup.append(r)

        results.extend(dedup)

    return results
