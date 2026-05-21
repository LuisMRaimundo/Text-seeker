"""Tests for inverted index and IndexManager."""
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from indexing import DocumentIndex, IndexManager, index_prefilter_allowed


class TestDocumentIndex(unittest.TestCase):
    def test_and_search(self):
        idx = DocumentIndex()
        idx.add_document("/a.txt", "alpha beta gamma")
        idx.add_document("/b.txt", "alpha only")
        ids = idx.search_terms(["alpha", "beta"], operator="AND")
        self.assertEqual(len(ids), 1)

    def test_or_search(self):
        idx = DocumentIndex()
        idx.add_document("/a.txt", "alpha")
        idx.add_document("/b.txt", "beta")
        ids = idx.search_terms(["alpha", "beta"], operator="OR")
        self.assertEqual(len(ids), 2)

    def test_persist_roundtrip_json(self):
        idx = DocumentIndex()
        idx.add_document("/x.txt", "hello world")
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "idx.json")
            self.assertTrue(idx.save_json(path))
            idx2 = DocumentIndex()
            self.assertTrue(idx2.load_json(path))
            self.assertEqual(idx2.get_statistics()["total_documents"], 1)

    def test_stem_index_lookup(self):
        idx = DocumentIndex(use_stemming=True)
        idx.add_document("/a.txt", "running fast")
        found = idx.search_terms(["run"], operator="AND")
        self.assertEqual(len(found), 1)


class TestIndexManager(unittest.TestCase):
    def test_incremental_skip(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = IndexManager(index_dir=td)
            f = Path(td) / "doc.txt"
            f.write_text("unique term zebra", encoding="utf-8")
            self.assertTrue(mgr.index_file(str(f), "unique term zebra"))
            mgr.save()
            self.assertTrue((Path(td) / "main_index.json").exists())
            self.assertFalse(mgr.index_file(str(f), "unique term zebra"))


if __name__ == "__main__":
    unittest.main()
