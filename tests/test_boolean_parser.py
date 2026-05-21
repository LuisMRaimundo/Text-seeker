"""Unit tests for BooleanSearchParser and index prefilter helpers."""
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from boolean_parser import BooleanSearchParser
from indexing import index_prefilter_allowed, index_operator_for_tokens


class TestBooleanSearchParser(unittest.TestCase):
    def test_simple_term_match(self):
        p = BooleanSearchParser("piano")
        ok, score = p.evaluate("The piano sonata features a grand piano.")
        self.assertTrue(ok)
        self.assertGreater(score, 0)

    def test_and_implicit(self):
        p = BooleanSearchParser("piano cello")
        self.assertTrue(p.evaluate("piano and cello duo")[0])
        self.assertFalse(p.evaluate("only piano here")[0])

    def test_or(self):
        p = BooleanSearchParser("piano OR violin")
        self.assertTrue(p.evaluate("violin concerto")[0])
        self.assertFalse(p.evaluate("cello suite")[0])

    def test_not(self):
        p = BooleanSearchParser("piano NOT noise")
        self.assertTrue(p.evaluate("piano music")[0])
        self.assertFalse(p.evaluate("piano noise floor")[0])

    def test_near(self):
        p = BooleanSearchParser("spectral NEAR/3 centroid")
        self.assertTrue(p.evaluate("the spectral analysis uses a centroid estimator")[0])
        self.assertFalse(p.evaluate("spectral density and later the centroid")[0])

    def test_wildcard_prefix(self):
        p = BooleanSearchParser("clar*")
        self.assertTrue(p.evaluate("clarinet clarion")[0])
        self.assertFalse(p.evaluate("violin")[0])

    def test_phrase_quotes(self):
        p = BooleanSearchParser('"spectral centroid"')
        self.assertTrue(p.evaluate("we study the spectral centroid of the tone")[0])

    def test_accent_fold(self):
        p = BooleanSearchParser("acao", accent_fold=True)
        self.assertTrue(p.evaluate("a ação continua")[0])

    def test_stemming_run_running(self):
        p = BooleanSearchParser("run", use_stemming=True)
        self.assertTrue(p.evaluate("the running athlete")[0])
        self.assertFalse(p.evaluate("walk only")[0])

    def test_precedence_not_before_and(self):
        p = BooleanSearchParser("NOT noise AND piano")
        # NOT noise AND piano  =>  (NOT noise) AND piano
        self.assertTrue(p.evaluate("piano music")[0])
        self.assertFalse(p.evaluate("piano with noise")[0])

    def test_is_simple_query(self):
        self.assertTrue(BooleanSearchParser("term").is_simple_query())
        self.assertFalse(BooleanSearchParser("a AND b").is_simple_query())

    def test_near_wildcard(self):
        p = BooleanSearchParser("textur* NEAR/4 uniform*")
        text = "textural uniform patterns and textural unity"
        self.assertTrue(p.evaluate(text)[0])


class TestIndexPrefilter(unittest.TestCase):
    def test_allows_simple_and(self):
        p = BooleanSearchParser("foo bar")
        self.assertTrue(index_prefilter_allowed(p.tokens, p.search_terms))

    def test_blocks_near(self):
        p = BooleanSearchParser("a NEAR/2 b")
        self.assertFalse(index_prefilter_allowed(p.tokens, p.search_terms))

    def test_blocks_wildcard(self):
        p = BooleanSearchParser("clar*")
        self.assertFalse(index_prefilter_allowed(p.tokens, p.search_terms))

    def test_operator_or(self):
        p = BooleanSearchParser("a OR b")
        self.assertEqual(index_operator_for_tokens(p.tokens), "OR")


if __name__ == "__main__":
    unittest.main()
