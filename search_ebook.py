# search_ebook.py — EPUB / FB2 (and similar) ebook text search
from __future__ import annotations

import re
import zipfile
from typing import Any, Callable, List, Optional
from xml.etree import ElementTree as ET

Normalizer = Callable[[str], str]
Evaluator = Callable[..., List[dict]]

__all__ = ["search_in_ebook_file", "extract_ebook_text", "EBOOK_EXTS"]

EBOOK_EXTS = {".epub", ".fb2", ".fb2.zip"}


def _noop_normalize(s: str) -> str:
    return s


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()
        return soup.get_text("\n", strip=True)
    except Exception:
        text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
        text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()


def _extract_epub(filepath: str) -> str:
    parts: List[str] = []
    try:
        with zipfile.ZipFile(filepath, "r") as zf:
            names = zf.namelist()
            # Find package document via container.xml
            spine_hrefs: List[str] = []
            rootfile = None
            if "META-INF/container.xml" in names:
                try:
                    container = ET.fromstring(zf.read("META-INF/container.xml"))
                    for el in container.iter():
                        if el.tag.endswith("rootfile"):
                            rootfile = el.attrib.get("full-path")
                            break
                except Exception:
                    rootfile = None

            opf_dir = ""
            if rootfile:
                opf_dir = rootfile.rsplit("/", 1)[0] + "/" if "/" in rootfile else ""
                try:
                    opf = ET.fromstring(zf.read(rootfile))
                    id_to_href = {}
                    for el in opf.iter():
                        if el.tag.endswith("item"):
                            iid = el.attrib.get("id")
                            href = el.attrib.get("href")
                            if iid and href:
                                id_to_href[iid] = href
                    for el in opf.iter():
                        if el.tag.endswith("itemref"):
                            idref = el.attrib.get("idref")
                            if idref and idref in id_to_href:
                                spine_hrefs.append(id_to_href[idref])
                except Exception:
                    spine_hrefs = []

            candidates = spine_hrefs or [
                n for n in names
                if n.lower().endswith((".xhtml", ".html", ".htm", ".xml"))
                and "meta-inf" not in n.lower()
            ]

            seen = set()
            for href in candidates:
                path = href
                if opf_dir and not href.startswith(opf_dir) and "/" not in href:
                    path = opf_dir + href
                # normalize zip paths
                path = path.replace("\\", "/").lstrip("./")
                if path in seen or path not in zf.namelist():
                    # try join variants
                    alt = (opf_dir + href).replace("\\", "/").lstrip("./")
                    if alt in seen or alt not in zf.namelist():
                        continue
                    path = alt
                seen.add(path)
                try:
                    raw = zf.read(path)
                    for enc in ("utf-8", "utf-8-sig", "latin-1"):
                        try:
                            html = raw.decode(enc)
                            break
                        except UnicodeDecodeError:
                            html = ""
                    text = _html_to_text(html)
                    if text:
                        parts.append(text)
                except Exception:
                    continue
    except Exception as e:
        print(f"EPUB error {filepath}: {e}")
        return ""
    return "\n\n".join(parts)


def _extract_fb2(filepath: str) -> str:
    lower = filepath.lower()
    data = b""
    try:
        if lower.endswith(".fb2.zip"):
            with zipfile.ZipFile(filepath, "r") as zf:
                for name in zf.namelist():
                    if name.lower().endswith(".fb2"):
                        data = zf.read(name)
                        break
        else:
            with open(filepath, "rb") as f:
                data = f.read()
    except Exception as e:
        print(f"FB2 read error {filepath}: {e}")
        return ""

    if not data:
        return ""

    xml_text = ""
    for enc in ("utf-8", "utf-8-sig", "windows-1251", "latin-1"):
        try:
            xml_text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not xml_text:
        return ""

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(xml_text, "lxml-xml")
        chunks: List[str] = []
        for tag_name in ("book-title", "title", "p", "v", "subtitle", "text-author"):
            for el in soup.find_all(tag_name):
                t = el.get_text(" ", strip=True)
                if t:
                    chunks.append(t)
        if chunks:
            return "\n".join(chunks)
        return soup.get_text("\n", strip=True)
    except Exception:
        return _html_to_text(xml_text)


def extract_ebook_text(filepath: str) -> str:
    lower = filepath.lower()
    if lower.endswith(".epub"):
        return _extract_epub(filepath)
    if lower.endswith(".fb2") or lower.endswith(".fb2.zip"):
        return _extract_fb2(filepath)
    return ""


def search_in_ebook_file(
    filepath: str,
    parser: Any,
    context_size: int,
    normalize: Optional[Normalizer] = None,
    evaluate_text: Optional[Evaluator] = None,
) -> List[dict]:
    if evaluate_text is None:
        raise ValueError("evaluate_text callable is required.")
    normalize = normalize or _noop_normalize
    try:
        raw = extract_ebook_text(filepath)
        if not raw:
            return []
        text = normalize(raw)
        # One document-level hit location (chapter splitting would be overkill)
        return evaluate_text(text, filepath, parser, context_size, location=1)
    except Exception as e:
        print(f"Ebook search error {filepath}: {e}")
        return []
