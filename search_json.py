# search_json.py — JSON / JSONL full-text search
from __future__ import annotations

import json
from typing import Any, Callable, List, Optional

Normalizer = Callable[[str], str]
Evaluator = Callable[..., List[dict]]

__all__ = ["search_in_json_file", "extract_json_text"]


def _noop_normalize(s: str) -> str:
    return s


def _collect_strings(obj: Any, out: List[str]) -> None:
    if obj is None:
        return
    if isinstance(obj, str):
        s = obj.strip()
        if s:
            out.append(s)
        return
    if isinstance(obj, (int, float, bool)):
        out.append(str(obj))
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.strip():
                out.append(k.strip())
            _collect_strings(v, out)
        return
    if isinstance(obj, (list, tuple)):
        for item in obj:
            _collect_strings(item, out)


def extract_json_text(filepath: str) -> str:
    """Flatten JSON/JSONL into searchable plain text."""
    lower = filepath.lower()
    parts: List[str] = []

    if lower.endswith(".jsonl"):
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                with open(filepath, "r", encoding=enc) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            _collect_strings(json.loads(line), parts)
                        except Exception:
                            parts.append(line)
                break
            except UnicodeDecodeError:
                parts.clear()
                continue
            except Exception:
                return ""
        return "\n".join(parts)

    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            with open(filepath, "r", encoding=enc) as f:
                data = json.load(f)
            _collect_strings(data, parts)
            return "\n".join(parts)
        except UnicodeDecodeError:
            parts.clear()
            continue
        except Exception:
            # Fallback: treat as text if not valid JSON
            try:
                with open(filepath, "r", encoding=enc) as f:
                    return f.read()
            except Exception:
                return ""
    return ""


def search_in_json_file(
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
        raw = extract_json_text(filepath)
        if not raw:
            return []
        text = normalize(raw)
        return evaluate_text(text, filepath, parser, context_size, location=1)
    except Exception as e:
        print(f"JSON search error {filepath}: {e}")
        return []
