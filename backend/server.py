import logging
import os
from uuid import uuid4

import httpx
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from utils import embedding_model_gemini, build_tree, gemini_flash_lite
from template import chat_model_template, rephrase_question_template
from retrival import split_documents, Document
from supabase_store import SupabaseVectorStore, build_context_block

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
Clients = {}
embed_model = embedding_model_gemini()
chat_model = gemini_flash_lite()
vector_store = SupabaseVectorStore()
MAX_FILE_BYTES = int(os.getenv("MAX_REPO_FILE_BYTES", "250000"))

EXT_TO_LANG = {
    "cpp": "cpp",
    "go": "go",
    "java": "java",
    "kt": "kotlin",
    "js": "js",
    "ts": "ts",
    "php": "php",
    "proto": "proto",
    "py": "python",
    "rst": "rst",
    "rb": "ruby",
    "rs": "rust",
    "scala": "scala",
    "swift": "swift",
    "md": "markdown",
    "tex": "latex",
    "html": "html",
    "sol": "solidity",
    "cs": "csharp",
    "cob": "cobol",
    "c": "c",
    "lua": "lua",
    "pl": "perl",
    "hs": "haskell",
    "xml": "xml",
    "h": "h"
}

_ALLOWED_EXTENSIONS = tuple(EXT_TO_LANG.keys())

# ---------------------------------------------------------------------------
# GitHub helpers  (replaces langchain GithubFileLoader)
# ---------------------------------------------------------------------------

_GH_API = "https://api.github.com"


def _github_headers() -> dict:
    return {
        "Authorization": f"token {os.environ['ACCESS_TOKEN']}",
        "Accept": "application/vnd.github+json",
    }


def _fetch_repo_files(repo_name: str, branch: str) -> list[Document]:
    """Download every matching file from *repo_name* at *branch* via the GitHub API."""
    url = f"{_GH_API}/repos/{repo_name}/git/trees/{branch}?recursive=1"
    headers = _github_headers()

    resp = httpx.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    tree = resp.json().get("tree", [])

    # filter to files with allowed extensions
    file_entries = [
        entry for entry in tree
        if entry["type"] == "blob" and entry["path"].endswith(_ALLOWED_EXTENSIONS)
        and entry.get("size", 0) <= MAX_FILE_BYTES
    ]

    docs: list[Document] = []
    for entry in file_entries:
        file_path = entry["path"]
        raw_url = f"https://raw.githubusercontent.com/{repo_name}/{branch}/{file_path}"
        try:
            file_resp = httpx.get(raw_url, headers=headers, timeout=30)
            file_resp.raise_for_status()
            content = file_resp.text
        except Exception:
            continue

        docs.append(Document(
            page_content=content,
            metadata={"source": f"{repo_name}/{branch}/{file_path}"},
        ))

    return docs


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def ensure_session(session_id):
    return Clients.setdefault(session_id, {"history": []})


# ---------------------------------------------------------------------------
# Chat helpers  (replaces langchain PromptTemplate | ChatModel | StrOutputParser)
# ---------------------------------------------------------------------------

def get_rephrased_question(question: str, chat_history: list, chat_model_inst):
    """Use the rephrase template to make standalone questions."""
    history_str = "\n".join(
        f"{msg['role'].capitalize()}: {msg['content']}" for msg in chat_history
    )
    filled_prompt = rephrase_question_template.format(
        history=history_str, question=question
    )
    return chat_model_inst.invoke([{"role": "user", "content": filled_prompt}])


