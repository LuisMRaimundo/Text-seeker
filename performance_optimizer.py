# performance_optimizer.py — parallel processing and BM25 ranking
from __future__ import annotations

import math
import multiprocessing
import sys
from typing import List, Any, Optional, Callable
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
    ) -> List[Any]:
        results: List[Any] = []
        total = len(file_paths)
        processed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_path = {executor.submit(process_fn, path): path for path in file_paths}
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    print(f"Error processing {path}: {e}")
                finally:
                    processed += 1
                    if progress_callback:
                        progress_callback(processed, total)

        return results


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
