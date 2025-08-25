# AI Codebase Navigator & Explainer

A simple web-based tool that lets you point at any public GitHub repository, automatically clone and index its source code into a FAISS vector store, and then interactively ask natural-language questions about the code. Powered by Flask, React.js, LangChain, OpenAI Embeddings, and FAISS.

---

## 🚀 Features

- **One-click clone & index** of any public GitHub repo  
- **Multi-language support**: Python, JavaScript/TypeScript, Java, C++, Go, Rust, etc.  
- **Semantic search** via FAISS + OpenAI’s `text-embedding-3-small`  
- **Conversational Q&A** with follow-up handling (uses LangChain’s `ConversationalRetrievalChain` + `ConversationBufferMemory`)  
- **Session isolation**: each client gets its own vector store, in-memory memory, and temp cleanup  

---

## 📁 Repository Structure
``` plaintext
    Ai-Codebase-Navigator/
    ├── backend/ # Flask API + indexing & retrieval logic
    │ ├── server.py # main application
    │ ├── template.py # prompt templates
    │ └── requirements.txt
    ├── frontend/ # React.js client
    │ ├── src/
    │ ├── public/
    │ └── package.json
    ├── .gitignore
    └── README.md  # this file
```

## ⚙️ Installation & Setup

### 1. Clone this repo

```bash
git clone https://github.com/DayyanAli/Ai-Codebase-Navigator.git
cd Ai-Codebase-Navigator
```

## 2. Bckend
``` bash
    cd backend
    python3 -m venv .venv
    source .venv/bin/activate        # macOS/Linux
    .\.venv\Scripts\activate         # Windows PowerShell

    pip install -r requirements.txt

    # Create .env with your OpenAI API key:
    echo "OPENAI_API_KEY=sk-…" > .env

    # Run the Flask server
    python server.py
```

3. Frontend
- Open a new terminal:

``` bash
cd frontend
npm install
npm run dev
```

## 🏃‍♂️ Usage
- Open the React app in your browser.

- Paste any public GitHub repo name (e.g. rattle99/QtNotepad) and the branch and then click Add.

- Wait for “Repo Added” – the backend clones, chunks, embeds, and indexes the code.

- Ask a natural-language question (e.g. “Explain the main.cpp file”).