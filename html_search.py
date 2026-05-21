# html_search.py — HTML mining robusto (Grove-like): encoding cp1252, símbolos musicais, blocos ordenados, dedup
from __future__ import annotations
from typing import Callable, List, Optional, Any, Iterable
import re, io, hashlib, unicodedata, os

Normalizer = Callable[[str], str]
Evaluator  = Callable[..., List[dict]]

__all__ = ["search_in_html_file"]

# ---------------- util: hash/dedup ----------------
def _md5_hex(b: bytes) -> str:
    try:
        import hashlib
        return hashlib.md5(b, usedforsecurity=False).hexdigest()
    except TypeError:
        return hashlib.md5(b).hexdigest()

# ---------------- util: encoding ------------------
_META_CHARSET_RE = re.compile(
    br"""<meta[^>]+(?:charset\s*=\s*["']?([^"'>\s;]+)|content\s*=\s*["'][^"']*charset=([^"'>\s;]+)[^"']*["'])""",
    re.IGNORECASE,
)

def _detect_encoding(bin_data: bytes) -> str:
    # 1) BOMs
    if bin_data.startswith(b"\xef\xbb\xbf"): return "utf-8-sig"
    if bin_data.startswith(b"\xff\xfe"):     return "utf-16le"
    if bin_data.startswith(b"\xfe\xff"):     return "utf-16be"
    # 2) <meta charset=...>
    m = _META_CHARSET_RE.search(bin_data[:4096])
    if m:
        enc = (m.group(1) or m.group(2) or b"").decode("ascii", "ignore").strip().lower()
        # normalizações comuns
        if enc in ("cp1252", "windows-1252"): return "cp1252"
        if enc in ("latin-1", "iso-8859-1"):  return "latin-1"
        return enc or "utf-8"
    # 3) chardet (se disponível)
    try:
        import chardet
        det = chardet.detect(bin_data[:16384])
        enc = (det.get("encoding") or "").lower()
        if enc:
            if enc in ("windows-1252", "cp1252"): return "cp1252"
            return enc
    except Exception:
        pass
    # 4) fallback pragmático para Grove-like
    return "cp1252"

# --------------- util: limpeza texto --------------
_LIG_MAP = str.maketrans({
    "\u00A0": " ",   # NBSP
    "\u00AD": "",    # soft hyphen
    "ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl",
    "—": "-", "–": "-", "‒": "-", "−": "-",
    # zero-widths
    "\u200B": "", "\u200C": "", "\u200D": "", "\u200E": "", "\u200F": "", "\u2060": "",
})

def _clean_text(s: str) -> str:
    if not s: return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(_LIG_MAP)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def _variant_hyphen_space(s: str) -> str:
    # tolerância a hífen/barra interpalavra: "musica-ficta" ~ "musica ficta"
    return re.sub(r"(?<=\w)[\-/](?=\w)", " ", s)

# --------------- mapeamento de símbolos -----------
# Nas páginas Grove, acidentais surgem via <img src="../Images/flat.gif">, etc. (ver exemplo S00008.htm)
_IMG_SYMBOLS = {
    "flat.gif": "♭",
    "sharp.gif": "♯",
    "natural.gif": "♮",
    "dblflat.gif": "𝄫",
    "dflat.gif": "𝄫",
    "dblsharp.gif": "𝄪",
    "dsharp.gif": "𝄪",
}

def _map_symbol_images(soup) -> None:
    for img in soup.find_all("img"):
        src = (img.get("src") or "").lower()
        key = os.path.basename(src)
        if key in _IMG_SYMBOLS:
            img.replace_with(_IMG_SYMBOLS[key])

# --------------- iteração por blocos --------------
_ALLOWED_TAGS = {"h1","h2","h3","h4","h5","h6","p","li","table","div","span","article","section","blockquote","pre","code"}

def _iter_blocks(root) -> Iterable[str]:
    """
    Extrai texto em ordem de leitura: headings (h1–h6), parágrafos, listas, tabelas, divs, etc.
    Converte <table> em linhas "célula1 | célula2 | ...".
    Melhorado para lidar com HTML5, XHTML e HTML malformado.
    """
    from bs4.element import Tag
    
    # Usar find_all com recursive=False para evitar duplicação de elementos aninhados
    # Mas também verificar descendants para elementos não diretos
    processed = set()
    
    # Primeiro, processar elementos diretos do root
    for el in root.find_all(_ALLOWED_TAGS, recursive=False):
        if id(el) in processed:
            continue
        processed.add(id(el))
        
        name = (el.name or "").lower()
        
        if name == "table":
            rows = []
            for tr in el.find_all("tr", recursive=False):
                cells = []
                for td in tr.find_all(["td","th"], recursive=False):
                    txt = td.get_text(" ", strip=True)
                    if txt: cells.append(txt)
                if cells:
                    rows.append(" | ".join(cells))
            text = "\n".join(rows).strip()
        elif name in {"pre", "code"}:
            # Preservar espaços em código
            text = el.get_text("\n", strip=True)
        else:
            text = el.get_text(" ", strip=True)

        if text:
            yield text
    
    # Depois, processar elementos aninhados que não foram capturados
    for el in root.descendants:
        if not isinstance(el, Tag) or id(el) in processed:
            continue
        
        name = (el.name or "").lower()
        if name not in _ALLOWED_TAGS:
            continue
        
        # Verificar se este elemento não está dentro de outro elemento já processado
        parent_processed = False
        for parent in el.parents:
            if id(parent) in processed and parent.name in _ALLOWED_TAGS:
                parent_processed = True
                break
        
        if parent_processed:
            continue
        
        processed.add(id(el))
        
        if name == "table":
            rows = []
            for tr in el.find_all("tr"):
                cells = []
                for td in tr.find_all(["td","th"]):
                    txt = td.get_text(" ", strip=True)
                    if txt: cells.append(txt)
                if cells:
                    rows.append(" | ".join(cells))
            text = "\n".join(rows).strip()
        elif name in {"pre", "code"}:
            text = el.get_text("\n", strip=True)
        else:
            text = el.get_text(" ", strip=True)

        if text:
            yield text

