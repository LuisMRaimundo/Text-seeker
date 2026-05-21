# nlp_utils.py — shared tokenization (incl. CJK), accent-fold, PT/EN stemming
from __future__ import annotations

import re
import unicodedata
from typing import List, Optional

__all__ = [
    "strip_accents",
    "tokenize_unicode",
    "stem_token",
    "normalize_token",
    "expand_index_keys",
]

_CJK_RX = re.compile(
    r"[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u30ff\uac00-\ud7af]"
)
_WORD_RX = re.compile(r"\w+", flags=re.UNICODE)

# Portuguese + English suffix stripping (lightweight, no external deps)
_PT_EN_SUFFIXES = (
    "ization", "isation", "amento", "imentos", "imento", "idades", "idade",
    "amente", "ações", "acao", "ações", "izer", "iser", "ness", "ment",
    "ings", "ing", "edly", "edly", "ous", "ive", "ally", "ful", "less",
    "ism", "ist", "ity", "ous", "ive", "ers", "er", "ed", "es", "s",
    "ar", "er", "ir", "or", "ur", "em", "am", "os", "as", "ão", "ões",
)


def strip_accents(s: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", s)
        if unicodedata.category(ch) != "Mn"
    )


def normalize_token(s: str, *, accent_fold: bool = True) -> str:
    if not s:
        return ""
    t = unicodedata.normalize("NFKC", s).lower()
    if accent_fold:
        t = strip_accents(t)
    return t


def stem_token(word: str, *, min_len: int = 4) -> str:
    """
    Conservative PT/EN stemmer for recall (running→run, análise→analis).
    Skips very short tokens and tokens with wildcards.
    """
    w = normalize_token(word)
    if not w or len(w) < min_len or "*" in w or "?" in w:
        return w
    if _CJK_RX.search(w):
        return w

    changed = True
    cur = w
    while changed and len(cur) >= min_len:
        changed = False
        for suf in _PT_EN_SUFFIXES:
            if len(cur) - len(suf) >= min_len and cur.endswith(suf):
                cur = cur[: -len(suf)]
                changed = True
                break
    if len(cur) >= 2 and cur[-1] == cur[-2]:
        cur = cur[:-1]
    return cur


def tokenize_unicode(text: str) -> List[str]:
    """
    Tokenize: \\w+ words plus isolated CJK codepoints as tokens.
    """
    if not text:
        return []
    tokens: List[str] = []
    i, n = 0, len(text)
    while i < n:
        m = _CJK_RX.match(text, i)
        if m:
            tokens.append(m.group(0))
            i = m.end()
            continue
        m2 = _WORD_RX.match(text, i)
        if m2:
            tokens.append(m2.group(0))
            i = m2.end()
            continue
        i += 1
    return tokens


def expand_index_keys(word: str, *, accent_fold: bool = True, use_stemming: bool = True) -> List[str]:
    """Surface + stem keys for inverted index postings."""
    n = normalize_token(word, accent_fold=accent_fold)
    if not n:
        return []
    keys = [n]
    if use_stemming:
        s = stem_token(n)
        if s and s not in keys:
            keys.append(s)
    return keys
