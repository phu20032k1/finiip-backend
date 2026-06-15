-- Finiip V101/V60-V66 Supabase Admin RAG schema
-- Run in Supabase SQL Editor. Keep service_role key ONLY on the backend.
-- These table names intentionally avoid the older V67/V68 rag_documents schema.

create table if not exists public.admin_rag_documents (
  document_id text primary key,
  workspace_id text not null default 'default',
  title text not null,
  source_type text not null default 'knowledge',
  content_sha256 text,
  metadata jsonb not null default '{}'::jsonb,
  status text not null default 'active',
  chunk_count integer not null default 0,
  char_count integer not null default 0,
  storage_bucket text,
  storage_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.admin_rag_document_chunks (
  chunk_id text primary key,
  document_id text not null references public.admin_rag_documents(document_id) on delete cascade,
  workspace_id text not null default 'default',
  title text not null,
  source_type text not null default 'knowledge',
  section integer,
  chunk_no integer,
  heading text,
  content text not null,
  tokens text[] not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists public.admin_rag_audit_logs (
  audit_id bigint generated always as identity primary key,
  event_type text not null,
  workspace_id text,
  document_id text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- V60: Evaluation/Test Center
create table if not exists public.admin_rag_eval_results (
  eval_id bigint generated always as identity primary key,
  workspace_id text not null default 'default',
  question text not null,
  expected_answer text,
  expected_source text,
  actual_answer text,
  score numeric not null default 0,
  passed boolean not null default false,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- V66: Persistent memory for Admin RAG conversations
create table if not exists public.admin_rag_chat_messages (
  message_id bigint generated always as identity primary key,
  conversation_id text not null default 'admin',
  workspace_id text not null default 'default',
  role text not null,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_admin_rag_documents_workspace_status
  on public.admin_rag_documents(workspace_id, status, updated_at desc);

create index if not exists idx_admin_rag_document_chunks_workspace_doc
  on public.admin_rag_document_chunks(workspace_id, document_id, chunk_no);

create index if not exists idx_admin_rag_document_chunks_tokens_gin
  on public.admin_rag_document_chunks using gin(tokens);

create index if not exists idx_admin_rag_eval_results_workspace_created
  on public.admin_rag_eval_results(workspace_id, created_at desc);

create index if not exists idx_admin_rag_chat_messages_workspace_conversation_created
  on public.admin_rag_chat_messages(workspace_id, conversation_id, created_at desc);

-- Storage bucket: create manually in Supabase dashboard if it does not exist:
-- Bucket name: rag-knowledge or the value of SUPABASE_RAG_BUCKET. Public: false.
-- If RLS is enabled, keep writes through backend service_role only.
