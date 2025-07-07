import os
import stat
import shutil
from flask import Flask, request, jsonify
from flask_cors import CORS
from git import Repo
from langchain_community.document_loaders import DirectoryLoader
from langchain.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage 
from langchain.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv


load_dotenv()
app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "*"}}) 

session_counter = 1

Clients = {}

rephrase_system = """\
You are a question-rewriting assistant. Your job is to turn a possibly ambiguous follow-up question into a fully self-contained, specific question. Always include:

- The exact filename (e.g. “main.py”)  
- If you know it, the line number or range (e.g. “lines 10–15”)  
- The code element name (e.g. “while loop”)  

If the user’s question is already self-contained, return it verbatim.  

Now apply this logic to the conversation below.

Conversation history:  
{history}

User’s latest question:  
{question}

Respond with only the rewritten question—no extra commentary.
"""

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
}

def _on_rm_error(func, path, exc_info):
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    else:
        raise

def get_rephrased_question(question: str, chat_history, chat_model):
    history = chat_history
    prompt = PromptTemplate(
        template=rephrase_system,
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
        chat_model = ChatOpenAI(model="gpt-3.5-turbo")
        rephrased_question = get_rephrased_question(question, chat_history, chat_model)
        parser = StrOutputParser()

        vector_store = Clients[session_id]["vector_store"]
        retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 2})

        retrieved_code = retriever.invoke(rephrased_question)
        combined_result = "\n\n".join(code.page_content for code in retrieved_code)
        
        prompt = PromptTemplate(
            template="""
                You are a code explainer assistant.  Given some code snippets and a question, you will:
                1. Read the code carefully (it may come from different files).
                2. Explain in plain English how the code works.
                3. Directly answer the user’s question, pointing out relevant lines if helpful.
                4. When writing the answer dont say words such as based on the code snippets, just explain the code.
                5. If the code snippet does not answer the question simply say "Could not find an answer".
                
                The Context Code snippets:
                {context}
                
                The question of the user:
                {question}
            """,
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

@app.route('/clone',methods=["POST"])
def clone_repo():
    global session_counter
    print("session counter", session_counter)
    data = request.get_json()
    try:
        cwd = os.getcwd()
        base = os.path.join(cwd, "sessions")
        os.makedirs(base, exist_ok=True)              # ensure the root exists
        session_id = str(session_counter)
        session_counter += 1
        session_dir = os.path.join(base, session_id)
        repo_dir    = os.path.join(session_dir, "repo")
        index_dir   = os.path.join(session_dir, "index")

        os.makedirs(repo_dir, exist_ok=True)
        os.makedirs(index_dir, exist_ok=True)
        
        repo_url = data["repo_url"]
        Repo.clone_from(repo_url, repo_dir)
        # Load code files
        loader = DirectoryLoader(
            repo_dir,
            glob="**/*",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
        )
        docs = loader.load()
        embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")
        all_chunks = []
        for doc in docs:
            ext = doc.metadata["source"].split(".")[-1]
            lang = EXT_TO_LANG.get(ext)
            if lang:
                splitter = RecursiveCharacterTextSplitter.from_language(lang)
            else:
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=100,
                    chunk_overlap=20,
                )
            chunks = splitter.split_documents([doc])
            all_chunks.extend(chunks)
            
        vector_store = FAISS.from_documents(all_chunks, embedding_model)
        vector_store.save_local(index_dir)

        Clients[session_id] = {"history": [], "vector_store": vector_store}
        shutil.rmtree(session_dir, onerror=_on_rm_error)
        return jsonify({"message": "Repo Added", "session_id": session_id})
    except Exception as e:
        print("error",e)
        return jsonify({"error": str(e)})

@app.route("/status")
def status():
    return jsonify({"message": "Welcome to status page"})

@app.route("/")
def home():
    return "Welcome to home page"

if __name__ == "__main__":
    app.run(debug=True)
