# performance_optimizer.py — parallel processing and BM25 ranking
from __future__ import annotations

import math
import multiprocessing
import sys
from typing import List, Any, Optional, Callable, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

__all__ = ["ParallelProcessor", "calculate_bm25_score"]


class ParallelProcessor:
    """Thread-pool file processing for I/O-bound search workloads."""

    def __init__(self, max_workers: Optional[int] = None):
        if max_workers is None:
            cap = 4 if sys.platform == "win32" else 8
            max_workers = min(multiprocessing.cpu_count(), cap)
        self.max_workers = max(1, max_workers)

    def process_files_parallel(
        self,
        file_paths: List[Any],
        process_fn: Callable[[Any], Any],
        progress_callback: Optional[Callable[[int, int], None]] = None,
        file_timeout_sec: Optional[float] = None,
        on_timeout: Optional[Callable[[Any], None]] = None,
    ) -> Tuple[List[Any], List[Any]]:
        """
        Process files in parallel.

        Returns (results, timed_out_items).

        Per-file time limits must be enforced inside ``process_fn`` (deadline
        starts when the worker actually picks up the file). This pool does
        **not** measure from submit/queue time — that incorrectly skipped
        files still waiting for a free worker.
        """
        results: List[Any] = []
        timed_out: List[Any] = []
        total = len(file_paths)
        processed = 0

        if total == 0:
            return results, timed_out

        # file_timeout_sec / on_timeout kept for API compatibility; enforcement
        # is cooperative inside process_fn (see app.process_file_wrapper).
        _ = file_timeout_sec
        _ = on_timeout

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_item = {
                executor.submit(process_fn, item): item for item in file_paths
            }
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    print(f"Error processing {item}: {e}")
                finally:
                    processed += 1
                    if progress_callback:
                        progress_callback(processed, total)

        return results, timed_out


def calculate_bm25_score(
    term: str,
    document_text: str,
    avg_doc_length: float,
    total_docs: int,
    doc_frequency: int,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    """BM25 relevance score for a term in a document."""
    doc_terms = document_text.lower().split()
    term_count = doc_terms.count(term.lower())
    doc_length = len(doc_terms)
    idf = math.log((total_docs - doc_frequency + 0.5) / (doc_frequency + 0.5) + 1.0)
    numerator = term_count * (k1 + 1)
    denominator = (
        term_count + k1 * (1 - b + b * (doc_length / avg_doc_length))
        if avg_doc_length > 0
        else term_count + k1
    )
    return idf * (numerator / denominator) if denominator > 0 else 0.0
