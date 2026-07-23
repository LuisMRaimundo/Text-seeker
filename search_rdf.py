# search_rdf.py — Turtle / N-Triples / RDF/XML / OWL text search
from __future__ import annotations

import re
from typing import Any, Callable, List, Optional
from xml.etree import ElementTree as ET

Normalizer = Callable[[str], str]
Evaluator = Callable[..., List[dict]]

__all__ = ["search_in_rdf_file", "extract_rdf_text", "RDF_EXTS"]

RDF_EXTS = {".ttl", ".nt", ".n3", ".rdf", ".owl", ".trig", ".nq"}


def _noop_normalize(s: str) -> str:
    return s


def _read_text(filepath: str) -> str:
    for enc in ("utf-8", "utf-8-sig", "utf-16", "latin-1", "cp1252"):
        try:
            with open(filepath, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception:
            return ""
    return ""


def _strip_turtle_noise(text: str) -> str:
    """Keep literals and IRIs readable; drop prefix boilerplate where easy."""
    if not text:
        return ""
    # Remove block comments
    text = re.sub(r"(?s)/\*.*?\*/", " ", text)
    # Remove line comments (# ...) but keep # inside URLs roughly
    lines = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        lines.append(line)
    text = "\n".join(lines)
    # Expand quoted literals prominence
    return text


def _extract_xml_text(filepath: str) -> str:
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except Exception:
        return _read_text(filepath)
    chunks: List[str] = []
    for el in root.iter():
        if el.text and el.text.strip():
            chunks.append(el.text.strip())
        if el.tail and el.tail.strip():
            chunks.append(el.tail.strip())
        for attr in el.attrib.values():
            if isinstance(attr, str) and attr.strip() and not attr.startswith("http"):
                chunks.append(attr.strip())
    return "\n".join(chunks)


def extract_rdf_text(filepath: str) -> str:
    ext = ("." + filepath.rsplit(".", 1)[-1].lower()) if "." in filepath else ""
    if ext in {".rdf", ".owl"}:
        return _extract_xml_text(filepath)
    return _strip_turtle_noise(_read_text(filepath))


def search_in_rdf_file(
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
        raw = extract_rdf_text(filepath)
        if not raw:
            return []
        text = normalize(raw)
        return evaluate_text(text, filepath, parser, context_size, location=1)
    except Exception as e:
        print(f"RDF/TTL search error {filepath}: {e}")
        return []
