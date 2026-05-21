import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nlp_utils import tokenize_unicode, stem_token, expand_index_keys, normalize_token


class TestNlpUtils(unittest.TestCase):
    def test_cjk_tokens(self):
        toks = tokenize_unicode("中文测试 alpha")
        self.assertIn("中", toks)
        self.assertIn("alpha", toks)

    def test_stem_running(self):
        self.assertEqual(stem_token("running"), "run")

    def test_accent_normalize(self):
        self.assertEqual(normalize_token("Ação"), "acao")

    def test_expand_index_keys(self):
        keys = expand_index_keys("running", use_stemming=True)
        self.assertIn("running", keys)
        self.assertIn("run", keys)


if __name__ == "__main__":
    unittest.main()
