"""Smoke integration: index + search on a temp folder."""
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import search_in_files


class TestSearchIntegration(unittest.TestCase):
    def test_txt_and_stemming(self):
        with tempfile.TemporaryDirectory() as td:
            a = Path(td) / "music.txt"
            a.write_text("The pianos are playing loudly.\n", encoding="utf-8")
            b = Path(td) / "other.txt"
            b.write_text("violin only", encoding="utf-8")

            res = search_in_files(
                directory=td,
                boolean_query="piano",
                file_types={"txt": True, "pdf": False, "docx": False,
                            "html": False, "image": False, "md": False,
                            "excel": False, "csv": False},
                min_relevance=0.0,
                use_indexing=True,
                use_parallel=False,
                use_stemming=True,
                include_subfolders=False,
            )
            paths = {r["filepath"] for r in res}
            self.assertIn(str(a), paths)
            self.assertNotIn(str(b), paths)

    def test_index_json_created(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "doc.txt"
            f.write_text("zebra unique term", encoding="utf-8")
            search_in_files(
                directory=td,
                boolean_query="zebra",
                file_types={"txt": True, "pdf": False, "docx": False,
                            "html": False, "image": False, "md": False,
                            "excel": False, "csv": False},
                use_indexing=True,
                use_parallel=False,
                include_subfolders=False,
            )
            from indexing import IndexManager
            from brand import default_index_dir
            mgr = IndexManager(index_dir=str(default_index_dir()))
            stats = mgr.get_index_statistics()
            self.assertGreaterEqual(stats["total_documents"], 1)


if __name__ == "__main__":
    unittest.main()
