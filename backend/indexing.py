import os
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever

def build_indexes(docs, embed_model, persist_dir="indexes", index_name="repo"):
    # VECTOR (FAISS)
    vector_store = FAISS.from_documents(docs, embed_model)
    os.makedirs(persist_dir, exist_ok=True)
    vector_store.save_local(os.path.join(persist_dir, index_name))

    # BM25 (lexical) – excellent for identifiers/error messages
    bm25 = BM25Retriever.from_documents(docs)
    bm25.k = 25  # widen lexical recall a bit

    return vector_store, bm25
