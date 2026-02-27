import logging
import os
import base64

import httpx
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from utils import embedding_model_openai, build_tree, openai_gpt5nano
from template import chat_model_template, rephrase_question_template
from retrival import build_vector_db, split_documents, retrieve_context, Document

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
session_counter = 1
Clients = {}
embed_model = embedding_model_openai()
chat_model = openai_gpt5nano()

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

def store_vector_store(session_id, vector_store):
    Clients[session_id] = {
        "vector_store": vector_store,
        "history": []
    }


def retrieve_vector_store(session_id):
    return Clients[session_id]["vector_store"]


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
    
    # OpenAI quota/billing errors
    if "insufficient_quota" in err_str or "exceeded your current quota" in err_str:
        return "OpenAI API quota exceeded. Please check your API billing details."
    elif "incorrect api key" in err_str or "invalid api key" in err_str:
        return "Invalid OpenAI API key configured on the server."
        
    # GitHub HTTP errors
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return "Repository or branch not found. Please verify the URL."
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
        chat_history = Clients[session_id]["history"]
        vector_store = retrieve_vector_store(session_id=session_id)
        rephrased_question = get_rephrased_question(question, chat_history, chat_model)
        combined_docs, combined_result = retrieve_context(
            vector_store, rephrased_question, embed_model=embed_model
        )
        answer = answer_question(question, combined_result, chat_model)
        Clients[session_id]["history"].append({"role": "user", "content": rephrased_question})
        Clients[session_id]["history"].append({"role": "assistant", "content": answer})
        return jsonify({"answer": answer})
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

    session = Clients.pop(session_id, None)
    if session is None:
        return jsonify({"message": "already evicted or not found", "session_id": session_id}), 200

    try:
        vs = session.get("vector_store")
        if isinstance(vs, dict):
            vs["vector"] = None
            vs["bm25"] = None
    except Exception:
        pass

    return jsonify({"message": "session evicted", "session_id": session_id}), 200


@app.route('/clone', methods=["POST"])
def clone_repo():
    global session_counter
    data = request.get_json()
    repo_name = data["repo_name"]
    branch_name = data["branch_name"]
    try:
        docs = _fetch_repo_files(repo_name, branch_name)
        file_paths = list({doc.metadata['source'] for doc in docs})
        all_chunks = split_documents(docs)
        vector_store = build_vector_db(all_chunks, embed_model)
        session_id = session_counter
        store_vector_store(session_id, vector_store=vector_store)
        session_counter += 1
        folder_structure = build_tree(file_paths, branch_name=branch_name)
        return jsonify({
            "message": "Repo embedded in memory",
            "session_id": session_id,
            "folder_structure": folder_structure,
        })
    except Exception as e:  
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
