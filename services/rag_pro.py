"""V72-V75 Pro RAG backend utilities.

Adds production-style RAG features without frontend:
- Structure-aware chunking for Vietnamese legal/accounting docs.
- Hybrid retrieval: pgvector + lexical scoring + phrase boosts + simple rerank.
- Batch upload helpers and audit logging.
- Quality evaluation endpoint helpers.

This module intentionally depends only on optional packages already listed for the project.
If Supabase/Postgres is not configured, it falls back to the local JSON store in rag_v66_v67.
"""
from __future__ import annotations

import json
import math
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import rag_v66_v67 as base

AUDIT_FILE = base.DATA_DIR / "rag_audit_log.jsonl"
DEFAULT_PRO_CHUNK_SIZE = int(os.getenv("RAG_PRO_CHUNK_SIZE", "1600"))
DEFAULT_PRO_OVERLAP = int(os.getenv("RAG_PRO_OVERLAP", "220"))
MAX_BATCH_FILES = int(os.getenv("RAG_MAX_BATCH_FILES", "12"))

HEADING_PATTERNS = [
    re.compile(r"^\s*(PHẦN|CHƯƠNG|MỤC|TIỂU MỤC)\s+([IVXLCDM0-9]+|[A-Z])\b.*", re.I),
    re.compile(r"^\s*Điều\s+\d+[a-zA-Z]?\.?\s+.*", re.I),
    re.compile(r"^\s*Khoản\s+\d+[a-zA-Z]?\.?\s+.*", re.I),
    re.compile(r"^\s*[0-9]+[.)]\s+.*"),
    re.compile(r"^\s*[a-zđ][)]\s+.*", re.I),
    re.compile(r"^\s*(Appendix|Annex|Article|Section|Chapter)\b.*", re.I),
]


def audit_log(action: str, status: str = "ok", **payload: Any) -> Dict[str, Any]:
    event = {
        "id": str(uuid.uuid4()),
        "ts": base.now_iso(),
        "action": action,
        "status": status,
        **payload,
    }
    try:
        with AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return event


