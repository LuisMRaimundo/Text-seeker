# text_search.py — plain text and DOCX search
from __future__ import annotations
from typing import Callable, List, Any, Optional

Normalizer = Callable[[str], str]
Evaluator = Callable[..., List[dict]]

__all__ = ["search_in_text_file", "search_in_docx_file"]

def _noop_normalize(s: str) -> str:
    return s

def search_in_text_file(
    filepath: str,
    parser: Any,
    context_size: int,
    normalize: Optional[Normalizer] = None,
    evaluate_text: Optional[Evaluator] = None,
) -> List[dict]:
    """
    Lê ficheiros de texto e aplica a avaliação.
    - normalize: função para normalizar texto (ex.: normalize_extracted_text)
    - evaluate_text: função avaliadora (ex.: _evaluate_text)
      assinatura esperada: evaluate_text(text, filepath, parser, context_size, **kwargs) -> list
    """
    if evaluate_text is None:
        raise ValueError("evaluate_text callable é obrigatório.")
    normalize = normalize or _noop_normalize

    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            with open(filepath, "r", encoding=enc) as f:
                raw = f.read()
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            return []
        try:
            text = normalize(raw)
            return evaluate_text(
                text, filepath, parser, context_size,
                location_type="line"
            )
        except Exception as e:
            print(f"Evaluate error {filepath}: {e}")
            return []
    return []

def search_in_docx_file(
    filepath: str,
    parser: Any,
    context_size: int,
    normalize: Optional[Normalizer] = None,
    evaluate_text: Optional[Evaluator] = None,
) -> List[dict]:
    """
    Lê .docx por parágrafos e aplica a avaliação.
    - Mantém a semântica original: passa apenas `location=i` (location_type omitido).
    """
    if evaluate_text is None:
        raise ValueError("evaluate_text callable é obrigatório.")
    normalize = normalize or _noop_normalize

    try:
        from docx import Document
    except Exception:
        print("DOCX Error: dependência 'python-docx' em falta.")
        return []

    try:
        doc = Document(filepath)
        results: List[dict] = []
        for i, para in enumerate(doc.paragraphs, 1):
            text = normalize(para.text or "")
            if text:
                results.extend(
                    evaluate_text(text, filepath, parser, context_size, location=i)
                )
        return results
    except Exception as e:
        print(f"DOCX Error {filepath}: {e}")
        return []