# --------------- principal ------------------------
def search_in_html_file(
    filepath: str,
    parser: Any,
    context_size: int,
    *,
    normalize: Optional[Normalizer] = None,
    evaluate_text: Optional[Evaluator] = None,
    bs4_parser: Optional[str] = None,   # "lxml" (recomendado), "html.parser", "html5lib"
) -> List[dict]:
    """
    Mineração robusta para HTML Grove-like:
      - detecção de encoding (meta/chardet) — cp1252 por defeito
      - parser tolerante ("lxml" por omissão se disponível)
      - mapeamento de <img> acidentais -> símbolos musicais
      - remoção de script/style/noscript/iframe/object e comentários
      - extração por blocos ordenados (h1–h4, p, li, table)
      - deduplicação intra-página por hash
      - avaliação bloco-a-bloco (location = índice do bloco)
    """
    if evaluate_text is None:
        raise ValueError("evaluate_text callable é obrigatório.")
    normalize = normalize or (lambda s: s)

    # --- carregar HTML com encoding correto ---
    try:
        with open(filepath, "rb") as fb:
            raw = fb.read()
        encoding = _detect_encoding(raw)
        html = raw.decode(encoding, errors="replace")
    except Exception as e:
        print(f"HTML Error {filepath}: {e}")
        return []

    # --- BeautifulSoup com parser robusto ---
    try:
        from bs4 import BeautifulSoup, Comment
    except Exception:
        print("HTML Error: dependência 'beautifulsoup4' em falta.")
        return []

    chosen = bs4_parser
    if chosen is None:
        # Tentar múltiplos parsers em ordem de preferência
        # 1. lxml (mais rápido, melhor para HTML malformado)
        # 2. html5lib (mais tolerante, melhor para HTML5)
        # 3. html.parser (fallback da stdlib)
        for parser_candidate in ["lxml", "html5lib", "html.parser"]:
            try:
                if parser_candidate == "lxml":
                    import lxml  # noqa: F401
                elif parser_candidate == "html5lib":
                    import html5lib  # noqa: F401
                chosen = parser_candidate
                break
            except ImportError:
                continue
        else:
            chosen = "html.parser"  # fallback final

    # Tentar parse com parser escolhido
    # Se falhar, tentar outros parsers como fallback
    soup = None
    parse_errors = []
    
    for parser_attempt in [chosen, "html5lib", "lxml", "html.parser"]:
        try:
            if parser_attempt == "html5lib":
                try:
                    import html5lib
                except ImportError:
                    continue
            elif parser_attempt == "lxml":
                try:
                    import lxml
                except ImportError:
                    continue
            
            soup = BeautifulSoup(html, parser_attempt)
            # Verificar se parse foi bem-sucedido (tem conteúdo)
            if soup and (soup.body or soup.find_all()):
                chosen = parser_attempt
                break
        except Exception as e:
            parse_errors.append(f"{parser_attempt}: {str(e)}")
            continue
    
    if soup is None:
        print(f"HTML Error {filepath}: Could not parse with any parser. Errors: {parse_errors}")
        return []

    # Corrigir HTMLs inválidos: se não houver <body>, usar a raiz
    root = soup.body if soup.body else soup

    # Remover ruído e comentários
    for tag in root.find_all(["script","style","noscript","iframe","object"]):
        tag.decompose()
    for c in root.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()

    # Mapear imagens de acidentais para símbolos (♭, ♯, ♮, …)
    _map_symbol_images(root)

    # Iterar blocos em ordem de leitura
    results: List[dict] = []
    seen_hashes: set[str] = set()
    for idx, block in enumerate(_iter_blocks(root), start=1):
        # limpeza + variante tolerante hífen/barra
        cleaned = _clean_text(block)
        variant = _variant_hyphen_space(cleaned)
        for cand in (cleaned, variant if variant != cleaned else None):
            if not cand:
                continue
            norm = normalize(cand)
            h = _md5_hex(norm.encode("utf-8"))
            if h in seen_hashes:
                continue
            try:
                hits = evaluate_text(norm, filepath, parser, context_size, location=idx)
            except Exception as e:
                print(f"HTML Evaluate error ({filepath}, block {idx}): {e}")
                hits = []
            if hits:
                results.extend(hits)
                seen_hashes.add(h)

    return results