def answer_question(question: str, context: str, chat_model_inst) -> str:
    """Use the chat template to produce an answer."""
    filled_prompt = chat_model_template.format(
        context=context, question=question
    )
    return chat_model_inst.invoke([{"role": "user", "content": filled_prompt}])


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def _sanitize_error(e: Exception) -> str:
    err_str = str(e).lower()
    
    # API quota/billing errors
    if "insufficient_quota" in err_str or "exceeded your current quota" in err_str:
        return "API quota exceeded. Please check your API billing details."
    elif "incorrect api key" in err_str or "invalid api key" in err_str:
        return "Invalid API key configured on the server."
    elif "missing gemini api key" in err_str:
        return "Gemini API key missing. Set GEMINI_API_KEY or GOOGLE_API_KEY on the server."
    elif "missing supabase config" in err_str:
        return "Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY on the server."
    elif "match_code_chunks" in err_str or "code_chunks" in err_str or "code_repositories" in err_str:
        return "Supabase schema is not ready. Run backend/supabase_schema.sql in your Supabase SQL editor."
        
    # GitHub HTTP errors
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return "Repository or branch not found. Please verify the URL."
        elif status == 429:
            return "Gemini API rate limit hit while indexing embeddings. Please wait a minute, try a smaller repo, or enable billing for higher limits."
        elif status in (500, 502, 503, 504):
            return "Gemini API is temporarily unavailable. Please retry in a moment."
        elif status == 403:
            return "GitHub API rate limit exceeded or access denied. Please check the access token."
            
    # Generic safe fallback (hide the stacktrace/url details)
    return "An internal server error occurred while processing your request."

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/query', methods=["POST"])
def query_repo():
    data = request.get_json()
    session_id = data["session_id"]
    question = data["question"]
    if not session_id or not question:
        return jsonify({"error": "Invalid input"}), 400
    try:
        session = ensure_session(session_id)
        chat_history = session["history"]
        rephrased_question = get_rephrased_question(question, chat_history, chat_model)
        query_embedding = embed_model.embed_query(rephrased_question)
        combined_docs = vector_store.match_chunks(session_id, query_embedding)
        combined_result = build_context_block(combined_docs)
        answer = answer_question(question, combined_result, chat_model)
        session["history"].append({"role": "user", "content": rephrased_question})
        session["history"].append({"role": "assistant", "content": answer})
        sources = [
            doc.metadata.get("path")
            for doc in combined_docs
            if doc.metadata and doc.metadata.get("path")
        ]
        return jsonify({"answer": answer, "sources": list(dict.fromkeys(sources))})
    except Exception as e:
        logger.error(f"Error in /query endpoint: {e}", exc_info=True)
        safe_msg = _sanitize_error(e)
        return jsonify({"error": safe_msg}), 400


@app.route("/remove_repo", methods=["POST", "DELETE"])
def remove_repo():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    try:
        Clients.pop(session_id, None)
        vector_store.delete_session(session_id)
    except Exception as e:
        logger.error(f"Error in /remove_repo endpoint: {e}", exc_info=True)
        return jsonify({"error": _sanitize_error(e)}), 400

    return jsonify({"message": "session evicted", "session_id": session_id}), 200


@app.route('/clone', methods=["POST"])
def clone_repo():
    data = request.get_json()
    repo_name = data["repo_name"]
    branch_name = data["branch_name"]
    session_id = str(uuid4())
    try:
        docs = _fetch_repo_files(repo_name, branch_name)
        if not docs:
            return jsonify({"error": "No supported source files found in this repository."}), 400

        file_paths = list({doc.metadata['source'] for doc in docs})
        all_chunks = split_documents(docs)
        if not all_chunks:
            return jsonify({"error": "No indexable code chunks found in this repository."}), 400

        vector_store.create_repository(session_id, repo_name, branch_name)
        vector_store.insert_chunks(session_id, repo_name, branch_name, all_chunks, embed_model)
        ensure_session(session_id)
        folder_structure = build_tree(file_paths, branch_name=branch_name)
        return jsonify({
            "message": "Repo embedded in Supabase",
            "session_id": session_id,
            "folder_structure": folder_structure,
        })
    except Exception as e:  
        try:
            vector_store.delete_session(session_id)
        except Exception:
            pass
        logger.error(f"Error in /clone endpoint: {e}", exc_info=True)
        safe_msg = _sanitize_error(e)
        return jsonify({"error": safe_msg}), 400


@app.route("/status")
def status():
    return jsonify({"message": "Welcome to status page"})


@app.route("/")
def home():
    return "Welcome to home page"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
