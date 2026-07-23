"""Tests for JSON, TTL/RDF, and ebook extractors/search."""
import json
import tempfile
import unittest
import zipfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import search_in_files
from search_json import extract_json_text
from search_rdf import extract_rdf_text
from search_ebook import extract_ebook_text


class TestNewFormats(unittest.TestCase):
    def test_json_extract_and_search(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "doc.json"
            p.write_text(json.dumps({"title": "uniquezebraword", "n": 1}), encoding="utf-8")
            self.assertIn("uniquezebraword", extract_json_text(str(p)))
            res = search_in_files(
                directory=td,
                boolean_query="uniquezebraword",
                file_types={
                    "json": True, "txt": False, "pdf": False, "docx": False,
                    "html": False, "image": False, "md": False, "excel": False,
                    "csv": False, "ttl": False, "ebook": False,
                },
                min_relevance=0.0,
                use_indexing=False,
                use_parallel=False,
                include_subfolders=False,
                file_timeout_sec=60,
            )
            self.assertTrue(any(str(p) == r.get("filepath") for r in res))

    def test_ttl_extract(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sample.ttl"
            p.write_text(
                '@prefix ex: <http://example.org/> .\n'
                'ex:Book ex:title "Spectral Texture Study" .\n',
                encoding="utf-8",
            )
            text = extract_rdf_text(str(p))
            self.assertIn("Spectral Texture Study", text)

    def test_epub_extract(self):
        with tempfile.TemporaryDirectory() as td:
            epub = Path(td) / "book.epub"
            with zipfile.ZipFile(epub, "w") as zf:
                zf.writestr(
                    "META-INF/container.xml",
                    '<?xml version="1.0"?>'
                    '<container><rootfiles>'
                    '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                    '</rootfiles></container>',
                )
                zf.writestr(
                    "OEBPS/content.opf",
                    '<?xml version="1.0"?>'
                    '<package>'
                    '<manifest>'
                    '<item id="c1" href="chap1.xhtml" media-type="application/xhtml+xml"/>'
                    '</manifest>'
                    '<spine><itemref idref="c1"/></spine>'
                    '</package>',
                )
                zf.writestr(
                    "OEBPS/chap1.xhtml",
                    '<html><body><p>Hello epubuniquephrase here</p></body></html>',
                )
            text = extract_ebook_text(str(epub))
            self.assertIn("epubuniquephrase", text)


if __name__ == "__main__":
    unittest.main()
