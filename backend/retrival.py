from __future__ import annotations
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field
from pathlib import Path
import ast
import hashlib
import re

import numpy as np
import faiss
from rank_bm25 import BM25Okapi

# ---------------------------------------------------------------------------
# Lightweight Document dataclass (replaces langchain.schema.Document)
# ---------------------------------------------------------------------------

@dataclass
class Document:
    page_content: str = ""
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Language-aware separators (mirrors langchain's RecursiveCharacterTextSplitter)
# ---------------------------------------------------------------------------

_SEPARATORS: dict[str, list[str]] = {
    "python": ["\nclass ", "\ndef ", "\n\tdef ", "\n\n", "\n", " ", ""],
    "js":     ["\nfunction ", "\nconst ", "\nlet ", "\nvar ", "\nclass ",
               "\nif ", "\nfor ", "\nwhile ", "\nswitch ", "\ncase ",
               "\ndefault ", "\n\n", "\n", " ", ""],
    "java":   ["\nclass ", "\npublic ", "\nprotected ", "\nprivate ",
               "\nstatic ", "\nif ", "\nfor ", "\nwhile ", "\nswitch ",
               "\n\n", "\n", " ", ""],
    "go":     ["\nfunc ", "\nvar ", "\nconst ", "\ntype ", "\nif ",
               "\nfor ", "\nswitch ", "\ncase ", "\n\n", "\n", " ", ""],
    "cpp":    ["\nclass ", "\nvoid ", "\nint ", "\nfloat ", "\ndouble ",
               "\nif ", "\nfor ", "\nwhile ", "\nswitch ", "\n\n", "\n", " ", ""],
    "c":      ["\nvoid ", "\nint ", "\nfloat ", "\ndouble ", "\nif ",
               "\nfor ", "\nwhile ", "\nswitch ", "\n\n", "\n", " ", ""],
    "rust":   ["\nfn ", "\nconst ", "\nlet ", "\nif ", "\nwhile ",
               "\nfor ", "\nloop ", "\nmatch ", "\nconst ", "\n\n", "\n", " ", ""],
    "ruby":   ["\ndef ", "\nclass ", "\nif ", "\nunless ", "\nwhile ",
               "\nfor ", "\ndo ", "\nbegin ", "\nrescue ", "\n\n", "\n", " ", ""],
    "php":    ["\nfunction ", "\nclass ", "\nif ", "\nforeach ", "\nwhile ",
               "\n\n", "\n", " ", ""],
}
_DEFAULT_SEPS = ["\n\n", "\n", " ", ""]


def _get_separators(lang_key: Optional[str]) -> list[str]:
    if not lang_key:
        return _DEFAULT_SEPS
    return _SEPARATORS.get(lang_key.lower().strip(), _DEFAULT_SEPS)


# ---------------------------------------------------------------------------
# Language mapping (replaces langchain_text_splitters.Language enum)
# ---------------------------------------------------------------------------

LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "js", ".ts": "js", ".tsx": "js",
    ".java": "java", ".go": "go",
    ".cpp": "cpp", ".hpp": "cpp", ".c": "c",
    ".rs": "rust", ".rb": "ruby", ".php": "php",
}


def _lang_for_source(source_path: Optional[str]) -> Optional[str]:
    if not source_path:
        return None
    return LANG_MAP.get(Path(source_path).suffix.lower(), None)


# ---------------------------------------------------------------------------
# Recursive character splitter (replaces RecursiveCharacterTextSplitter)
# ---------------------------------------------------------------------------

