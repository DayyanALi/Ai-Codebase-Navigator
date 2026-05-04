create extension if not exists vector with schema extensions;

create table if not exists public.code_repositories (
  session_id text primary key,
  repo_name text not null,
  branch_name text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.code_chunks (
  id bigserial primary key,
  session_id text not null references public.code_repositories(session_id) on delete cascade,
  repo_name text not null,
  branch_name text not null,
  path text,
  language text,
  symbol text,
  kind text,
  start_line integer,
  end_line integer,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  embedding extensions.vector(768) not null,
  created_at timestamptz not null default now()
);

create index if not exists code_chunks_session_id_idx
  on public.code_chunks(session_id);

create index if not exists code_chunks_path_idx
  on public.code_chunks(path);

create index if not exists code_chunks_embedding_hnsw_idx
  on public.code_chunks
  using hnsw (embedding extensions.vector_cosine_ops);

create or replace function public.match_code_chunks(
  query_embedding extensions.vector(768),
  match_session_id text,
  match_count int default 40
)
returns table (
  id bigint,
  content text,
  metadata jsonb,
  similarity float
)
language sql
stable
as $$
  select
    code_chunks.id,
    code_chunks.content,
    jsonb_build_object(
      'path', code_chunks.path,
      'language', code_chunks.language,
      'symbol', code_chunks.symbol,
      'kind', code_chunks.kind,
      'start_line', code_chunks.start_line,
      'end_line', code_chunks.end_line,
      'repo_name', code_chunks.repo_name,
      'branch_name', code_chunks.branch_name
    ) || code_chunks.metadata as metadata,
    1 - (code_chunks.embedding <=> query_embedding) as similarity
  from public.code_chunks
  where code_chunks.session_id = match_session_id
  order by code_chunks.embedding <=> query_embedding
  limit least(match_count, 200);
$$;

grant usage on schema public to anon, authenticated, service_role;
grant usage on schema extensions to anon, authenticated, service_role;

grant select, insert, update, delete on public.code_repositories to service_role;
grant select, insert, update, delete on public.code_chunks to service_role;
grant usage, select on sequence public.code_chunks_id_seq to service_role;
grant execute on function public.match_code_chunks(extensions.vector(768), text, int) to service_role;

notify pgrst, 'reload schema';
