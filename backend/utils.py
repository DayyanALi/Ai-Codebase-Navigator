import os
import time
import httpx


# ---------------------------------------------------------------------------
# Gemini wrappers so the rest of the app can call embed_model.embed_documents,
# embed_model.embed_query, and chat_model.invoke the same way as before.
# ---------------------------------------------------------------------------


class _GeminiEmbeddingModel:
    """Drop-in embedding wrapper for Gemini's batchEmbedContents REST API."""

    def __init__(
        self,
        model: str = "gemini-embedding-001",
        output_dimensionality: int = 768,
        batch_size: int = 8,
        max_retries: int = 6,
        batch_delay_seconds: float = 1.0,
    ):
        self.model = model
        self.output_dimensionality = output_dimensionality
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.batch_delay_seconds = batch_delay_seconds
        self._api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self._base_url = "https://generativelanguage.googleapis.com/v1beta"

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not self._api_key:
            raise RuntimeError(
                "Missing Gemini API key. Set GEMINI_API_KEY or GOOGLE_API_KEY in the backend environment."
            )

        url = f"{self._base_url}/models/{self.model}:batchEmbedContents"
        requests = [
            {
                "model": f"models/{self.model}",
                "content": {"parts": [{"text": text or " "}]},
                "outputDimensionality": self.output_dimensionality,
            }
            for text in texts
        ]

        for attempt in range(self.max_retries):
            resp = httpx.post(
                url,
                headers={"x-goog-api-key": self._api_key},
                json={"requests": requests},
                timeout=60,
            )

            if resp.status_code not in (429, 500, 502, 503, 504):
                resp.raise_for_status()
                break

            retry_after = resp.headers.get("retry-after")
            if retry_after and retry_after.isdigit():
                sleep_seconds = float(retry_after)
            else:
                sleep_seconds = min(2 ** attempt, 30)

            if attempt == self.max_retries - 1:
                resp.raise_for_status()

            time.sleep(sleep_seconds)

        embeddings = resp.json().get("embeddings", [])
        return [embedding.get("values", []) for embedding in embeddings]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            embeddings.extend(self._embed_batch(texts[start:start + self.batch_size]))
            if start + self.batch_size < len(texts):
                time.sleep(self.batch_delay_seconds)
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class _GeminiChatModel:
    """Drop-in chat wrapper for Gemini's generateContent REST API."""

    def __init__(
        self,
        model: str = "gemini-2.5-flash-lite",
        temperature: float = 0.0,
        max_retries: int = 5,
    ):
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        self._api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self._base_url = "https://generativelanguage.googleapis.com/v1beta"

    def _to_gemini_contents(self, messages: list[dict]) -> list[dict]:
        contents = []
        for message in messages:
            role = "model" if message.get("role") == "assistant" else "user"
            content = str(message.get("content", ""))
            if content.strip():
                contents.append({
                    "role": role,
                    "parts": [{"text": content}],
                })
        return contents

    def invoke(self, messages: list[dict]) -> str:
        if not self._api_key:
            raise RuntimeError(
                "Missing Gemini API key. Set GEMINI_API_KEY or GOOGLE_API_KEY in the backend environment."
            )

        url = f"{self._base_url}/models/{self.model}:generateContent"
        payload = {
            "contents": self._to_gemini_contents(messages),
            "generationConfig": {
                "temperature": self.temperature,
            },
        }

        for attempt in range(self.max_retries):
            resp = httpx.post(
                url,
                headers={"x-goog-api-key": self._api_key},
                json=payload,
                timeout=60,
            )

            if resp.status_code not in (429, 500, 502, 503, 504):
                resp.raise_for_status()
                break

            retry_after = resp.headers.get("retry-after")
            if retry_after and retry_after.isdigit():
                sleep_seconds = float(retry_after)
            else:
                sleep_seconds = min(2 ** attempt, 20)

            if attempt == self.max_retries - 1:
                resp.raise_for_status()

            time.sleep(sleep_seconds)

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return ""

        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(part.get("text", "") for part in parts).strip()


# --------------- public helpers (same signatures as before) ----------------


def gemini_flash_lite(temperature: float = 0.0) -> _GeminiChatModel:
    return _GeminiChatModel(model="gemini-2.5-flash-lite", temperature=temperature)


def embedding_model_gemini() -> _GeminiEmbeddingModel:
    return _GeminiEmbeddingModel(model="gemini-embedding-001", output_dimensionality=768)


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
