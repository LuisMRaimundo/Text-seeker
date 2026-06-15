"""Tests for the HTML search-term highlight styling (soft pastel palette).

These verify presentation only: markup is still produced, term text is preserved,
and the colours come from the soft pastel palette (no saturated legacy colours).
They do not touch match-finding, counts, or ranking.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import save_results  # noqa: E402

# Soft pastel palette (must match save_results._highlight_context_html).
PASTEL = {
    "#fff3b0", "#d8f3dc", "#dbeafe", "#fde2e4",
    "#f3e8ff", "#ffe5d9", "#e0f2fe", "#fef9c3",
}
# Saturated colours that must no longer appear anywhere in the output styling.
LEGACY_SATURATED = {
    "#fff59d", "#ffcc80", "#f48fb1", "#90caf9", "#a5d6a7", "#ce93d8",
    "#ffab91", "#b0bec5", "#ffe082", "#c5e1a5", "#b39ddb", "#ef9a9a",
    "#81c784", "#64b5f6", "#ffb74d",
}

_HEX = re.compile(r"background-color:\s*(#[0-9a-fA-F]{6})")


class TestHtmlHighlight(unittest.TestCase):
    def test_highlight_markup_present_and_term_preserved(self):
        out = save_results._highlight_context_html("the quick brown fox", ["quick"])
        self.assertIn('class="highlight"', out)
        # The matched term text is preserved verbatim.
        self.assertIn("quick", out)
        self.assertIn("brown fox", out)  # non-matched text intact

    def test_highlight_colours_are_soft_pastels(self):
        out = save_results._highlight_context_html("alpha beta gamma", ["beta"])
        colours = set(m.lower() for m in _HEX.findall(out))
        self.assertTrue(colours, "expected at least one highlight background colour")
        self.assertTrue(colours <= PASTEL, f"non-pastel colours used: {colours - PASTEL}")
        self.assertFalse(colours & LEGACY_SATURATED, "legacy saturated colour present")

    def test_multiple_terms_keep_distinct_colours(self):
        out = save_results._highlight_context_html("one two three four", ["one", "two"])
        colours = [c.lower() for c in _HEX.findall(out)]
        self.assertGreaterEqual(len(set(colours)), 2, "terms should be visually distinct")
        self.assertTrue(set(colours) <= PASTEL)

    def test_no_legacy_saturated_colours_in_source(self):
        src = (ROOT / "save_results.py").read_text(encoding="utf-8")
        lower = src.lower()
        for colour in LEGACY_SATURATED:
            self.assertNotIn(colour, lower, f"legacy saturated colour still in source: {colour}")


if __name__ == "__main__":
    unittest.main()
