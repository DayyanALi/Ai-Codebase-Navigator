from typing import List, Tuple, Dict, Optional
from pathlib import Path
import ast, hashlib

from langchain.schema import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever

try:
    # from sentence_transformers import CrossEncoder
    # # _CE = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    _CE = None
except Exception:
    _CE = None

LANG_MAP = {
    ".py": Language.PYTHON,
    ".js": Language.JS, ".ts": Language.JS, ".tsx": Language.JS,
    ".java": Language.JAVA, ".go": Language.GO,
    ".cpp": Language.CPP, ".hpp": Language.CPP, ".c": Language.C,
    ".rs": Language.RUST, ".rb": Language.RUBY, ".php": Language.PHP
}

def _lang_for_source(source_path: Optional[str]) -> Optional[Language]:
    if not source_path:
        return None
    return LANG_MAP.get(Path(source_path).suffix.lower(), None)

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

def split_documents(docs: List[Document],
                    code_chunk_size: int = 900,
                    code_chunk_overlap: int = 150) -> List[Document]:
    """Return high-quality code chunks with path/language/line ranges in metadata."""
    out: List[Document] = []

    for d in docs:
        text = d.page_content or ""
        source = d.metadata.get("source") if d.metadata else None
        lang = _lang_for_source(source)

        if lang == Language.PYTHON:
            try:
                tree = ast.parse(text)
                lines = text.splitlines()
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        start = getattr(node, "lineno", None)
                        end = getattr(node, "end_lineno", None)
                        if start and end:
                            code = "\n".join(lines[start-1:end])
                            sym = getattr(node, "name", None)
                            kind = "class" if isinstance(node, ast.ClassDef) else "function"
                            header = f"{kind} {sym} in {source or 'unknown'}"
                            chunk = Document(
                                page_content=f"{header}\n{code}",
                                metadata={
                                    "path": source, "language": "python",
                                    "symbol": sym, "kind": kind,
                                    "start_line": start, "end_line": end
                                }
                            )
                            out.append(chunk)
                if any(md.get("kind") in ("function", "class") for md in (c.metadata for c in out if c.metadata and c.metadata.get("path")==source)):
                    continue  
            except Exception:
                pass  

        splitter = (RecursiveCharacterTextSplitter.from_language(language=lang,
                                                                 chunk_size=code_chunk_size,
                                                                 chunk_overlap=code_chunk_overlap)
                    if lang else
                    RecursiveCharacterTextSplitter(chunk_size=code_chunk_size,
                                                   chunk_overlap=code_chunk_overlap))
        pieces = splitter.split_text(text)
        idx = 0
        for ch in pieces:
            s, e, idx = _compute_line_span(text, ch, idx)
            header = f"block in {source or 'unknown'}"
            out.append(
                Document(
                    page_content=f"{header}\n{ch}",
                    metadata={
                        "path": source, "language": str(lang) if lang else "unknown",
                        "symbol": None, "kind": "block",
                        "start_line": s, "end_line": e
                    }
                )
            )
    return out

def build_vector_db(chunks: List[Document], embed_model) -> Dict[str, object]:
    """Return an in-memory bundle: {'vector': FAISS, 'bm25': BM25Retriever}."""
    vector = FAISS.from_documents(chunks, embed_model)
    bm25 = BM25Retriever.from_documents(chunks)
    bm25.k = 25
    return {"vector": vector, "bm25": bm25}

def _doc_key(d: Document) -> str:
    path = (d.metadata or {}).get("path")
    s = (d.metadata or {}).get("start_line")
    e = (d.metadata or {}).get("end_line")
    head = (d.page_content or "")[:80]
    return f"{path}:{s}:{e}:{hashlib.sha1(head.encode()).hexdigest()[:8]}"

def _rrf_fuse(v_docs_with_scores, b_docs, k: int = 50) -> List[Document]:
    v_sorted = sorted(v_docs_with_scores, key=lambda x: x[1])  # smaller distance is better
    scores = {}
    for rank, (doc, _) in enumerate(v_sorted, start=1):
        key = _doc_key(doc)
        scores.setdefault(key, (doc, 0.0))
        scores[key] = (doc, scores[key][1] + 1.0/(60 + rank))
    for rank, doc in enumerate(b_docs, start=1):
        key = _doc_key(doc)
        scores.setdefault(key, (doc, 0.0))
        scores[key] = (doc, scores[key][1] + 1.0/(60 + rank))
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
        kept.append(d); seen.add(key); used += len(txt)
    return kept

def _rerank(query: str, candidates: List[Document]) -> List[Document]:
    if not _CE or not candidates:
        print("returing without rerank")
        return candidates
    pairs = [(query, d.page_content) for d in candidates]
    scores = _CE.predict(pairs, convert_to_numpy=True)
    order = list(reversed(scores.argsort()))
    return [candidates[i] for i in order]

def retrieve_context(
    vdb: Dict[str, object],
    query: str,
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
    vector: FAISS = vdb["vector"]
    bm25: BM25Retriever = vdb["bm25"]

    v_hits = vector.similarity_search_with_score(query, k=k_vec)   
    b_hits = bm25.invoke(query)[:k_lex]                            

    candidates = _rrf_fuse(v_hits, b_hits, k=50)
    if use_reranker:
        candidates = _rerank(query, candidates)

    if len(candidates) < min_results:
        # widen recall on identifiers
        q2 = query.replace("_", " ").replace("-", " ")
        v_hits = vector.similarity_search_with_score(q2, k=k_vec * 2)
        b_hits = bm25.invoke(q2)[:k_lex * 2]
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
