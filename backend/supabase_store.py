import os
from typing import Iterable

import httpx

from retrival import Document


class SupabaseVectorStore:
    """Small Supabase REST client for pgvector-backed code chunks."""

    def __init__(self):
        self.url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
        self.key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_KEY")
            or os.getenv("SUPABASE_ANON_KEY")
        )
        self.chunk_insert_batch_size = int(os.getenv("SUPABASE_INSERT_BATCH_SIZE", "100"))
        self.match_count = int(os.getenv("SUPABASE_MATCH_COUNT", "40"))

    def _headers(self, prefer: str | None = None) -> dict:
        if not self.url or not self.key:
            raise RuntimeError(
                "Missing Supabase config. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
            )

        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _postgrest_url(self, path: str) -> str:
        return f"{self.url}/rest/v1/{path}"

    def _rpc_url(self, function_name: str) -> str:
        return f"{self.url}/rest/v1/rpc/{function_name}"

    def create_repository(self, session_id: str, repo_name: str, branch_name: str) -> None:
        payload = {
            "session_id": session_id,
            "repo_name": repo_name,
            "branch_name": branch_name,
        }
        resp = httpx.post(
            self._postgrest_url("code_repositories"),
            headers=self._headers(prefer="resolution=merge-duplicates,return=minimal"),
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()

    def delete_session(self, session_id: str) -> None:
        resp = httpx.delete(
            self._postgrest_url(f"code_repositories?session_id=eq.{session_id}"),
            headers=self._headers(prefer="return=minimal"),
            timeout=30,
        )
        resp.raise_for_status()

    def insert_chunks(
        self,
        session_id: str,
        repo_name: str,
        branch_name: str,
        chunks: list[Document],
        embed_model,
    ) -> None:
        texts = [chunk.page_content for chunk in chunks]
        embeddings = embed_model.embed_documents(texts)

        for rows in self._build_rows(
            session_id=session_id,
            repo_name=repo_name,
            branch_name=branch_name,
            chunks=chunks,
            embeddings=embeddings,
        ):
            resp = httpx.post(
                self._postgrest_url("code_chunks"),
                headers=self._headers(prefer="return=minimal"),
                json=rows,
                timeout=60,
            )
            resp.raise_for_status()

    def match_chunks(self, session_id: str, query_embedding: list[float]) -> list[Document]:
        resp = httpx.post(
            self._rpc_url("match_code_chunks"),
            headers=self._headers(),
            json={
                "query_embedding": query_embedding,
                "match_session_id": session_id,
                "match_count": self.match_count,
            },
            timeout=60,
        )
        resp.raise_for_status()

        docs = []
        for row in resp.json():
            metadata = row.get("metadata") or {}
            metadata["similarity"] = row.get("similarity")
            docs.append(Document(page_content=row.get("content") or "", metadata=metadata))
        return docs

    def _build_rows(
        self,
        *,
        session_id: str,
        repo_name: str,
        branch_name: str,
        chunks: list[Document],
        embeddings: list[list[float]],
    ) -> Iterable[list[dict]]:
        batch = []
        for chunk, embedding in zip(chunks, embeddings):
            metadata = chunk.metadata or {}
            batch.append({
                "session_id": session_id,
                "repo_name": repo_name,
                "branch_name": branch_name,
                "path": metadata.get("path"),
                "language": metadata.get("language"),
                "symbol": metadata.get("symbol"),
                "kind": metadata.get("kind"),
                "start_line": metadata.get("start_line"),
                "end_line": metadata.get("end_line"),
                "content": chunk.page_content,
                "embedding": embedding,
                "metadata": metadata,
            })

            if len(batch) >= self.chunk_insert_batch_size:
                yield batch
                batch = []

        if batch:
            yield batch


def build_context_block(docs: list[Document], token_budget_chars: int = 8000) -> str:
    blocks = []
    used = 0

    for doc in docs:
        text = doc.page_content or ""
        if used + len(text) > token_budget_chars:
            break

        metadata = doc.metadata or {}
        path = metadata.get("path")
        start_line = metadata.get("start_line")
        end_line = metadata.get("end_line")
        language = metadata.get("language", "text")
        header = f"# {path}:{start_line}-{end_line}"
        blocks.append(f"```{language}\n{header}\n{text}\n```")
        used += len(text)

    return "\n\n".join(blocks)
