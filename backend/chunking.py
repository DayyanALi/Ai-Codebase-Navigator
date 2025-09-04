# pip install langchain langchain-community langchain-text-splitters faiss-cpu rank-bm25 sentence-transformers

from pathlib import Path
import os, hashlib
import ast
from langchain.schema import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain.embeddings import OpenAIEmbeddings  # or your current embed_model

# ---------- Helpers

ALLOWED_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".java", ".go", ".rs", ".cpp", ".c", ".h", ".hpp", ".rb", ".php"
}
IGNORE_DIRS = {"node_modules", "build", "dist", ".venv", ".git", ".mypy_cache", "__pycache__"}

LANG_MAP = {
    ".py": Language.PYTHON,
    ".js": Language.JS, ".ts": Language.JS, ".tsx": Language.JS,
    ".java": Language.JAVA, ".go": Language.GO,
    ".cpp": Language.CPP, ".hpp": Language.CPP, ".c": Language.C,
    ".rs": Language.RUST, ".rb": Language.RUBY, ".php": Language.PHP
}

def iter_repo_files(root: str):
    root = Path(root)
    for p in root.rglob("*"):
        if p.is_dir():
            if p.name in IGNORE_DIRS: 
                # skip entire subtree
                for _ in p.rglob("*"): pass
            continue
        if p.suffix.lower() in ALLOWED_EXTS and p.stat().st_size < 1_000_000:  # <1MB
            yield p

def lang_for_path(path: Path):
    return LANG_MAP.get(path.suffix.lower(), None)

def compute_line_span(full_text: str, snippet: str, start_idx_hint: int = 0):
    """Find snippet in full_text and return (start_line, end_line, next_search_idx)."""
    i = full_text.find(snippet, start_idx_hint)
    if i < 0:
        # fallback: search from 0
        i = full_text.find(snippet)
    if i < 0:
        return None, None, start_idx_hint
    start_line = full_text.count("\n", 0, i) + 1
    end_line = start_line + snippet.count("\n")
    return start_line, end_line, i + len(snippet)

# ---------- Python symbol chunker (functions/classes) for high-quality chunks

def py_symbol_docs(text: str, path: str):
    """
    Extract function/class level chunks for Python using AST.
    Falls back to language-aware splitter if AST parsing fails.
    """
    docs = []
    try:
        tree = ast.parse(text)
        lines = text.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Use .lineno / .end_lineno (py>=3.8 usually has end_lineno)
                start = getattr(node, "lineno", None)
                end = getattr(node, "end_lineno", None)
                if start and end:
                    code = "\n".join(lines[start-1:end])
                    sym_name = getattr(node, "name", None)
                    kind = "class" if isinstance(node, ast.ClassDef) else "function"
                    docs.append(
                        Document(
                            page_content=code,
                            metadata={
                                "path": path, "language": "python", "symbol": sym_name,
                                "kind": kind, "start_line": start, "end_line": end
                            },
                        )
                    )
        if docs:
            return docs
    except Exception:
        pass  # fall back if AST fails

    # Fallback splitter for Python files
    splitter = RecursiveCharacterTextSplitter.from_language(
        language=Language.PYTHON, chunk_size=900, chunk_overlap=150
    )
    chunks = splitter.split_text(text)
    # enrich with approximate line ranges
    idx = 0
    out = []
    for ch in chunks:
        s, e, idx = compute_line_span(text, ch, idx)
        out.append(
            Document(page_content=ch, metadata={
                "path": path, "language": "python", "symbol": None,
                "kind": "block", "start_line": s, "end_line": e
            })
        )
    return out

# ---------- Generic code splitter (non-Python)

def generic_code_docs(text: str, path: str, lang: Language | None):
    if lang:
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=lang, chunk_size=900, chunk_overlap=150
        )
    else:
        splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=150)
    chunks = splitter.split_text(text)
    idx = 0
    out = []
    for ch in chunks:
        s, e, idx = compute_line_span(text, ch, idx)
        out.append(
            Document(page_content=ch, metadata={
                "path": path, "language": str(lang) if lang else "unknown",
                "kind": "block", "start_line": s, "end_line": e
            })
        )
    return out

# ---------- Build corpus

def load_repo_as_documents(repo_root: str):
    all_docs = []
    for p in iter_repo_files(repo_root):
        text = p.read_text(encoding="utf-8", errors="ignore")
        lang = lang_for_path(p)
        if p.suffix.lower() == ".py":
            docs = py_symbol_docs(text, str(p))
        else:
            docs = generic_code_docs(text, str(p), lang)
        all_docs.extend(docs)
    return all_docs

