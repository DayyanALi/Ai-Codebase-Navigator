import os
from openai import OpenAI


# ---------------------------------------------------------------------------
# Thin wrappers around the OpenAI SDK so the rest of the app can call
# embed_model.embed_documents(texts) / embed_model.embed_query(text)
# and chat_model.invoke(messages) the same way as before.
# ---------------------------------------------------------------------------

class _EmbeddingModel:
    """Drop-in replacement for langchain's OpenAIEmbeddings."""

    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self._client = OpenAI()           # uses OPENAI_API_KEY env var

    # langchain's FAISS wrapper called this; our new retrival.py calls it too
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(input=texts, model=self.model)
        return [d.embedding for d in resp.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class _ChatModel:
    """Drop-in replacement for langchain's ChatOpenAI."""

    def __init__(self, model: str = "gpt-5-nano", temperature: float = 0.0):
        self.model = model
        self.temperature = temperature
        self._client = OpenAI()

    def invoke(self, messages: list[dict]) -> str:
        """Accept a list of {role, content} dicts and return the answer string."""
        kwargs = {
            "model": self.model,
            "messages": messages,
        }
        if "o1" not in self.model and "gpt-5" not in self.model:
            kwargs["temperature"] = self.temperature
            
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content


# --------------- public helpers (same signatures as before) ----------------

def openai_gpt35(temperature: float = 0.0) -> _ChatModel:
    return _ChatModel(model="gpt-3.5-turbo", temperature=temperature)


def openai_gpt4mini(temperature: float = 0.0) -> _ChatModel:
    return _ChatModel(model="gpt-4.1-nano-2025-04-14", temperature=temperature)


def openai_gpt5nano(temperature: float = 0.0) -> _ChatModel:
    return _ChatModel(model="gpt-5-nano", temperature=temperature)


def embedding_model_openai() -> _EmbeddingModel:
    return _EmbeddingModel(model="text-embedding-3-small")


# --------------- tree builder (unchanged) ---------------------------------

def build_tree(paths, branch_name='main'):
    tree = {}
    for path in paths:
        parts = path.split('/')
        if branch_name not in parts:
            continue
        branch_index = parts.index(branch_name)
        relevant_parts = parts[branch_index + 1:]
        current = tree
        for part in relevant_parts:
            current = current.setdefault(part, {})
    return tree
