# Supabase Vector Store Setup

This backend stores repository chunks and Gemini embeddings in Supabase Postgres using `pgvector`.

## 1. Create Supabase Project

Create a project at Supabase, then open the SQL Editor.

## 2. Run Schema

Copy and run all SQL from:

```text
backend/supabase_schema.sql
```

This creates:

- `code_repositories`
- `code_chunks`
- `match_code_chunks(...)`
- a `pgvector` HNSW index for similarity search

## 3. Add Backend Environment Variables

Add these to `backend/.env` locally and to Vercel environment variables:

```env
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
GEMINI_API_KEY="your-gemini-api-key"
ACCESS_TOKEN="your-github-token"
```

Use the Supabase service role key only on the backend. Never expose it in the frontend.

Optional:

```env
SUPABASE_MATCH_COUNT="40"
SUPABASE_INSERT_BATCH_SIZE="100"
MAX_REPO_FILE_BYTES="250000"
```

## 4. Restart Backend

Restart Flask after changing `.env`.

## What Changed

`/clone` now:

1. Fetches GitHub files.
2. Splits files into chunks.
3. Generates Gemini embeddings.
4. Inserts chunks and vectors into Supabase.
5. Returns a `session_id`.

`/query` now:

1. Embeds the question with Gemini.
2. Calls Supabase RPC `match_code_chunks`.
3. Sends the retrieved chunks to Gemini chat.