def list_audit_logs(limit: int = 100, action: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
    if not AUDIT_FILE.exists():
        return {"items": [], "total_loaded": 0}
    rows: List[Dict[str, Any]] = []
    with AUDIT_FILE.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                item = json.loads(line)
            except Exception:
                continue
            if action and item.get("action") != action:
                continue
            if status and item.get("status") != status:
                continue
            rows.append(item)
    rows = rows[-max(1, min(limit, 1000)):]
    rows.reverse()
    return {"items": rows, "total_loaded": len(rows)}


def is_heading(line: str) -> bool:
    stripped = (line or "").strip()
    if not stripped:
        return False
    if len(stripped) <= 120 and stripped.isupper() and len(stripped.split()) >= 2:
        return True
    return any(p.match(stripped) for p in HEADING_PATTERNS)


def detect_heading_level(line: str) -> int:
    s = (line or "").strip().lower()
    if s.startswith(("phần", "chương", "chapter")):
        return 1
    if s.startswith(("mục", "section")):
        return 2
    if s.startswith(("điều", "article")):
        return 3
    if s.startswith("khoản") or re.match(r"^[0-9]+[.)]", s):
        return 4
    if re.match(r"^[a-zđ][)]", s):
        return 5
    return 6


def normalize_document_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    # Remove common PDF page noise without deleting real legal numbering.
    text = re.sub(r"\n\s*Trang\s+\d+\s*/\s*\d+\s*\n", "\n", text, flags=re.I)
    return text.strip()


@dataclass
class SectionBlock:
    heading: str
    path: List[str]
    text: str


def split_into_structure_blocks(text: str) -> List[SectionBlock]:
    cleaned = normalize_document_text(text)
    lines = cleaned.splitlines()
    current_path: List[Tuple[int, str]] = []
    blocks: List[SectionBlock] = []
    current_heading = "Mở đầu"
    current_lines: List[str] = []

    def flush() -> None:
        nonlocal current_lines, current_heading
        body = "\n".join(current_lines).strip()
        if body:
            blocks.append(SectionBlock(
                heading=current_heading,
                path=[h for _, h in current_path] or [current_heading],
                text=body,
            ))
        current_lines = []

    for raw in lines:
        line = raw.strip()
        if is_heading(line):
            if current_lines:
                flush()
            level = detect_heading_level(line)
            current_path = [(lvl, h) for lvl, h in current_path if lvl < level]
            current_path.append((level, line))
            current_heading = line
            current_lines.append(line)
        else:
            current_lines.append(raw)
    flush()

    if not blocks and cleaned:
        blocks.append(SectionBlock(heading="Nội dung", path=["Nội dung"], text=cleaned))
    return blocks


def smart_chunk_text(text: str, chunk_size: int = DEFAULT_PRO_CHUNK_SIZE, overlap: int = DEFAULT_PRO_OVERLAP) -> List[Dict[str, Any]]:
    """Return structure-aware chunks with metadata.

    Keeps legal headings in metadata and avoids splitting across Điều/Khoản unless needed.
    """
    blocks = split_into_structure_blocks(text)
    chunks: List[Dict[str, Any]] = []
    for block in blocks:
        prefix = " > ".join(block.path[-4:])
        content = block.text.strip()
        if len(content) <= chunk_size:
            chunks.append({"content": content, "heading": block.heading, "path": block.path, "char_start": None, "char_end": None})
            continue
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
        current = ""
        start_idx = 0
        for para in paragraphs:
            candidate = (current + "\n\n" + para).strip() if current else para
            if len(candidate) <= chunk_size:
                current = candidate
                continue
            if current:
                chunks.append({"content": current, "heading": block.heading, "path": block.path, "char_start": start_idx, "char_end": start_idx + len(current)})
                tail = current[-overlap:] if overlap and len(current) > overlap else ""
                current = (tail + "\n\n" + para).strip() if tail else para
                start_idx += max(0, len(current) - overlap)
            else:
                step = max(1, chunk_size - overlap)
                for pos in range(0, len(para), step):
                    part = para[pos:pos + chunk_size].strip()
                    if part:
                        chunks.append({"content": part, "heading": block.heading, "path": block.path, "char_start": pos, "char_end": pos + len(part)})
                current = ""
        if current:
            chunks.append({"content": current, "heading": block.heading, "path": block.path, "char_start": start_idx, "char_end": start_idx + len(current)})
    # Remove tiny duplicate/noisy chunks.
    seen = set()
    final: List[Dict[str, Any]] = []
    for ch in chunks:
        c = re.sub(r"\s+", " ", ch["content"]).strip()
        key = c[:300]
        if len(c) < 30 or key in seen:
            continue
        seen.add(key)
        ch["content"] = c
        final.append(ch)
    return final


def chunk_strings_with_metadata(text: str, chunk_size: int = DEFAULT_PRO_CHUNK_SIZE, overlap: int = DEFAULT_PRO_OVERLAP) -> Tuple[List[str], List[Dict[str, Any]]]:
    smart = smart_chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    return [x["content"] for x in smart], [{k: v for k, v in x.items() if k != "content"} for x in smart]


def _pg_rows(sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
    import psycopg2.extras
    with base._pg_conn() as conn:  # type: ignore[attr-defined]
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]


def _execute(sql: str, params: Sequence[Any] = ()) -> None:
    with base._pg_conn() as conn:  # type: ignore[attr-defined]
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()


def ensure_pro_schema() -> Dict[str, Any]:
    base_schema = base.ensure_supabase_rag_schema()
    if not base.supabase_enabled():
        return {"ok": True, "enabled": False, "base_schema": base_schema, "message": "Local mode only"}
    try:
        with base._pg_conn() as conn:  # type: ignore[attr-defined]
            with conn.cursor() as cur:
                cur.execute("alter table rag_documents add column if not exists tags text[] default '{}'::text[]")
                cur.execute("alter table rag_documents add column if not exists metadata jsonb default '{}'::jsonb")
                cur.execute("alter table rag_documents add column if not exists status text default 'active'")
                cur.execute("alter table rag_documents add column if not exists content_sha256 text")
                cur.execute("alter table rag_chunks add column if not exists lexical tsvector")
                cur.execute("alter table rag_chunks add column if not exists heading text")
                cur.execute("alter table rag_chunks add column if not exists section_path text[] default '{}'::text[]")
                cur.execute("update rag_chunks set lexical = to_tsvector('simple', coalesce(content,'')) where lexical is null")
                cur.execute("create index if not exists rag_chunks_lexical_idx on rag_chunks using gin(lexical)")
                cur.execute("create index if not exists rag_documents_status_idx on rag_documents(status)")
                cur.execute("""
                    create table if not exists rag_audit_logs (
                      id uuid primary key default gen_random_uuid(),
                      action text not null,
                      status text not null,
                      payload jsonb default '{}'::jsonb,
                      created_at timestamptz default now()
                    )
                """)
            conn.commit()
        return {"ok": True, "enabled": True, "base_schema": base_schema}
    except Exception as exc:
        return {"ok": False, "enabled": True, "error": str(exc), "base_schema": base_schema}


def save_pro_document(
    *,
    title: str,
    content: str,
    filename: str,
    category: str = "general",
    document_type: str = "document",
    source: str = "admin_upload",
    tags: Optional[List[str]] = None,
    storage_path: Optional[str] = None,
    uploaded_by: str = "admin",
    chunk_size: int = DEFAULT_PRO_CHUNK_SIZE,
    overlap: int = DEFAULT_PRO_OVERLAP,
) -> Dict[str, Any]:
    chunks, metas = chunk_strings_with_metadata(content, chunk_size=chunk_size, overlap=overlap)
    sha = base.hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()
    audit_log("rag_pro_upload_start", title=title, filename=filename, chunks=len(chunks), category=category)

    # Always save local store for dev fallback.
    local = base.save_local_rag_document(
        title=title,
        content=content,
        filename=filename,
        category=category,
        document_type=document_type,
        source=source,
        tags=tags or [],
        storage_path=storage_path,
    )

    if not base.supabase_enabled():
        audit_log("rag_pro_upload_done", status="local_only", title=title, chunks=len(chunks))
        return {"local": local["document"], "supabase": {"enabled": False}, "chunks": len(chunks), "chunking": "structure_aware"}

    schema = ensure_pro_schema()
    if not schema.get("ok"):
        audit_log("rag_pro_upload_failed", status="error", title=title, error=schema.get("error"))
        return {"local": local["document"], "supabase": {"enabled": True, "saved": False, "schema": schema}, "chunks": len(chunks)}

    try:
        import psycopg2.extras
        provider = base.embedding_provider()
        with base._pg_conn() as conn:  # type: ignore[attr-defined]
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    insert into rag_documents
                    (title, document_type, category, source, storage_path, uploaded_by, updated_at, tags, metadata, status, content_sha256)
                    values (%s,%s,%s,%s,%s,%s,now(),%s,%s::jsonb,'active',%s)
                    returning id
                    """,
                    (
                        title, document_type, category, source, storage_path or filename, uploaded_by,
                        tags or [], json.dumps({"filename": filename, "chunking": "structure_aware", "chunk_size": chunk_size, "overlap": overlap}, ensure_ascii=False), sha,
                    ),
                )
                document_id = str(cur.fetchone()["id"])
                for i, chunk in enumerate(chunks):
                    meta = {
                        "filename": filename,
                        "category": category,
                        "document_type": document_type,
                        "source": source,
                        "tags": tags or [],
                        "embedding_provider": provider["provider"],
                        "embedding_model": provider["model"],
                        **metas[i],
                    }
                    emb = base.embedding_literal(title + "\n" + chunk)  # type: ignore[attr-defined]
                    cur.execute(
                        """
                        insert into rag_chunks
                        (document_id, chunk_index, content, metadata, embedding, lexical, heading, section_path)
                        values (%s,%s,%s,%s::jsonb,%s::vector,to_tsvector('simple', %s),%s,%s)
                        """,
                        (document_id, i, chunk, json.dumps(meta, ensure_ascii=False), emb, chunk, meta.get("heading"), meta.get("path") or []),
                    )
            conn.commit()
        audit_log("rag_pro_upload_done", title=title, document_id=document_id, chunks=len(chunks), embedding=provider)
        return {"local": local["document"], "supabase": {"enabled": True, "saved": True, "document_id": document_id}, "chunks": len(chunks), "chunking": "structure_aware", "embedding": provider}
    except Exception as exc:
        audit_log("rag_pro_upload_failed", status="error", title=title, error=str(exc))
        return {"local": local["document"], "supabase": {"enabled": True, "saved": False, "error": str(exc)}, "chunks": len(chunks)}


def lexical_bonus(question: str, content: str, title: str = "", heading: str = "") -> float:
    score = base.keyword_score(question, f"{title}\n{heading}\n{content}")
    nq = base.normalize_text(question)
    nc = base.normalize_text(f"{title} {heading} {content}")
    # Boost legal/accounting references.
    for pat in [r"điều\s+\d+", r"khoản\s+\d+", r"thông tư\s+\d+", r"nghị định\s+\d+", r"tài khoản\s+\d+", r"tk\s*\d+"]:
        for m in re.findall(pat, nq):
            if m in nc:
                score += 5.0
    # Consecutive token proximity.
    q_tokens = base.tokenize(question)
    for n in (4, 3, 2):
        for i in range(0, max(0, len(q_tokens) - n + 1)):
            phrase = " ".join(q_tokens[i:i+n])
            if phrase and phrase in nc:
                score += n * 0.8
    return round(score, 4)


def _vector_distance_score(distance: Any) -> float:
    try:
        d = float(distance)
        return max(0.0, 1.0 - d)
    except Exception:
        return 0.0


def hybrid_search(question: str, limit: int = 8, category: Optional[str] = None, document_type: Optional[str] = None, tags: Optional[List[str]] = None) -> Dict[str, Any]:
    start = time.time()
    tags = tags or []
    if not base.supabase_enabled():
        local = base.search_local_rag(question, limit=limit, category=category)
        local.update({"mode": "local_keyword", "latency_ms": int((time.time() - start) * 1000)})
        return local

    try:
        ensure_pro_schema()
        q_emb = base.embedding_literal(question)  # type: ignore[attr-defined]
        rows = _pg_rows(
            """
            select c.id as chunk_id, c.document_id, c.chunk_index, c.content, c.metadata,
                   c.heading, c.section_path, d.title, d.source, d.category, d.document_type,
                   (c.embedding <=> %s::vector) as vector_distance
            from rag_chunks c
            join rag_documents d on d.id = c.document_id
            where d.status = 'active'
              and (%s is null or d.category = %s)
              and (%s is null or d.document_type = %s)
              and (%s::text[] = '{}'::text[] or d.tags && %s::text[] or (c.metadata->'tags') ?| %s)
            order by c.embedding <=> %s::vector
            limit 350
            """,
            (q_emb, category, category, document_type, document_type, tags, tags, tags, q_emb),
        )
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for row in rows:
            lex = lexical_bonus(question, row.get("content") or "", row.get("title") or "", row.get("heading") or "")
            vec = _vector_distance_score(row.get("vector_distance")) * 10.0
            heading_boost = 1.5 if row.get("heading") and lexical_bonus(question, row.get("heading") or "") > 0 else 0.0
            final = (0.55 * lex) + (0.35 * vec) + heading_boost
            if final > 0:
                row["lexical_score"] = lex
                row["vector_score"] = round(vec, 4)
                row["score"] = round(final, 4)
                scored.append((final, row))
        scored.sort(key=lambda x: x[0], reverse=True)

        # Diversity: avoid returning too many adjacent chunks from same doc.
        selected: List[Dict[str, Any]] = []
        per_doc = {}
        for _, row in scored:
            doc_id = str(row.get("document_id"))
            if per_doc.get(doc_id, 0) >= 4 and len(selected) < limit:
                continue
            selected.append(row)
            per_doc[doc_id] = per_doc.get(doc_id, 0) + 1
            if len(selected) >= limit:
                break

        results = []
        for row in selected:
            results.append({
                "score": row.get("score"),
                "lexical_score": row.get("lexical_score"),
                "vector_score": row.get("vector_score"),
                "document_id": str(row.get("document_id")),
                "chunk_id": str(row.get("chunk_id")),
                "chunk_index": row.get("chunk_index"),
                "title": row.get("title"),
                "source": row.get("source"),
                "category": row.get("category"),
                "document_type": row.get("document_type"),
                "heading": row.get("heading"),
                "section_path": row.get("section_path"),
                "content": row.get("content"),
            })
        audit_log("rag_pro_search", question=question[:300], matched=len(results), category=category, document_type=document_type)
        return {"enabled": True, "mode": "hybrid_vector_keyword_rerank", "question": question, "matched": len(results), "results": results, "latency_ms": int((time.time() - start) * 1000), "answer": base.build_answer_from_chunks(question, results)}
    except Exception as exc:
        audit_log("rag_pro_search_failed", status="error", question=question[:300], error=str(exc))
        fallback = base.search_supabase_rag(question, limit=limit, category=category)
        fallback.update({"mode": "fallback_v67", "pro_error": str(exc), "latency_ms": int((time.time() - start) * 1000)})
        return fallback


def build_cited_answer(question: str, results: List[Dict[str, Any]], style: str = "detailed") -> str:
    if not results:
        return "Chưa tìm thấy căn cứ phù hợp trong kho RAG. Hãy upload tài liệu liên quan hoặc kiểm tra category/tag."
    style = (style or "detailed").lower()
    max_chars = 900 if style == "short" else 1500
    lines = ["## Trả lời dựa trên tài liệu đã upload", ""]
    if style != "short":
        lines.append("### Căn cứ tìm được")
        for i, r in enumerate(results[:6], 1):
            quote = re.sub(r"\s+", " ", r.get("content") or "").strip()[:max_chars]
            lines.append(f"[{i}] **{r.get('title') or 'Tài liệu'}** — {r.get('heading') or 'chunk ' + str(r.get('chunk_index'))}: {quote}")
        lines.append("")
    lines.append("### Kết luận gợi ý")
    top = results[:3]
    summary_bits = []
    for r in top:
        content = re.sub(r"\s+", " ", r.get("content") or "").strip()
        if content:
            summary_bits.append(content[:420])
    lines.append("Dựa trên các đoạn liên quan nhất, cần đối chiếu các căn cứ sau rồi áp dụng theo đúng bối cảnh nghiệp vụ. Các nguồn chính nằm ở phần trích dẫn bên dưới.")
    for i, bit in enumerate(summary_bits, 1):
        lines.append(f"- Ý {i}: {bit}{'...' if len(bit) >= 420 else ''}")
    lines.append("")
    lines.append("### Nguồn")
    for i, r in enumerate(results[:8], 1):
        path = " > ".join(r.get("section_path") or []) if r.get("section_path") else r.get("heading")
        lines.append(f"- [{i}] {r.get('title')} | {path or 'chunk ' + str(r.get('chunk_index'))} | score={r.get('score')}")
    lines.append("")
    lines.append("Lưu ý: câu trả lời là kết quả RAG theo tài liệu đã upload; với luật/thông tư cần kiểm tra hiệu lực văn bản trước khi dùng chính thức.")
    return "\n".join(lines)


def answer_pro(question: str, limit: int = 8, category: Optional[str] = None, document_type: Optional[str] = None, tags: Optional[List[str]] = None, style: str = "detailed", use_llm: bool = False) -> Dict[str, Any]:
    search = hybrid_search(question, limit=limit, category=category, document_type=document_type, tags=tags)
    results = search.get("results", [])
    if use_llm and os.getenv("OPENAI_API_KEY") and results:
        # Reuse base answer function when available, but with hybrid results.
        try:
            base_answer = base.answer_rag_question(question=question, limit=limit, category=category, style=style, use_llm=True)
            if base_answer.get("answer"):
                base_answer["retrieval"] = search
                base_answer["mode"] = "pro_hybrid_plus_llm"
                audit_log("rag_pro_answer", question=question[:300], matched=len(results), use_llm=True)
                return base_answer
        except Exception:
            pass
    answer = build_cited_answer(question, results, style=style)
    audit_log("rag_pro_answer", question=question[:300], matched=len(results), use_llm=False)
    return {"question": question, "answer": answer, "sources": results, "retrieval": {k: v for k, v in search.items() if k != "results"}, "mode": "pro_hybrid_cited_extractive"}


def rag_quality_check(questions: List[str], category: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
    items = []
    matched = 0
    for q in questions[:50]:
        res = hybrid_search(q, limit=limit, category=category)
        top = (res.get("results") or [{}])[0]
        if res.get("matched", 0):
            matched += 1
        items.append({
            "question": q,
            "matched": res.get("matched", 0),
            "top_title": top.get("title"),
            "top_score": top.get("score"),
            "latency_ms": res.get("latency_ms"),
        })
    total = len(questions[:50])
    return {"total": total, "matched": matched, "coverage": round(matched / total, 3) if total else 0, "items": items}


def pro_health() -> Dict[str, Any]:
    base_health = base.rag_health()
    schema = ensure_pro_schema() if base.supabase_enabled() else {"enabled": False, "ok": True}
    audit_count = 0
    if AUDIT_FILE.exists():
        with AUDIT_FILE.open("r", encoding="utf-8", errors="ignore") as f:
            audit_count = sum(1 for _ in f)
    return {
        "level": "pro_backend_v72_v75",
        "base_health": base_health,
        "pro_schema": schema,
        "features": [
            "structure_aware_chunking",
            "hybrid_vector_keyword_search",
            "simple_reranking",
            "batch_upload_backend",
            "audit_logs",
            "quality_check",
        ],
        "limits": {"max_batch_files": MAX_BATCH_FILES, "max_upload_bytes": base.MAX_UPLOAD_BYTES},
        "audit_events": audit_count,
    }


# ============================================================
# V76-V80 Full Pro backend additions
# ============================================================
# These helpers are intentionally self-contained and work in two modes:
# - Supabase/Postgres mode when DATABASE_URL is configured.
# - Local JSON mode for development/testing without cloud services.

import base64
import hmac
import hashlib as _hashlib
from collections import defaultdict, deque

CACHE_FILE = base.DATA_DIR / "rag_query_cache.json"
SESSIONS_FILE = base.DATA_DIR / "rag_chat_sessions.json"
JOBS_FILE = base.DATA_DIR / "rag_jobs.json"
METRICS_FILE = base.DATA_DIR / "rag_metrics.jsonl"
DELETED_DOCS_FILE = base.DATA_DIR / "rag_deleted_documents.json"
DOCUMENT_VERSIONS_FILE = base.DATA_DIR / "rag_document_versions.json"

CACHE_TTL_SECONDS = int(os.getenv("RAG_CACHE_TTL_SECONDS", "900"))
MAX_SESSION_MESSAGES = int(os.getenv("RAG_MAX_SESSION_MESSAGES", "20"))
JOB_AUTO_RUN = os.getenv("RAG_JOB_AUTO_RUN", "true").lower() not in {"0", "false", "no"}


def _load_json_file(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _save_json_file(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _metric(event: str, **payload: Any) -> Dict[str, Any]:
    row = {"id": str(uuid.uuid4()), "ts": base.now_iso(), "event": event, **payload}
    try:
        with METRICS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return row


def ensure_full_pro_schema() -> Dict[str, Any]:
    """Create optional production tables/columns for full-pro backend features."""
    pro = ensure_pro_schema()
    if not base.supabase_enabled():
        return {"ok": True, "enabled": False, "pro_schema": pro, "message": "Local full-pro mode only"}
    try:
        with base._pg_conn() as conn:  # type: ignore[attr-defined]
            with conn.cursor() as cur:
                cur.execute("alter table rag_documents add column if not exists deleted_at timestamptz")
                cur.execute("alter table rag_documents add column if not exists version int default 1")
                cur.execute("alter table rag_documents add column if not exists parent_document_id uuid")
                cur.execute("alter table rag_documents add column if not exists effective_from date")
                cur.execute("alter table rag_documents add column if not exists effective_to date")
                cur.execute("alter table rag_documents add column if not exists authority_level int default 0")
                cur.execute("create index if not exists rag_documents_deleted_idx on rag_documents(deleted_at)")
                cur.execute("create index if not exists rag_documents_version_idx on rag_documents(parent_document_id, version)")
                cur.execute("""
                    create table if not exists rag_document_versions (
                      id uuid primary key default gen_random_uuid(),
                      document_id uuid,
                      title text,
                      version int default 1,
                      content_sha256 text,
                      metadata jsonb default '{}'::jsonb,
                      created_at timestamptz default now()
                    )
                """)
                cur.execute("""
                    create table if not exists rag_chat_sessions (
                      id text primary key,
                      title text,
                      messages jsonb default '[]'::jsonb,
                      metadata jsonb default '{}'::jsonb,
                      updated_at timestamptz default now(),
                      created_at timestamptz default now()
                    )
                """)
                cur.execute("""
                    create table if not exists rag_jobs (
                      id text primary key,
                      job_type text not null,
                      status text not null,
                      payload jsonb default '{}'::jsonb,
                      result jsonb default '{}'::jsonb,
                      error text,
                      created_at timestamptz default now(),
                      updated_at timestamptz default now()
                    )
                """)
                cur.execute("""
                    create table if not exists rag_metrics (
                      id uuid primary key default gen_random_uuid(),
                      event text not null,
                      payload jsonb default '{}'::jsonb,
                      created_at timestamptz default now()
                    )
                """)
            conn.commit()
        return {"ok": True, "enabled": True, "pro_schema": pro}
    except Exception as exc:
        return {"ok": False, "enabled": True, "error": str(exc), "pro_schema": pro}


def _cache_key(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return _hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cached_hybrid_search(question: str, limit: int = 8, category: Optional[str] = None, document_type: Optional[str] = None, tags: Optional[List[str]] = None, bypass_cache: bool = False) -> Dict[str, Any]:
    payload = {"question": question, "limit": limit, "category": category, "document_type": document_type, "tags": tags or []}
    key = _cache_key(payload)
    cache = _load_json_file(CACHE_FILE, {})
    now = time.time()
    if not bypass_cache and key in cache:
        item = cache[key]
        if now - item.get("created_ts", 0) <= CACHE_TTL_SECONDS:
            result = item.get("result", {})
            result = dict(result)
            result["cache"] = {"hit": True, "key": key, "ttl_seconds": CACHE_TTL_SECONDS}
            _metric("search_cache_hit", question=question[:200], matched=result.get("matched"))
            return result
    result = hybrid_search(question, limit=limit, category=category, document_type=document_type, tags=tags)
    result["cache"] = {"hit": False, "key": key, "ttl_seconds": CACHE_TTL_SECONDS}
    cache[key] = {"created_ts": now, "created_at": base.now_iso(), "result": result}
    # Keep cache bounded.
    if len(cache) > 500:
        ordered = sorted(cache.items(), key=lambda kv: kv[1].get("created_ts", 0), reverse=True)[:500]
        cache = dict(ordered)
    _save_json_file(CACHE_FILE, cache)
    _metric("search_cache_miss", question=question[:200], matched=result.get("matched"))
    return result


def clear_query_cache() -> Dict[str, Any]:
    old = _load_json_file(CACHE_FILE, {})
    _save_json_file(CACHE_FILE, {})
    audit_log("rag_cache_clear", cleared=len(old))
    return {"ok": True, "cleared": len(old)}


def _session_get(session_id: str) -> Dict[str, Any]:
    sessions = _load_json_file(SESSIONS_FILE, {})
    return sessions.get(session_id) or {"id": session_id, "title": None, "messages": [], "metadata": {}, "created_at": base.now_iso(), "updated_at": base.now_iso()}


def _session_save(session: Dict[str, Any]) -> Dict[str, Any]:
    sessions = _load_json_file(SESSIONS_FILE, {})
    session["updated_at"] = base.now_iso()
    session["messages"] = session.get("messages", [])[-MAX_SESSION_MESSAGES:]
    sessions[session["id"]] = session
    _save_json_file(SESSIONS_FILE, sessions)
    return session


def list_chat_sessions(limit: int = 50) -> Dict[str, Any]:
    sessions = _load_json_file(SESSIONS_FILE, {})
    items = list(sessions.values())
    items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    slim = []
    for s in items[:limit]:
        slim.append({"id": s.get("id"), "title": s.get("title"), "messages": len(s.get("messages", [])), "updated_at": s.get("updated_at"), "created_at": s.get("created_at")})
    return {"items": slim, "total": len(items)}


def get_chat_session(session_id: str) -> Dict[str, Any]:
    return _session_get(session_id)


def reset_chat_session(session_id: str) -> Dict[str, Any]:
    session = {"id": session_id, "title": None, "messages": [], "metadata": {}, "created_at": base.now_iso(), "updated_at": base.now_iso()}
    _session_save(session)
    audit_log("rag_session_reset", session_id=session_id)
    return session


def _contextualize_question(question: str, messages: List[Dict[str, Any]]) -> str:
    if not messages:
        return question
    # Lightweight query rewrite: include the last few user questions and assistant source titles.
    recent = messages[-6:]
    prior_user = [m.get("content", "") for m in recent if m.get("role") == "user"][-3:]
    if not prior_user:
        return question
    return "\n".join(["Ngữ cảnh hội thoại gần nhất:", *prior_user, "\nCâu hỏi hiện tại:", question])


def chat_answer(session_id: str, question: str, limit: int = 8, category: Optional[str] = None, document_type: Optional[str] = None, tags: Optional[List[str]] = None, style: str = "detailed", use_llm: bool = False) -> Dict[str, Any]:
    session = _session_get(session_id)
    contextual = _contextualize_question(question, session.get("messages", []))
    search = cached_hybrid_search(contextual, limit=limit, category=category, document_type=document_type, tags=tags)
    answer_text = build_cited_answer(question, search.get("results", []), style=style)
    session.setdefault("messages", []).append({"role": "user", "content": question, "ts": base.now_iso()})
    session.setdefault("messages", []).append({"role": "assistant", "content": answer_text, "ts": base.now_iso(), "sources": search.get("results", [])[:8]})
    if not session.get("title"):
        session["title"] = question[:80]
    _session_save(session)
    audit_log("rag_chat_answer", session_id=session_id, matched=search.get("matched"), question=question[:300])
    _metric("chat_answer", session_id=session_id, matched=search.get("matched"), latency_ms=search.get("latency_ms"))
    return {"session_id": session_id, "question": question, "contextual_query": contextual, "answer": answer_text, "sources": search.get("results", []), "retrieval": {k: v for k, v in search.items() if k != "results"}}


def create_job(job_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    jobs = _load_json_file(JOBS_FILE, {})
    job_id = str(uuid.uuid4())
    job = {"id": job_id, "job_type": job_type, "status": "queued", "payload": payload, "result": None, "error": None, "created_at": base.now_iso(), "updated_at": base.now_iso()}
    jobs[job_id] = job
    _save_json_file(JOBS_FILE, jobs)
    audit_log("rag_job_created", job_id=job_id, job_type=job_type)
    if JOB_AUTO_RUN:
        return run_job(job_id)
    return job


def run_job(job_id: str) -> Dict[str, Any]:
    jobs = _load_json_file(JOBS_FILE, {})
    job = jobs.get(job_id)
    if not job:
        return {"ok": False, "error": "job_not_found", "job_id": job_id}
    job["status"] = "running"
    job["updated_at"] = base.now_iso()
    jobs[job_id] = job
    _save_json_file(JOBS_FILE, jobs)
    try:
        if job["job_type"] == "clear_cache":
            result = clear_query_cache()
        elif job["job_type"] == "quality_check":
            result = rag_quality_check(job.get("payload", {}).get("questions", []), category=job.get("payload", {}).get("category"), limit=job.get("payload", {}).get("limit", 5))
        elif job["job_type"] == "reindex_document":
            result = base.reindex_rag_document(job.get("payload", {}).get("document_id"), chunk_size=job.get("payload", {}).get("chunk_size", 1200), overlap=job.get("payload", {}).get("overlap", 180))
        else:
            result = {"ok": False, "error": "unknown_job_type", "job_type": job["job_type"]}
        job["status"] = "done" if result.get("ok", True) is not False else "failed"
        job["result"] = result
        job["updated_at"] = base.now_iso()
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
        job["updated_at"] = base.now_iso()
    jobs[job_id] = job
    _save_json_file(JOBS_FILE, jobs)
    audit_log("rag_job_finished", job_id=job_id, job_type=job.get("job_type"), status=job.get("status"))
    return job


def list_jobs(limit: int = 100, status: Optional[str] = None) -> Dict[str, Any]:
    jobs = _load_json_file(JOBS_FILE, {})
    items = list(jobs.values())
    if status:
        items = [j for j in items if j.get("status") == status]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"items": items[:limit], "total": len(items)}


def get_job(job_id: str) -> Dict[str, Any]:
    jobs = _load_json_file(JOBS_FILE, {})
    return jobs.get(job_id) or {"ok": False, "error": "job_not_found", "job_id": job_id}


def soft_delete_document(document_id: str, reason: str = "manual_delete") -> Dict[str, Any]:
    deleted = _load_json_file(DELETED_DOCS_FILE, {})
    deleted[document_id] = {"document_id": document_id, "deleted_at": base.now_iso(), "reason": reason}
    _save_json_file(DELETED_DOCS_FILE, deleted)
    if base.supabase_enabled():
        try:
            _execute("update rag_documents set status='deleted', deleted_at=now(), metadata = coalesce(metadata,'{}'::jsonb) || %s::jsonb where id=%s", (json.dumps({"delete_reason": reason}, ensure_ascii=False), document_id))
            audit_log("rag_document_soft_delete", document_id=document_id, reason=reason)
            return {"ok": True, "mode": "supabase_soft_delete", "document_id": document_id, "reason": reason}
        except Exception as exc:
            return {"ok": False, "mode": "supabase_soft_delete", "document_id": document_id, "error": str(exc)}
    audit_log("rag_document_soft_delete", status="local_only", document_id=document_id, reason=reason)
    return {"ok": True, "mode": "local_marker", "document_id": document_id, "reason": reason}


def restore_document(document_id: str) -> Dict[str, Any]:
    deleted = _load_json_file(DELETED_DOCS_FILE, {})
    existed = document_id in deleted
    deleted.pop(document_id, None)
    _save_json_file(DELETED_DOCS_FILE, deleted)
    if base.supabase_enabled():
        try:
            _execute("update rag_documents set status='active', deleted_at=null where id=%s", (document_id,))
            audit_log("rag_document_restore", document_id=document_id)
            return {"ok": True, "mode": "supabase_restore", "document_id": document_id, "was_deleted": existed}
        except Exception as exc:
            return {"ok": False, "mode": "supabase_restore", "document_id": document_id, "error": str(exc)}
    audit_log("rag_document_restore", status="local_only", document_id=document_id)
    return {"ok": True, "mode": "local_marker", "document_id": document_id, "was_deleted": existed}


def list_document_versions(document_id: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    versions = _load_json_file(DOCUMENT_VERSIONS_FILE, [])
    if document_id:
        versions = [v for v in versions if str(v.get("document_id")) == str(document_id)]
    if base.supabase_enabled():
        try:
            cond = "where document_id=%s" if document_id else ""
            params: Sequence[Any] = (document_id,) if document_id else ()
            rows = _pg_rows(f"select * from rag_document_versions {cond} order by created_at desc limit {int(limit)}", params)
            return {"items": rows, "total_loaded": len(rows), "mode": "supabase"}
        except Exception as exc:
            return {"items": versions[-limit:][::-1], "total_loaded": len(versions), "mode": "local_fallback", "error": str(exc)}
    return {"items": versions[-limit:][::-1], "total_loaded": len(versions), "mode": "local"}


def register_document_version(document_id: str, title: str, content_sha256: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    versions = _load_json_file(DOCUMENT_VERSIONS_FILE, [])
    current = [v for v in versions if str(v.get("document_id")) == str(document_id)]
    version_no = len(current) + 1
    row = {"id": str(uuid.uuid4()), "document_id": document_id, "title": title, "version": version_no, "content_sha256": content_sha256, "metadata": metadata or {}, "created_at": base.now_iso()}
    versions.append(row)
    _save_json_file(DOCUMENT_VERSIONS_FILE, versions)
    if base.supabase_enabled():
        try:
            _execute("insert into rag_document_versions (document_id,title,version,content_sha256,metadata) values (%s,%s,%s,%s,%s::jsonb)", (document_id, title, version_no, content_sha256, json.dumps(metadata or {}, ensure_ascii=False)))
        except Exception:
            pass
    return row


def advanced_answer(question: str, limit: int = 8, category: Optional[str] = None, document_type: Optional[str] = None, tags: Optional[List[str]] = None, style: str = "detailed", bypass_cache: bool = False) -> Dict[str, Any]:
    start = time.time()
    search = cached_hybrid_search(question, limit=limit, category=category, document_type=document_type, tags=tags, bypass_cache=bypass_cache)
    answer = build_cited_answer(question, search.get("results", []), style=style)
    confidence = 0.0
    if search.get("results"):
        scores = [float(r.get("score") or 0) for r in search.get("results", [])[:5]]
        confidence = round(min(1.0, sum(scores) / max(1, len(scores)) / 10.0), 3)
    flags = []
    if confidence < 0.25:
        flags.append("low_confidence")
    if not search.get("matched"):
        flags.append("no_source_found")
    _metric("advanced_answer", matched=search.get("matched"), confidence=confidence, latency_ms=int((time.time()-start)*1000))
    return {"question": question, "answer": answer, "confidence": confidence, "quality_flags": flags, "sources": search.get("results", []), "retrieval": {k: v for k, v in search.items() if k != "results"}, "latency_ms": int((time.time()-start)*1000), "mode": "full_pro_cached_hybrid_cited"}


def metrics_summary(limit: int = 1000) -> Dict[str, Any]:
    rows = []
    if METRICS_FILE.exists():
        with METRICS_FILE.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    rows = rows[-limit:]
    by_event: Dict[str, int] = defaultdict(int)
    latencies = []
    matched = []
    for r in rows:
        by_event[r.get("event", "unknown")] += 1
        if isinstance(r.get("latency_ms"), (int, float)):
            latencies.append(float(r.get("latency_ms")))
        if isinstance(r.get("matched"), (int, float)):
            matched.append(float(r.get("matched")))
    return {
        "events_loaded": len(rows),
        "by_event": dict(by_event),
        "avg_latency_ms": round(sum(latencies)/len(latencies), 2) if latencies else None,
        "avg_matched": round(sum(matched)/len(matched), 2) if matched else None,
        "cache_items": len(_load_json_file(CACHE_FILE, {})),
        "sessions": len(_load_json_file(SESSIONS_FILE, {})),
        "jobs": len(_load_json_file(JOBS_FILE, {})),
    }


def full_pro_health() -> Dict[str, Any]:
    health = pro_health()
    schema = ensure_full_pro_schema()
    health.update({
        "level": "full_pro_backend_v76_v80",
        "full_pro_schema": schema,
        "full_pro_features": [
            "multi_turn_rag_chat_sessions",
            "query_cache_with_ttl",
            "background_job_queue_local_or_worker_ready",
            "document_soft_delete_restore",
            "document_version_registry",
            "metrics_summary",
            "confidence_and_quality_flags",
            "role_guard_ready_for_admin_user",
        ],
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "max_session_messages": MAX_SESSION_MESSAGES,
        "job_auto_run": JOB_AUTO_RUN,
        "metrics": metrics_summary(500),
    })
    return health
