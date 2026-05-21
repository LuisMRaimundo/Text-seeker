# boolean_parser.py — BooleanSearchParser (corrigido)
from __future__ import annotations

import math
import re
import unicodedata
from typing import List, Tuple, Optional, Pattern

from nlp_utils import strip_accents, tokenize_unicode, stem_token, normalize_token

__all__ = ["BooleanSearchParser"]

def _strip_accents(s: str) -> str:
    return strip_accents(s)

def _tokenize_text(text: str) -> List[str]:
    return tokenize_unicode(text)

def _wildcard_word_regex(pat: str) -> Pattern:
    """
    Regex ANCORADO para uma palavra com wildcards: * -> \\w* ; ? -> \\w
    
    Melhorado para suportar:
    - * no início, meio ou fim: textur* -> textur\\w*
    - ? para um único caractere: text?re -> text\\wre
    - Múltiplos wildcards: text*re* -> text\\w*re\\w*
    """
    if not pat:
        return re.compile(r"^$", re.IGNORECASE | re.UNICODE)
    
    # Escapar caracteres especiais, mas preservar * e ?
    esc = re.escape(pat)
    # Substituir wildcards: * -> \w* (zero ou mais), ? -> \w (exatamente um)
    esc = esc.replace(r"\*", r"\w*").replace(r"\?", r"\w")
    return re.compile(r"^" + esc + r"$", re.IGNORECASE | re.UNICODE)

def _compile_phrase_regex(core: str) -> Pattern:
    """
    Frases: espaços aceitam separadores flexíveis (espaço(s), hífen, barra).
    * e ? atuam ao nível de palavra (\\w* / \\w).
    """
    esc = re.escape(core)
    esc = esc.replace(r"\ ", r"(?:\s+|[-/])")
    esc = esc.replace(r"\*", r"\w*").replace(r"\?", r"\w")
    return re.compile(esc, re.IGNORECASE | re.UNICODE)

