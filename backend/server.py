import os
import stat
from flask import Flask, request, jsonify
from flask_cors import CORS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import GithubFileLoader
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage 
# from langchain.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
from utils import embedding_model_openai, build_tree, openai_gpt4mini, openai_gpt5nano
from template import chat_model_template, rephrase_question_template
from retrival import build_vector_db, split_documents, retrieve_context

load_dotenv()
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
    "h":"h"
}

def store_vector_store(session_id, vector_store):
    Clients[session_id] = {
        "vector_store": vector_store,
        "history": []
    }

def retrieve_vector_store(session_id):
    return Clients[session_id]["vector_store"]

def get_rephrased_question(question: str, chat_history, chat_model):
    history = chat_history
    prompt = PromptTemplate(
        template=rephrase_question_template,
        input_variables=["history", "question"]
    )
    parser = StrOutputParser()
    chain = prompt | chat_model | parser
    return chain.invoke({"history": history, "question": question})

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
        parser = StrOutputParser()
        combined_result = retrieve_context(vector_store, rephrased_question)
        prompt = PromptTemplate(
            template=chat_model_template,
            input_variables=["question", "context"]
        )
        chain = prompt | chat_model | parser
        answer = chain.invoke({"question": question, "context": combined_result})
        Clients[session_id]["history"].append(HumanMessage(content=rephrased_question))
        Clients[session_id]["history"].append(AIMessage(content=answer))
        return jsonify({"answer": answer})
    except Exception as e:
        print("error",e)
        return jsonify({"error": "Session not found"}), 400

@app.route('/clone', methods=["POST"])
def clone_repo():
    global session_counter
    data = request.get_json()
    repo_name = data["repo_name"]
    branch_name = data["branch_name"]
    try:
        loader = GithubFileLoader(
            repo=repo_name,
            branch=branch_name,
            access_token=os.environ["ACCESS_TOKEN"],
            file_filter=lambda file_path: file_path.endswith(tuple(EXT_TO_LANG.keys()))
        )
        docs = loader.load()
        file_paths = list({doc.metadata['source'] for doc in docs})
        all_chunks = split_documents(docs)
        vector_store = build_vector_db(all_chunks, embed_model)
        session_id = session_counter
        store_vector_store(session_id, vector_store=vector_store)
        session_counter+=1
        folder_structure = build_tree(file_paths, branch_name=branch_name)
        return jsonify({"message": "Repo embedded in memory", "session_id": session_id,"folder_structure": folder_structure})
    except Exception as e:
        print("error", e)
        return jsonify({"error": str(e)})


@app.route("/status")
def status():
    return jsonify({"message": "Welcome to status page"})

@app.route("/")
def home():
    return "Welcome to home page"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