def _recursive_split(text: str, separators: list[str],
                     chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split *text* recursively using the ordered *separators* list."""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    # pick the first separator that appears
    sep = ""
    for s in separators:
        if s in text:
            sep = s
            break

    parts = text.split(sep) if sep else list(text)
    chunks: list[str] = []
    current = ""

    for part in parts:
        candidate = current + (sep if current else "") + part
        if len(candidate) > chunk_size and current:
            chunks.append(current)
            # overlap: keep the tail of `current`
            overlap_text = current[-chunk_overlap:] if chunk_overlap else ""
            current = overlap_text + sep + part if overlap_text else part
        else:
            current = candidate

    if current.strip():
        chunks.append(current)

    # if any chunk still too big, recurse with next separator level
    remaining_seps = separators[separators.index(sep) + 1:] if sep in separators else separators[1:]
    final: list[str] = []
    for ch in chunks:
        if len(ch) > chunk_size and remaining_seps:
            final.extend(_recursive_split(ch, remaining_seps, chunk_size, chunk_overlap))
        else:
            final.append(ch)
    return final


# ---------------------------------------------------------------------------
# Compute line span helper (unchanged)
# ---------------------------------------------------------------------------

def _compute_line_span(full_text: str, snippet: str, start_idx_hint: int = 0):
    """Find snippet within full_text; return (start_line, end_line, next_search_idx)."""
    i = full_text.find(snippet, start_idx_hint)
    if i < 0:
        i = full_text.find(snippet)
    if i < 0:
        return None, None, start_idx_hint
    start_line = full_text.count("\n", 0, i) + 1
    end_line = start_line + snippet.count("\n")
    return start_line, end_line, i + len(snippet)


# ---------------------------------------------------------------------------
# split_documents (same algorithm, no langchain deps)
# ---------------------------------------------------------------------------

def split_documents(docs: List[Document],
                    code_chunk_size: int = 900,
                    code_chunk_overlap: int = 150) -> List[Document]:
    """Return high-quality code chunks with path/language/line ranges in metadata."""
    out: List[Document] = []

    for d in docs:
        text = d.page_content or ""
        source = d.metadata.get("source") if d.metadata else None
        lang = _lang_for_source(source)

        # AST-based splitting for Python
        if lang == "python":
            try:
                tree = ast.parse(text)
                lines = text.splitlines()
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        start = getattr(node, "lineno", None)
                        end = getattr(node, "end_lineno", None)
                        if start and end:
                            code = "\n".join(lines[start - 1:end])
                            sym = getattr(node, "name", None)
                            kind = "class" if isinstance(node, ast.ClassDef) else "function"
                            header = f"{kind} {sym} in {source or 'unknown'}"
                            chunk = Document(
                                page_content=f"{header}\n{code}",
                                metadata={
                                    "path": source, "language": "python",
                                    "symbol": sym, "kind": kind,
                                    "start_line": start, "end_line": end,
                                },
                            )
                            out.append(chunk)
                if any(
                    c.metadata.get("kind") in ("function", "class")
                    for c in out
                    if c.metadata and c.metadata.get("path") == source
                ):
                    continue
            except Exception:
                pass

        # Recursive character splitting
        separators = _get_separators(lang)
        pieces = _recursive_split(text, separators, code_chunk_size, code_chunk_overlap)
        idx = 0
        for ch in pieces:
            s, e, idx = _compute_line_span(text, ch, idx)
            header = f"block in {source or 'unknown'}"
            out.append(
                Document(
                    page_content=f"{header}\n{ch}",
                    metadata={
                        "path": source, "language": lang or "unknown",
                        "symbol": None, "kind": "block",
                        "start_line": s, "end_line": e,
                    },
                )
            )
    return out


# ---------------------------------------------------------------------------
# build_vector_db  (direct faiss + rank_bm25, no langchain wrappers)
# ---------------------------------------------------------------------------

def build_vector_db(chunks: List[Document], embed_model) -> Dict[str, object]:
    """Return an in-memory bundle: {'vector': ..., 'bm25': ..., 'chunks': ...}."""
    texts = [c.page_content for c in chunks]

    # --- FAISS index ---
    embeddings = embed_model.embed_documents(texts)          # list[list[float]]
    matrix = np.array(embeddings, dtype="float32")
    dim = matrix.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(matrix)

    # --- BM25 ---
    tokenized = [_tokenize(t) for t in texts]
    bm25 = BM25Okapi(tokenized)

    return {"vector": index, "bm25": bm25, "chunks": chunks, "matrix": matrix}


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer for BM25."""
    return re.findall(r"\w+", text.lower())


# ---------------------------------------------------------------------------
# Dedup / scoring helpers (unchanged logic)
# ---------------------------------------------------------------------------

def _doc_key(d: Document) -> str:
    path = (d.metadata or {}).get("path")
    s = (d.metadata or {}).get("start_line")
    e = (d.metadata or {}).get("end_line")
    head = (d.page_content or "")[:80]
    return f"{path}:{s}:{e}:{hashlib.sha1(head.encode()).hexdigest()[:8]}"


def _rrf_fuse(v_docs_with_scores, b_docs, k: int = 50) -> List[Document]:
    v_sorted = sorted(v_docs_with_scores, key=lambda x: x[1])  # smaller distance = better
    scores: dict = {}
    for rank, (doc, _) in enumerate(v_sorted, start=1):
        key = _doc_key(doc)
        scores.setdefault(key, (doc, 0.0))
        scores[key] = (doc, scores[key][1] + 1.0 / (60 + rank))
    for rank, doc in enumerate(b_docs, start=1):
        key = _doc_key(doc)
        scores.setdefault(key, (doc, 0.0))
        scores[key] = (doc, scores[key][1] + 1.0 / (60 + rank))
    return [d for d, _ in sorted(scores.values(), key=lambda x: x[1], reverse=True)[:k]]


def _stitch(docs: List[Document], token_budget_chars: int = 8000) -> List[Document]:
    kept, seen, used = [], set(), 0
    for d in docs:
        key = _doc_key(d)
        if key in seen:
            continue
        txt = d.page_content or ""
        if used + len(txt) > token_budget_chars:
            break
        kept.append(d)
        seen.add(key)
        used += len(txt)
    return kept


def _rerank(query: str, candidates: List[Document]) -> List[Document]:
    # Cross-encoder reranker was already disabled (_CE = None). Keep the stub.
    return candidates


# ---------------------------------------------------------------------------
# FAISS / BM25 search helpers (replaces langchain wrappers)
# ---------------------------------------------------------------------------

def _faiss_search(vdb: dict, query: str, embed_model, k: int) -> list[tuple]:
    """Return [(Document, distance), ...]."""
    q_emb = np.array([embed_model.embed_query(query)], dtype="float32")
    distances, indices = vdb["vector"].search(q_emb, k)
    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0:
            continue
        results.append((vdb["chunks"][idx], float(dist)))
    return results


def _bm25_search(vdb: dict, query: str, k: int) -> list[Document]:
    """Return top-k BM25 hits."""
    tokens = _tokenize(query)
    scores = vdb["bm25"].get_scores(tokens)
    top_k = np.argsort(scores)[::-1][:k]
    return [vdb["chunks"][i] for i in top_k if scores[i] > 0]


# ---------------------------------------------------------------------------
# Main retrieval (same algorithm, no langchain)
# ---------------------------------------------------------------------------

def retrieve_context(
    vdb: Dict[str, object],
    query: str,
    embed_model=None,
    *,
    min_results: int = 4,
    k_vec: int = 40,
    k_lex: int = 40,
    token_budget_chars: int = 8000,
    use_reranker: bool = True,
) -> Tuple[List[Document], str]:
    """
    Returns (docs, context_block_str). context_block_str is ready for your LLM prompt.
    """
    v_hits = _faiss_search(vdb, query, embed_model, k=k_vec)
    b_hits = _bm25_search(vdb, query, k=k_lex)

    candidates = _rrf_fuse(v_hits, b_hits, k=50)
    if use_reranker:
        candidates = _rerank(query, candidates)

    if len(candidates) < min_results:
        q2 = query.replace("_", " ").replace("-", " ")
        v_hits = _faiss_search(vdb, q2, embed_model, k=k_vec * 2)
        b_hits = _bm25_search(vdb, q2, k=k_lex * 2)
        candidates = _rrf_fuse(v_hits, b_hits, k=80)
        if use_reranker:
            candidates = _rerank(query, candidates)

    packed = _stitch(candidates, token_budget_chars=token_budget_chars)

    blocks = []
    for d in packed:
        path = (d.metadata or {}).get("path")
        s = (d.metadata or {}).get("start_line")
        e = (d.metadata or {}).get("end_line")
        lang = (d.metadata or {}).get("language", "text")
        header = f"# {path}:{s}-{e}"
        blocks.append(f"```{lang}\n{header}\n{d.page_content}\n```")

    return packed, "\n\n".join(blocks)
