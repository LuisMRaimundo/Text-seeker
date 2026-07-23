# performance_optimizer.py — parallel processing and BM25 ranking
from __future__ import annotations

import math
import multiprocessing
import sys
import time
from typing import List, Any, Optional, Callable, Tuple
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

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
        file_timeout_sec: Optional[float] = 180.0,
        on_timeout: Optional[Callable[[Any], None]] = None,
    ) -> Tuple[List[Any], List[Any]]:
        """
        Process files in parallel.

        Returns (results, timed_out_items). If a file exceeds file_timeout_sec,
        it is skipped so the batch can continue; on_timeout(item) is called if set.
        Stuck worker threads are abandoned via shutdown(wait=False).
        """
        results: List[Any] = []
        timed_out: List[Any] = []
        total = len(file_paths)
        processed = 0

        if total == 0:
            return results, timed_out

        timeout = float(file_timeout_sec) if file_timeout_sec and file_timeout_sec > 0 else None
        executor = ThreadPoolExecutor(max_workers=self.max_workers)
        try:
            future_to_item = {executor.submit(process_fn, item): item for item in file_paths}
            start_times = {fut: time.time() for fut in future_to_item}
            pending = set(future_to_item.keys())

            while pending:
                done, pending = wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)
                now = time.time()

                for fut in done:
                    item = future_to_item[fut]
                    try:
                        result = fut.result(timeout=0)
                        if result:
                            results.append(result)
                    except Exception as e:
                        print(f"Error processing {item}: {e}")
                    finally:
                        processed += 1
                        if progress_callback:
                            progress_callback(processed, total)

                if timeout is not None:
                    for fut in list(pending):
                        if now - start_times[fut] < timeout:
                            continue
                        item = future_to_item[fut]
                        pending.discard(fut)
                        timed_out.append(item)
                        if on_timeout is not None:
                            try:
                                on_timeout(item)
                            except Exception:
                                pass
                        processed += 1
                        if progress_callback:
                            progress_callback(processed, total)
        finally:
            # Do not block the batch on a hung Tesseract/Poppler worker
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                executor.shutdown(wait=False)

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
