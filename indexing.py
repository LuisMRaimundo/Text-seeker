# indexing.py — Full-text indexing system with inverted index
from __future__ import annotations

import os
import json
import pickle
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from collections import defaultdict
from datetime import datetime

from nlp_utils import normalize_token, expand_index_keys, stem_token
from brand import default_index_dir, legacy_index_dirs

__all__ = ["DocumentIndex", "IndexManager", "index_prefilter_allowed", "index_operator_for_tokens"]


def index_prefilter_allowed(tokens: List[str], search_terms: List[str]) -> bool:
    """
    True when the inverted index can safely narrow the file list (no NOT/NEAR/parens/wildcards).
    """
    if "(" in tokens or ")" in tokens:
        return False
    for t in tokens:
        if t == "NOT":
            return False
        if isinstance(t, str) and t.upper().startswith("NEAR/"):
            return False
    for term in search_terms:
        core = (term or "").strip().strip('"').strip("'")
        if "*" in core or "?" in core:
            return False
    return bool(search_terms)


def index_operator_for_tokens(tokens: List[str]) -> str:
    """AND if no OR in query tokens, else OR (for index union/intersection)."""
    return "OR" if "OR" in tokens else "AND"

# =============================
# Inverted Index Data Structure
# =============================

class DocumentIndex:
    """
    Inverted index for fast full-text search.
    
    Mathematical Foundation:
    - Inverted index: term -> {document_id: [positions]}
    - Search complexity: O(1) for term lookup, O(n) for intersection
    - Space complexity: O(T) where T is total terms across all documents
    
    Structure:
    {
        "term": {
            "doc_id_1": [pos1, pos2, ...],
            "doc_id_2": [pos3, pos4, ...]
        }
    }
    """
    
    def __init__(self, *, accent_fold: bool = True, use_stemming: bool = True):
        self.inverted_index: Dict[str, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.doc_id_counter = 0
        self.accent_fold = accent_fold
        self.use_stemming = use_stemming

    def _normalize_term(self, term: str) -> str:
        return normalize_token(term, accent_fold=self.accent_fold)

    def _tokenize(self, text: str) -> List[tuple[str, int]]:
        from nlp_utils import tokenize_unicode
        tokens: List[tuple[str, int]] = []
        words = tokenize_unicode(text)
        for pos, word in enumerate(words):
            for key in expand_index_keys(
                word, accent_fold=self.accent_fold, use_stemming=self.use_stemming
            ):
                tokens.append((key, pos))
        return tokens
    
    def add_document(self, filepath: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add document to index.
        
        Args:
            filepath: Path to document
            text: Full text content
            metadata: Optional metadata (size, modified time, etc.)
            
        Returns:
            Document ID
        """
        # Generate document ID
        doc_id = str(self.doc_id_counter)
        self.doc_id_counter += 1
        
        # Store document metadata
        file_stat = os.stat(filepath) if os.path.exists(filepath) else None
        self.documents[doc_id] = {
            'path': filepath,
            'size': file_stat.st_size if file_stat else 0,
            'modified': file_stat.st_mtime if file_stat else 0,
            'indexed_at': datetime.now().isoformat(),
            **(metadata or {})
        }
        
        # Tokenize and index
        tokens = self._tokenize(text)
        for term, position in tokens:
            self.inverted_index[term][doc_id].append(position)
        
        return doc_id
    
    def remove_document(self, doc_id: str) -> bool:
        """Remove document from index."""
        if doc_id not in self.documents:
            return False
        
        # Remove from inverted index
        for term in list(self.inverted_index.keys()):
            if doc_id in self.inverted_index[term]:
                del self.inverted_index[term][doc_id]
                # Remove term if no documents left
                if not self.inverted_index[term]:
                    del self.inverted_index[term]
        
        # Remove from documents
        del self.documents[doc_id]
        return True
    
    def update_document(self, filepath: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Update document in index (remove old, add new)."""
        # Find existing doc_id by path
        doc_id = None
        for did, doc_info in self.documents.items():
            if doc_info['path'] == filepath:
                doc_id = did
                break
        
        if doc_id:
            self.remove_document(doc_id)
        
        return self.add_document(filepath, text, metadata)
    
    def search_term(self, term: str) -> Dict[str, List[int]]:
        """
        Search for term in index.
        
        Returns:
            Dictionary mapping doc_id to list of positions
        """
        normalized = self._normalize_term(term)
        return dict(self.inverted_index.get(normalized, {}))
    
    def _lookup_term_keys(self, raw_term: str) -> List[str]:
        core = (raw_term or "").strip().strip('"').strip("'")
        if not core or "*" in core or "?" in core:
            return []
        keys = expand_index_keys(
            core, accent_fold=self.accent_fold, use_stemming=self.use_stemming
        )
        if self.use_stemming:
            s = stem_token(core)
            if s and s not in keys:
                keys.append(s)
        return keys or [self._normalize_term(core)]

    def search_terms(self, terms: List[str], operator: str = "AND") -> Set[str]:
        """Search for multiple terms with AND/OR (stem-aware lookup)."""
        if not terms:
            return set()

        doc_sets = []
        for raw in terms:
            if not raw:
                continue
            keys = self._lookup_term_keys(raw)
            docs: Set[str] = set()
            for key in keys:
                docs |= set(self.inverted_index.get(key, {}).keys())
            if not docs and keys:
                doc_sets.append(set())
                continue
            doc_sets.append(docs)

        if not doc_sets:
            return set()
        
        if operator.upper() == "AND":
            # Intersection: documents containing ALL terms
            result = doc_sets[0] if doc_sets else set()
            for doc_set in doc_sets[1:]:
                result &= doc_set
            return result
        else:  # OR
            # Union: documents containing ANY term
            result = set()
            for doc_set in doc_sets:
                result |= doc_set
            return result
    
    def get_document_path(self, doc_id: str) -> Optional[str]:
        """Get file path for document ID."""
        return self.documents.get(doc_id, {}).get('path')
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get index statistics."""
        total_terms = len(self.inverted_index)
        total_docs = len(self.documents)
        total_postings = sum(len(positions) for term_dict in self.inverted_index.values()
                            for positions in term_dict.values())
        
        return {
            'total_terms': total_terms,
            'total_documents': total_docs,
            'total_postings': total_postings,
            'avg_terms_per_doc': total_postings / total_docs if total_docs > 0 else 0,
            'index_size_bytes': self._estimate_size()
        }
    
    def _estimate_size(self) -> int:
        """Estimate index size in bytes."""
        # Rough estimate
        size = 0
        for term, doc_dict in self.inverted_index.items():
            size += len(term) + 8  # term string + overhead
            for doc_id, positions in doc_dict.items():
                size += len(doc_id) + 8 + len(positions) * 4  # doc_id + positions
        return size
    
    def _apply_loaded_data(self, data: dict) -> bool:
        if not isinstance(data, dict):
            return False
        ver = data.get('version')
        if ver not in (None, '1.0', '1.1', '2.0'):
            print("Error loading index: unsupported version")
            return False
        self.inverted_index = defaultdict(lambda: defaultdict(list))
        raw_index = data.get('inverted_index', {})
        for term, doc_dict in raw_index.items():
            self.inverted_index[term] = defaultdict(list, {
                str(k): list(v) for k, v in doc_dict.items()
            })
        self.documents = data.get('documents', {})
        self.doc_id_counter = int(data.get('doc_id_counter', 0))
        return True

    def save_json(self, filepath: str) -> bool:
        """Save index as UTF-8 JSON (safe, portable)."""
        try:
            data = {
                'inverted_index': {
                    term: {str(did): pos for did, pos in doc_dict.items()}
                    for term, doc_dict in self.inverted_index.items()
                },
                'documents': self.documents,
                'doc_id_counter': self.doc_id_counter,
                'version': '2.0',
                'created_at': datetime.now().isoformat(),
            }
            path = Path(filepath)
            tmp = path.with_suffix(path.suffix + '.tmp')
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            tmp.replace(path)
            return True
        except Exception as e:
            print(f"Error saving JSON index: {e}")
            return False

    def load_json(self, filepath: str) -> bool:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return self._apply_loaded_data(data)
        except Exception as e:
            print(f"Error loading JSON index: {e}")
            return False

    def save(self, filepath: str) -> bool:
        if str(filepath).lower().endswith('.json'):
            return self.save_json(filepath)
        try:
            data = {
                'inverted_index': dict(self.inverted_index),
                'documents': self.documents,
                'doc_id_counter': self.doc_id_counter,
                'version': '2.0',
                'created_at': datetime.now().isoformat(),
            }
            with open(filepath, 'wb') as f:
                pickle.dump(data, f)
            return True
        except Exception as e:
            print(f"Error saving index: {e}")
            return False

    def load(self, filepath: str) -> bool:
        if str(filepath).lower().endswith('.json'):
            return self.load_json(filepath)
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            return self._apply_loaded_data(data)
        except Exception as e:
            print(f"Error loading index: {e}")
            return False


class IndexManager:
    """
    Manages document indexing with persistence and incremental updates.
    
    Features:
    - Full-text indexing
    - Incremental updates (only changed files)
    - Index persistence
    - Fast search using inverted index
    """
    
    def __init__(
        self,
        index_dir: Optional[str] = None,
        *,
        accent_fold: bool = True,
        use_stemming: bool = True,
    ):
        self.index_dir = Path(index_dir) if index_dir else default_index_dir()
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.main_index_path = self.index_dir / 'main_index.json'
        self.legacy_pickle_path = self.index_dir / 'main_index.pkl'
        self.index = DocumentIndex(accent_fold=accent_fold, use_stemming=use_stemming)
        self._load_index()

    def _load_index(self):
        """Load JSON index; migrate from legacy dirs/pickle if needed."""
        if self.main_index_path.exists():
            if self.index.load_json(str(self.main_index_path)):
                print(f"[OK] Loaded index: {self.index.get_statistics()['total_documents']} documents")
                return
        if self.legacy_pickle_path.exists():
            try:
                if self.index.load(str(self.legacy_pickle_path)):
                    print(f"[OK] Migrated pickle index ({self.index.get_statistics()['total_documents']} docs) -> JSON")
                    self._save_index()
                    return
            except Exception as e:
                print(f"[WARN] Could not load legacy index: {e}")
        for legacy_dir in legacy_index_dirs():
            if legacy_dir.resolve() == self.index_dir.resolve():
                continue
            legacy_json = legacy_dir / "main_index.json"
            legacy_pkl = legacy_dir / "main_index.pkl"
            if legacy_json.exists() and self.index.load_json(str(legacy_json)):
                print(f"[OK] Migrated index from {legacy_dir.name} -> {self.index_dir.name}")
                self._save_index()
                return
            if legacy_pkl.exists() and self.index.load(str(legacy_pkl)):
                print(f"[OK] Migrated pickle from {legacy_dir.name} -> {self.index_dir.name}")
                self._save_index()
                return

    def _save_index(self):
        try:
            self.index.save_json(str(self.main_index_path))
        except Exception as e:
            print(f"[WARN] Could not save index: {e}")
    
    def _file_hash(self, filepath: str) -> Optional[str]:
        """Calculate file hash for change detection."""
        try:
            with open(filepath, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return None
    
    def _should_reindex(self, filepath: str, current_hash: Optional[str]) -> bool:
        """Check if file needs reindexing."""
        hash_file = self.index_dir / f"{hashlib.md5(filepath.encode()).hexdigest()}.hash"
        
        if not hash_file.exists():
            return True
        
        try:
            stored_hash = hash_file.read_text().strip()
            return stored_hash != current_hash
        except:
            return True
    
    def _save_file_hash(self, filepath: str, file_hash: str):
        """Save file hash for change detection."""
        hash_file = self.index_dir / f"{hashlib.md5(filepath.encode()).hexdigest()}.hash"
        try:
            hash_file.write_text(file_hash)
        except:
            pass
    
    def index_file(self, filepath: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Index a file (with change detection).
        
        Returns:
            True if indexed, False if skipped (unchanged)
        """
        if not os.path.exists(filepath):
            return False
        
        # Check if file needs reindexing
        file_hash = self._file_hash(filepath)
        if not self._should_reindex(filepath, file_hash):
            return False  # File unchanged, skip
        
        # Add/update in index
        self.index.update_document(filepath, text, metadata)
        
        # Save hash
        if file_hash:
            self._save_file_hash(filepath, file_hash)
        
        return True

    def search(self, query_terms: List[str], operator: str = "AND") -> List[str]:
        """
        Search index for query terms.
        
        Returns:
            List of file paths matching the query
        """
        doc_ids = self.index.search_terms(query_terms, operator)
        paths = []
        for doc_id in doc_ids:
            path = self.index.get_document_path(doc_id)
            if path:
                paths.append(path)
        return paths
    
    def get_index_statistics(self) -> Dict[str, Any]:
        """Get index statistics."""
        return self.index.get_statistics()
    
    def clear_index(self):
        """Clear entire index."""
        self.index = DocumentIndex()
        # Remove hash files
        for hash_file in self.index_dir.glob("*.hash"):
            try:
                hash_file.unlink()
            except:
                pass
        self._save_index()
    
    def save(self):
        """Save index to disk."""
        self._save_index()