def _compile_term_regex(term: str) -> Pattern:
    """Termo simples ou frase (com aspas). Usa wildcards. Termos simples com \\b...\\b."""
    t = (term or "").strip()
    is_phrase = (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'"))
    core = t[1:-1] if is_phrase else t
    core = core.strip()
    if is_phrase:
        return _compile_phrase_regex(core)
    esc = re.escape(core)
    esc = esc.replace(r"\*", r"\w*").replace(r"\?", r"\w")
    return re.compile(r"\b" + esc + r"\b", re.IGNORECASE | re.UNICODE)

# =============================
# Parser booleano (shunting-yard)
# =============================
_OPS = {"AND", "OR", "NOT"}  # NEAR/x tratado à parte
_PRECEDENCE = {"NOT": 4, "NEAR": 3, "AND": 2, "OR": 1}

def _is_operator(tok: str) -> bool:
    if tok in _OPS: return True
    return tok.upper().startswith("NEAR/") and tok[5:].isdigit()

def _op_prec(tok: str) -> int:
    if tok in _OPS: return _PRECEDENCE[tok]
    if tok.upper().startswith("NEAR/"): return _PRECEDENCE["NEAR"]
    return -1

def _is_unary(tok: str) -> bool:
    return tok == "NOT"

def _clean_term(tok: str) -> str:
    return (tok or "").strip()

class BooleanSearchParser:
    """
    - Operadores: AND, OR, NOT, NEAR/x (x >= 0)
    - Sinónimos: &&, ||, !, ~
    - Parênteses e AND implícito (inclui inserção antes de NOT)
    - Frases com aspas; wildcards * e ? por palavra
    - Avaliação por tokens, NEAR com base em posições de palavra
    - Accent-fold opcional (default: True)
    API pública:
      * is_simple_query() -> bool
      * evaluate(text) -> (matched: bool, score: float)
      * find_all_term_occurrences(text) -> List[(start,end)]
      * extract_context(text, window_size) -> (snippet, start, end)
      * extract_context_at_span(text, s, e, window_size) -> (snippet, start, end)
    """
    def __init__(self, query: str, *, accent_fold: bool = True, use_stemming: bool = True):
        self.accent_fold = accent_fold
        self.use_stemming = use_stemming
        self.original_query = (query or "").strip()
        qn = unicodedata.normalize("NFKC", self.original_query)
        self.query = _strip_accents(qn) if accent_fold else qn
        self.tokens = self._insert_implicit_and(self._tokenize(self.query))
        self.rpn = self._to_rpn(self.tokens)
        self.search_terms = self._extract_terms(self.tokens)
        self.warnings = self._build_warnings()

    def _build_warnings(self) -> List[str]:
        """Return user-facing warnings about potentially ambiguous queries."""
        warns: List[str] = []
        has_near = any(t.upper().startswith("NEAR/") for t in self.tokens)
        has_or = "OR" in self.tokens
        has_parens = "(" in self.tokens or ")" in self.tokens
        if has_near and has_or and not has_parens:
            warns.append(
                "Query uses NEAR and OR without parentheses. "
                "Example: A NEAR/4 B OR C matches any C. "
                "If you want A near (B or C), use parentheses."
            )
        return warns

    # ---------- Helpers de spans ----------
    def _merge_spans(self, spans_a, spans_b):
        if not spans_a and not spans_b:
            return []
        spans = sorted((spans_a or []) + (spans_b or []))
        merged = []
        for s in spans:
            if not merged or s[0] > merged[-1][1] + 1:
                merged.append([s[0], s[1]])
            else:
                merged[-1][1] = max(merged[-1][1], s[1])
        return [(a, b) for a, b in merged]

    # ============ API pública ============
    def is_simple_query(self) -> bool:
        if not self.tokens:
            return False
        terms = 0
        for t in self.tokens:
            if t in ("(", ")"): 
                return False
            if _is_operator(t): 
                return False
            terms += 1
            if terms > 1: 
                return False
        return terms == 1

    def evaluate(self, text: str) -> Tuple[bool, float]:
        """
        Avalia correspondência booleana e devolve score simples.
        Score heurístico: #ocorrências de termos / (#palavras + 1e-6).
        - Propaga spans por AND/OR (união), para permitir NEAR sobre expressões compostas como A NEAR/x (B OR C).
        - Para NOT, não se propagam spans (NEAR aplicado a NOT é indefinido → devolve False se usado).
        """
        if not text:
            return (False, 0.0)
        text_norm = unicodedata.normalize("NFKC", text).lower()
        if self.accent_fold:
            text_norm = _strip_accents(text_norm)
        words = _tokenize_text(text_norm)
        word_stems = (
            [stem_token(w) for w in words]
            if self.use_stemming else words
        )

        term_spans_cache = {}
        def spans_for_term(term_tok: str) -> List[Tuple[int,int]]:
            key = term_tok
            if key in term_spans_cache:
                return term_spans_cache[key]
            ok, spans = self._match_term_spans(term_tok, words, word_stems)
            term_spans_cache[key] = spans if ok else []
            return term_spans_cache[key]

        # RPN eval (booleana); para NEAR/x precisamos dos spans
        stack: List[Tuple[bool, Optional[List[Tuple[int,int]]], bool]] = []
        # tuple: (matched, spans, is_leaf) ; is_leaf True apenas para termos simples/frases

        leaf_occ_count = 0

        for tok in self.rpn:
            if not _is_operator(tok) and tok not in ("(", ")"):
                spans = spans_for_term(tok)
                matched = bool(spans)
                if matched:
                    leaf_occ_count += len(spans)
                stack.append((matched, spans, True))
                continue

            if tok == "NOT":
                if not stack:
                    stack.append((False, None, False))
                    continue
                a, asp, _ = stack.pop()
                stack.append((not a, None, False))
                continue

            if tok == "AND":
                b, bsp, _ = stack.pop() if stack else (False, None, False)
                a, asp, _ = stack.pop() if stack else (False, None, False)
                stack.append((a and b, self._merge_spans(asp, bsp), False))
                continue

            if tok == "OR":
                b, bsp, _ = stack.pop() if stack else (False, None, False)
                a, asp, _ = stack.pop() if stack else (False, None, False)
                stack.append((a or b, self._merge_spans(asp, bsp), False))
                continue

            if tok.upper().startswith("NEAR/"):
                try:
                    dist = int(tok.split("/", 1)[1])
                except Exception:
                    dist = 1
                b, bsp, _ = stack.pop() if stack else (False, [], False)
                a, asp, _ = stack.pop() if stack else (False, [], False)
                stack.append((self._near_match(asp or [], bsp or [], dist), None, False))
                continue

        matched = bool(stack and stack[-1][0])
        if not matched:
            return (False, 0.0)
        # log-scaled TF, length-normalized (bounded 0..1)
        n_words = max(1, len(words))
        tf = leaf_occ_count / n_words
        score = min(1.0, tf * math.log1p(n_words) / math.log1p(1000))
        return (matched, score)

    def find_all_term_occurrences(self, text: str) -> List[Tuple[int, int]]:
        """Para query simples, devolve spans (start,end) no texto normalizado (regex com separadores flexíveis nas frases)."""
        if not self.is_simple_query() or not self.search_terms:
            return []
        term = self.search_terms[0]
        text_norm = unicodedata.normalize("NFKC", text).lower()
        if self.accent_fold:
            text_norm = _strip_accents(text_norm)
        rx = _compile_term_regex(term)
        return [(m.start(), m.end()) for m in rx.finditer(text_norm)]

    def extract_context(self, text: str, window_size: int = 180) -> Tuple[str, int, int]:
        """Extrai snippet centrado na 1.ª ocorrência. Para queries complexas, tenta o 1.º termo disponível."""
        text_norm = unicodedata.normalize("NFKC", text).lower()
        if self.accent_fold:
            text_norm = _strip_accents(text_norm)

        spans = self.find_all_term_occurrences(text_norm)
        if spans:
            s, e = spans[0]
            return self.extract_context_at_span(text_norm, s, e, window_size)

        for term in self.search_terms:
            rx = _compile_term_regex(term)
            m = rx.search(text_norm)
            if m:
                return self.extract_context_at_span(text_norm, m.start(), m.end(), window_size)

        return self.extract_context_at_span(text_norm, 0, 0, window_size)

    def extract_context_at_span(self, text: str, s: int, e: int, window_size: int = 180) -> Tuple[str, int, int]:
        n = len(text)
        if n == 0:
            return ("", 0, 0)
        s = max(0, min(s, n - 1))
        e = max(s, min(e, n))
        center = (s + e) // 2
        a = max(0, center - window_size)
        b = min(n, center + window_size)
        return (text[a:b], a, b)

    # ============ tokenização/shunting-yard ============
    def _tokenize(self, q: str) -> List[str]:
        toks: List[str] = []
        i, n = 0, len(q)
        WS = set(" \t\r\n")
        while i < n:
            c = q[i]
            if c in "()":
                toks.append(c); i += 1; continue
            if c in WS:
                i += 1; continue
            if c in ['"', "'"]:
                quote = c; i += 1; buf = []
                while i < n and q[i] != quote:
                    buf.append(q[i]); i += 1
                if i < n and q[i] == quote: i += 1
                toks.append(f'{quote}{"".join(buf)}{quote}'); continue
            if q[i:i+5].upper() == "NEAR/":
                i += 5; j = i
                while i < n and q[i].isdigit(): i += 1
                toks.append(f'NEAR/{q[j:i]}' if j < i else 'NEAR/1'); continue
            if q[i:i+2] == "&&": toks.append("AND"); i += 2; continue
            if q[i:i+2] == "||": toks.append("OR"); i += 2; continue
            if q[i] in "!~": toks.append("NOT"); i += 1; continue

            buf = []
            while i < n and q[i] not in WS and q[i] not in "()":
                if q[i:i+5].upper() == "NEAR/": break
                if q[i:i+2] in ("&&", "||"): break
                if q[i] in "!~": break
                buf.append(q[i]); i += 1
            if buf: toks.append("".join(buf))
            else: i += 1

        norm = []
        for t in toks:
            tu = t.upper()
            if tu in ("AND", "OR", "NOT"):
                norm.append(tu)
            elif tu.startswith("NEAR/") and tu[5:].isdigit():
                norm.append(tu)
            else:
                norm.append(t)
        return norm

    def _insert_implicit_and(self, toks: List[str]) -> List[str]:
        """Insere AND entre operandos adjacentes, parênteses e também antes de NOT quando apropriado."""
        def is_term(x: str) -> bool:
            return (x not in _OPS) and (x not in ("(", ")")) and not (x.upper().startswith("NEAR/") and x[5:].isdigit())
        def is_not(x: str) -> bool:
            return x == "NOT"
        out: List[str] = []
        for i, t in enumerate(toks):
            if i > 0:
                prev = out[-1]
                if ((is_term(prev) and (is_term(t) or t == "(" or is_not(t))) or
                    (prev == ")" and (t == "(" or is_term(t) or is_not(t)))):
                    out.append("AND")
            out.append(t)
        return out

    def _to_rpn(self, toks: List[str]) -> List[str]:
        out: List[str] = []
        ops: List[str] = []
        i = 0
        n = len(toks)
        while i < n:
            t = toks[i]
            if t == "(":
                ops.append(t); i += 1; continue
            if t == ")":
                while ops and ops[-1] != "(":
                    out.append(ops.pop())
                if ops and ops[-1] == "(": ops.pop()
                i += 1; continue
            if _is_operator(t):
                while ops and _is_operator(ops[-1]) and _op_prec(ops[-1]) >= _op_prec(t):
                    if t == "NOT" and _op_prec(ops[-1]) == _op_prec(t):
                        break
                    out.append(ops.pop())
                ops.append(t); i += 1; continue
            out.append(t); i += 1
        while ops:
            out.append(ops.pop())
        return out

    def _extract_terms(self, toks: List[str]) -> List[str]:
        out: List[str] = []
        for t in toks:
            if t in ("(", ")"): continue
            if _is_operator(t): continue
            out.append(_clean_term(t))
        return out

    # ============ avaliação de termos / NEAR ============
    def _word_matches(self, w: str, core: str, word_stems: Optional[List[str]], idx: int) -> bool:
        if w == core:
            return True
        if self.use_stemming and word_stems:
            return word_stems[idx] == stem_token(core)
        return False

    def _match_term_spans(
        self,
        term_tok: str,
        words: List[str],
        word_stems: Optional[List[str]] = None,
    ) -> Tuple[bool, List[Tuple[int,int]]]:
        """
        Devolve (ok, spans_em_indices_de_palavra_inclusivos).
        Suporta frases com wildcards ao nível de palavra.
        
        Melhorado para NEAR/x com wildcards:
        - textur* NEAR/4 uniform* funciona corretamente
        - Cada termo com wildcard é expandido para todas as palavras correspondentes
        - Spans são calculados para todas as correspondências
        """
        t = (term_tok or "").strip()
        if not t:
            return (False, [])
        
        is_phrase = (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'"))
        core = t[1:-1] if is_phrase else t
        core = unicodedata.normalize("NFKC", core).lower()
        core = core.strip()

        if is_phrase:
            # Frase: dividir em palavras, cada uma pode ter wildcards
            parts = [p for p in core.split() if p]
            if not parts:
                return (False, [])
            
            # Criar regex para cada parte (com wildcards se necessário)
            regs: List[Optional[Pattern]] = [
                _wildcard_word_regex(p) if ("*" in p or "?" in p) else None
                for p in parts
            ]
            
            spans: List[Tuple[int,int]] = []
            L = len(parts)
            
            # Procurar sequência de palavras que correspondem à frase
            for i in range(0, max(0, len(words) - L + 1)):
                ok = True
                for j in range(L):
                    w = words[i + j]
                    r = regs[j]
                    if r is None:
                        if not self._word_matches(w, parts[j], word_stems, i + j):
                            ok = False
                            break
                    else:
                        # Match com wildcard
                        if not r.fullmatch(w): 
                            ok = False
                            break
                
                if ok:
                    # Span: do primeiro ao último índice da frase
                    spans.append((i, i + L - 1))
            
            return (bool(spans), spans)

        # Termo simples (pode ter wildcards)
        spans: List[Tuple[int,int]] = []
        
        if "*" in core or "?" in core:
            # Termo com wildcard: usar regex
            rx = _wildcard_word_regex(core)
            for i, w in enumerate(words):
                if rx.fullmatch(w):
                    spans.append((i, i))
        else:
            for i, w in enumerate(words):
                if self._word_matches(w, core, word_stems, i):
                    spans.append((i, i))

        return (bool(spans), spans)

    def _near_match(self, a_spans: List[Tuple[int,int]], b_spans: List[Tuple[int,int]], dist: int) -> bool:
        """Retorna True se houver pares com gap <= dist (0 significa tocar/overlap)."""
        if not a_spans or not b_spans:
            return False
        a_spans = sorted(a_spans)
        b_spans = sorted(b_spans)
        i = j = 0
        while i < len(a_spans) and j < len(b_spans):
            a0, a1 = a_spans[i]
            b0, b1 = b_spans[j]
            if a1 < b0:
                gap = max(0, b0 - a1 - 1)
            elif b1 < a0:
                gap = max(0, a0 - b1 - 1)
            else:
                gap = 0
            if gap <= dist:
                return True
            if a1 < b1:
                i += 1
            else:
                j += 1
        return False
