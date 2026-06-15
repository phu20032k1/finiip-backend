"""Finiip V101 - Supabase-backed RAG storage adapter.

This module keeps the same response shapes as the V86/V100 local JSON store but
can persist official Admin RAG knowledge into Supabase:

- File bytes        -> Supabase Storage bucket (default: rag-knowledge)
- Document metadata -> public.admin_rag_documents by default
- Text chunks       -> public.admin_rag_document_chunks by default

It is safe for local development: unless RAG_STORAGE_MODE=supabase and the
Supabase env vars are present, callers can keep using the existing local store.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import unicodedata
import threading
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from services.accounting_ai_full import ACCOUNT_NAMES, analyze_transaction, solve_text_question
from services.smart_orchestrator_v110 import analyze_request

from services.accounting_ai_enterprise import (
    ENTERPRISE_VERSION,
    ROOT_DIR,
    _id,
    _now,
    _sha256_text,
    _tokens as _enterprise_tokens,
    ask_accounting_ai,
    search_documents as search_documents_local,
    extract_text_from_bytes,
    normalize_extracted_text_for_rag,
    split_document_into_chunks,
)

V101_VERSION = "v110_long_context_calculation_file_intelligence"

# V59-V62: persistent local conversation memory is used when Supabase is not
# active, so follow-up questions also work during local development.
LOCAL_CHAT_MEMORY_PATH = Path(ROOT_DIR) / "data" / "rag_chat_memory_v106.json"
_LOCAL_CHAT_MEMORY_LOCK = threading.Lock()
MAX_LOCAL_MEMORY_MESSAGES = int(os.getenv("FINIIP_LOCAL_CHAT_MEMORY_MAX", "400"))


def _tokens(text: Any) -> List[str]:
    """Tokenize Vietnamese text consistently for Supabase RAG.

    The enterprise tokenizer strips accents but does not convert Vietnamese
    "đ/Đ" into "d/D", so phrases like "sửa đổi" became "sua oi".
    Converting here improves both retrieval and the answer synthesizer without
    changing older local-store behavior.
    """
    safe = str(text or "").replace("đ", "d").replace("Đ", "D")
    return _enterprise_tokens(safe)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _table_env(name: str, default: str) -> str:
    """Read a safe PostgREST table name from env.

    V101 originally reused ``rag_documents``. Older V67/V68 builds also used that
    table name with a different ``id uuid`` schema, which caused admin uploads to
    fail with Supabase REST 400 / PostgreSQL 23502. The V101 admin console now uses
    its own tables by default, while still allowing an explicit override.
    """
    value = _env(name, default)
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        return value
    return default


RAG_DOCUMENTS_TABLE = _table_env("SUPABASE_RAG_DOCUMENTS_TABLE", "admin_rag_documents")
RAG_CHUNKS_TABLE = _table_env("SUPABASE_RAG_CHUNKS_TABLE", "admin_rag_document_chunks")
RAG_AUDIT_TABLE = _table_env("SUPABASE_RAG_AUDIT_TABLE", "admin_rag_audit_logs")
RAG_EVAL_TABLE = _table_env("SUPABASE_RAG_EVAL_TABLE", "admin_rag_eval_results")
RAG_MEMORY_TABLE = _table_env("SUPABASE_RAG_MEMORY_TABLE", "admin_rag_chat_messages")

SUPABASE_SCHEMA_SQL = f"""
-- Finiip V101 Supabase Admin RAG schema
-- Run in Supabase SQL Editor. Keep service_role key ONLY on the backend.
-- These table names intentionally avoid the older V67/V68 rag_documents schema.

create table if not exists public.{RAG_DOCUMENTS_TABLE} (
  document_id text primary key,
  workspace_id text not null default 'default',
  title text not null,
  source_type text not null default 'knowledge',
  content_sha256 text,
  metadata jsonb not null default '{{}}'::jsonb,
  status text not null default 'active',
  chunk_count integer not null default 0,
  char_count integer not null default 0,
  storage_bucket text,
  storage_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.{RAG_CHUNKS_TABLE} (
  chunk_id text primary key,
  document_id text not null references public.{RAG_DOCUMENTS_TABLE}(document_id) on delete cascade,
  workspace_id text not null default 'default',
  title text not null,
  source_type text not null default 'knowledge',
  section integer,
  chunk_no integer,
  heading text,
  content text not null,
  tokens text[] not null default '{{}}',
  created_at timestamptz not null default now()
);

create table if not exists public.{RAG_AUDIT_TABLE} (
  audit_id bigint generated always as identity primary key,
  event_type text not null,
  workspace_id text,
  document_id text,
  payload jsonb not null default '{{}}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.{RAG_EVAL_TABLE} (
  eval_id bigint generated always as identity primary key,
  workspace_id text not null default 'default',
  question text not null,
  expected_answer text,
  expected_source text,
  actual_answer text,
  score numeric not null default 0,
  passed boolean not null default false,
  payload jsonb not null default '{{}}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.{RAG_MEMORY_TABLE} (
  message_id bigint generated always as identity primary key,
  conversation_id text not null default 'admin',
  workspace_id text not null default 'default',
  role text not null,
  content text not null,
  metadata jsonb not null default '{{}}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_{RAG_DOCUMENTS_TABLE}_workspace_status
  on public.{RAG_DOCUMENTS_TABLE}(workspace_id, status, updated_at desc);

create index if not exists idx_{RAG_CHUNKS_TABLE}_workspace_doc
  on public.{RAG_CHUNKS_TABLE}(workspace_id, document_id, chunk_no);

create index if not exists idx_{RAG_CHUNKS_TABLE}_tokens_gin
  on public.{RAG_CHUNKS_TABLE} using gin(tokens);

create index if not exists idx_{RAG_EVAL_TABLE}_workspace_created
  on public.{RAG_EVAL_TABLE}(workspace_id, created_at desc);

create index if not exists idx_{RAG_MEMORY_TABLE}_workspace_conversation_created
  on public.{RAG_MEMORY_TABLE}(workspace_id, conversation_id, created_at desc);

-- Storage bucket: create manually in Supabase dashboard if it does not exist:
-- Bucket name: rag-knowledge or the value of SUPABASE_RAG_BUCKET. Public: false.
-- If RLS is enabled, keep writes through backend service_role only.
""".strip()


def supabase_config() -> Dict[str, Any]:
    url = _env("SUPABASE_URL").rstrip("/")
    key = _env("SUPABASE_SERVICE_ROLE_KEY") or _env("SUPABASE_KEY")
    bucket = _env("SUPABASE_RAG_BUCKET", "rag-knowledge")
    mode = _env("RAG_STORAGE_MODE", "local").lower()
    configured = bool(url and key)
    active = mode == "supabase" and configured
    return {
        "version": V101_VERSION,
        "mode": mode,
        "active_backend": "supabase" if active else "local",
        "configured": configured,
        "supabase_url_set": bool(url),
        "service_role_key_set": bool(key),
        "bucket": bucket,
        "tables": [RAG_DOCUMENTS_TABLE, RAG_CHUNKS_TABLE, RAG_AUDIT_TABLE, RAG_EVAL_TABLE, RAG_MEMORY_TABLE],
        "table_env_vars": {
            "documents": "SUPABASE_RAG_DOCUMENTS_TABLE",
            "chunks": "SUPABASE_RAG_CHUNKS_TABLE",
            "audit": "SUPABASE_RAG_AUDIT_TABLE",
        },
        "note": "Supabase active when RAG_STORAGE_MODE=supabase and SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY are set.",
    }


def supabase_is_active() -> bool:
    return supabase_config()["active_backend"] == "supabase"


def require_supabase_active() -> None:
    if not supabase_is_active():
        cfg = supabase_config()
        raise RuntimeError(
            "Supabase RAG chưa active. Đặt RAG_STORAGE_MODE=supabase, "
            "SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY và SUPABASE_RAG_BUCKET. "
            f"Trạng thái hiện tại: {cfg}"
        )




def _supabase_rest_error_hint(response_text: str) -> str:
    text = response_text or ""
    if any(code in text for code in ("PGRST204", "23502")):
        return (
            " | Gợi ý: schema Supabase có thể đang là bản cũ V67/V68 hoặc chưa chạy SQL V101. "
            f"Admin UI V101 mặc định dùng các bảng {RAG_DOCUMENTS_TABLE}, {RAG_CHUNKS_TABLE}, {RAG_AUDIT_TABLE}. "
            "Mở /admin/rag-ui/api/supabase-schema?key=YOUR_ADMIN_KEY, chạy SQL trong Supabase SQL Editor, "
            "rồi thử upload lại. Nếu dùng SUPABASE_RAG_BUCKET riêng, nhớ tạo bucket tương ứng."
        )
    return ""

class SupabaseRAGClient:
    def __init__(self) -> None:
        cfg = supabase_config()
        self.url = _env("SUPABASE_URL").rstrip("/")
        self.key = _env("SUPABASE_SERVICE_ROLE_KEY") or _env("SUPABASE_KEY")
        self.bucket = cfg["bucket"]
        if not self.url or not self.key:
            raise RuntimeError("Thiếu SUPABASE_URL hoặc SUPABASE_SERVICE_ROLE_KEY")
        self.timeout = float(_env("SUPABASE_TIMEOUT_SECONDS", "30") or "30")

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
        }

    def rest(self, method: str, table: str, *, params: Optional[Dict[str, Any]] = None, json_body: Any = None, prefer: Optional[str] = None) -> Any:
        headers = dict(self.headers)
        headers["Content-Type"] = "application/json"
        if prefer:
            headers["Prefer"] = prefer
        with httpx.Client(timeout=self.timeout) as client:
            res = client.request(method, f"{self.url}/rest/v1/{table}", headers=headers, params=params, json=json_body)
        if res.status_code >= 400:
            raise RuntimeError(f"Supabase REST lỗi {res.status_code}: {res.text[:500]}{_supabase_rest_error_hint(res.text)}")
        if res.text:
            try:
                return res.json()
            except Exception:
                return res.text
        return None

    def storage_upload(self, object_path: str, content: bytes, content_type: str = "application/octet-stream") -> Dict[str, Any]:
        headers = dict(self.headers)
        headers["Content-Type"] = content_type
        headers["x-upsert"] = "true"
        encoded = "/".join(urllib.parse.quote(part) for part in object_path.split("/"))
        with httpx.Client(timeout=self.timeout) as client:
            res = client.put(f"{self.url}/storage/v1/object/{self.bucket}/{encoded}", headers=headers, content=content)
        if res.status_code >= 400:
            raise RuntimeError(f"Supabase Storage upload lỗi {res.status_code}: {res.text[:500]}")
        try:
            return res.json()
        except Exception:
            return {"ok": True, "path": object_path}

    def storage_download(self, object_path: str) -> bytes:
        encoded = "/".join(urllib.parse.quote(part) for part in object_path.split("/"))
        with httpx.Client(timeout=self.timeout) as client:
            res = client.get(f"{self.url}/storage/v1/object/{self.bucket}/{encoded}", headers=self.headers)
        if res.status_code >= 400:
            raise RuntimeError(f"Supabase Storage download lỗi {res.status_code}: {res.text[:500]}")
        return res.content

    def storage_delete(self, object_path: str) -> Dict[str, Any]:
        # Supabase supports DELETE for individual objects through this REST path.
        encoded = "/".join(urllib.parse.quote(part) for part in object_path.split("/"))
        with httpx.Client(timeout=self.timeout) as client:
            res = client.delete(f"{self.url}/storage/v1/object/{self.bucket}/{encoded}", headers=self.headers)
        if res.status_code >= 400:
            # Keep metadata deletion working even if object delete is not supported by the deployed gateway.
            return {"ok": False, "warning": f"Storage delete lỗi {res.status_code}: {res.text[:300]}"}
        return {"ok": True}


def _safe_storage_name(filename: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(filename).name) or "upload.bin"
    return safe_name[:180]


def _content_type(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".csv": "text/csv; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".htm": "text/html; charset=utf-8",
    }.get(suffix, "application/octet-stream")


def _parse_markdown_front_matter(text: str) -> tuple[Dict[str, Any], str]:
    """Parse the small YAML-like header used by the bundled knowledge pack.

    This intentionally avoids a PyYAML dependency. It supports scalar values and
    either ``[a, b]`` or dash-list syntax, which is enough for our metadata.
    Unknown syntax is kept as plain text instead of raising.
    """
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not raw.startswith("---\n"):
        return {}, raw
    end = raw.find("\n---\n", 4)
    if end < 0:
        return {}, raw
    header = raw[4:end]
    body = raw[end + 5 :].lstrip("\n")
    meta: Dict[str, Any] = {}
    current_key = ""
    for original_line in header.splitlines():
        line = original_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("-") and current_key:
            item = stripped[1:].strip().strip('"\'')
            current = meta.get(current_key)
            if not isinstance(current, list):
                current = []
            current.append(item)
            meta[current_key] = current
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_key = key
        if not value:
            meta[key] = []
            continue
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            meta[key] = [part.strip().strip('"\'') for part in inner.split(",") if part.strip()]
            continue
        clean = value.strip('"\'')
        low = clean.lower()
        if low in {"true", "false"}:
            meta[key] = low == "true"
        elif re.fullmatch(r"-?\d+", clean):
            try:
                meta[key] = int(clean)
            except Exception:
                meta[key] = clean
        else:
            meta[key] = clean
    return meta, body


def _parse_iso_date(value: Any) -> Optional[date]:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            pass
    return None


def _source_knowledge_metadata(source: Dict[str, Any]) -> Dict[str, Any]:
    metadata = source.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    front = metadata.get("knowledge_front_matter") or metadata.get("front_matter") or {}
    if not isinstance(front, dict):
        front = {}
    intelligence = metadata.get("document_intelligence") or metadata.get("legal_intelligence") or {}
    if not isinstance(intelligence, dict):
        intelligence = {}
    merged = dict(intelligence)
    merged.update(front)
    return merged


def _query_mentions_source(question: str, source: Dict[str, Any]) -> bool:
    q = _normalized_text(question) if "_normalized_text" in globals() else str(question or "").lower()
    meta = _source_knowledge_metadata(source)
    values = [
        meta.get("document_number"), meta.get("doc_no"), meta.get("title"),
        source.get("title"),
    ]
    for value in values:
        n = _normalized_text(str(value or "")) if "_normalized_text" in globals() else str(value or "").lower()
        if n and len(n) >= 5 and n in q:
            return True
    return False


def _source_governance_policy(question: str, source: Dict[str, Any]) -> Dict[str, Any]:
    """Govern legal freshness, authority and incomplete extracts.

    The gate does not replace retrieval relevance. It prevents a future-effective,
    repealed or partial legal extract from being presented as current complete law.
    """
    meta = _source_knowledge_metadata(source)
    status = str(meta.get("status") or "active").strip().lower()
    authority = str(meta.get("authority") or meta.get("source_authority") or "curated_internal").strip().lower()
    completeness = str(meta.get("source_completeness") or "summary").strip().lower()
    effective_value = meta.get("effective_from") or meta.get("effective_date")
    effective = _parse_iso_date(effective_value)
    q = _normalized_text(question) if "_normalized_text" in globals() else str(question or "").lower()
    named_source = _query_mentions_source(question, source)
    asks_future = any(x in q for x in ["sap toi", "tu ngay", "sau ngay", "tu 01/07/2026", "nam 2027", "future"])
    asks_history = any(x in q for x in ["truoc day", "lich su", "tai thoi diem", "nam 2024", "nam 2025", "quy dinh cu"])
    legal_query = bool(_extract_legal_identifiers(question)) if "_extract_legal_identifiers" in globals() else False
    legal_query = legal_query or any(x in q for x in ["hien hanh", "quy dinh", "thong tu", "nghi dinh", "luat", "thue", "muc phat", "thoi han"])

    accepted = True
    reason = "source_governance_ok"
    warnings: List[str] = []
    priority = 0.0
    authority_weight = {
        "official_legal": 7.0,
        "official_legal_extract": 6.0,
        "verified_legal_summary": 5.0,
        "curated_internal": 3.0,
        "internal_policy": 3.0,
        "faq": 1.0,
    }
    priority += authority_weight.get(authority, 2.0)

    if status in {"repealed", "superseded", "inactive", "deleted"} and not (named_source or asks_history):
        accepted = False
        reason = "source_not_current"
    if status in {"future_effective", "pending"} or (effective and effective > date.today()):
        warnings.append(f"Nguồn này chỉ có hiệu lực từ {effective.isoformat() if effective else effective_value}.")
        priority -= 5.0
        if legal_query and not (named_source or asks_future):
            accepted = False
            reason = "future_effective_source_not_current_answer"
    if completeness in {"partial", "partial_extract", "excerpt", "incomplete"}:
        warnings.append("Nguồn là bản trích/không đầy đủ; không nên dùng một mình để kết luận toàn bộ văn bản.")
        priority -= 1.5
        concepts = _concepts_in_text(question) if "_concepts_in_text" in globals() else []
        if any(c in concepts for c in ["penalty", "deadline", "signer"]) and not named_source:
            accepted = False
            reason = "partial_source_not_enough_for_exact_legal_answer"
    verified = str(meta.get("verified_on") or "").strip()
    if legal_query and authority.startswith("official") and verified:
        priority += 1.0
    return {
        "accepted": accepted,
        "reason": reason,
        "priority": round(priority, 2),
        "warnings": warnings,
        "status": status,
        "authority": authority,
        "source_completeness": completeness,
        "effective_from": str(effective_value or ""),
        "named_source": named_source,
    }



# ---------------------------------------------------------------------------
# V60-V66 quality layer: document intelligence, legal citations, memory, evals
# ---------------------------------------------------------------------------

_ACCOUNTING_RISK_TERMS = [
    "hạch toán", "định khoản", "ghi sổ", "quyết toán", "kê khai", "thuế", "hoá đơn", "hóa đơn",
    "khấu hao", "dự phòng", "tài sản", "công nợ", "báo cáo tài chính", "hợp nhất", "bút toán",
]


def _extract_document_intelligence(filename: str, title: str, text: str, source_type: str = "knowledge") -> Dict[str, Any]:
    """Best-effort metadata extraction without requiring a separate NLP service.

    Stored in document.metadata so the admin UI and conflict checker can explain
    what was uploaded: document type, legal number, effective date, modified docs,
    and suggested tags. It is deliberately conservative; unknown fields stay blank.
    """
    sample = normalize_extracted_text_for_rag("\n".join([title or "", filename or "", text[:9000] or ""]))
    compact = re.sub(r"\s+", " ", sample).strip()
    lower = compact.lower()
    doc_type = "knowledge"
    if "thông tư" in lower or "thong tu" in _normalized_text(compact):
        doc_type = "circular"
    elif "nghị định" in lower or "nghi dinh" in _normalized_text(compact):
        doc_type = "decree"
    elif "chuẩn mực" in lower or "chuan muc" in _normalized_text(compact):
        doc_type = "accounting_standard"
    elif "hợp đồng" in lower or "hop dong" in _normalized_text(compact):
        doc_type = "contract"
    elif "báo cáo tài chính" in lower or "bao cao tai chinh" in _normalized_text(compact):
        doc_type = "financial_statement"
    elif source_type in {"accounting_law", "tax_legal"}:
        doc_type = "legal_document"

    number = ""
    patterns = [
        r"Số\s*[:：]?\s*([0-9]+/[0-9]{4}/[A-ZĐ\-]+)",
        r"([0-9]+/[0-9]{4}/TT-BTC)",
        r"([0-9]+/[0-9]{4}/NĐ-CP)",
        r"([0-9]+/[0-9]{4}/QH[0-9]+)",
    ]
    for pat in patterns:
        m = re.search(pat, compact, flags=re.I)
        if m:
            number = m.group(1).strip()
            break

    issue_date = ""
    m = re.search(r"ngày\s*(\d{1,2})\s*tháng\s*(\d{1,2})\s*năm\s*(\d{4})", compact, flags=re.I)
    if m:
        issue_date = f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"

    effective_date = ""
    eff_patterns = [
        r"có hiệu lực kể từ ngày ký ban hành",
        r"hiệu lực kể từ ngày ký ban hành",
        r"áp dụng[^\.]{0,120}?từ hoặc sau ngày\s*(\d{1,2}/\d{1,2}/\d{4})",
        r"có hiệu lực[^\.]{0,80}?ngày\s*(\d{1,2}/\d{1,2}/\d{4})",
    ]
    if re.search(eff_patterns[0], compact, flags=re.I) or re.search(eff_patterns[1], compact, flags=re.I):
        effective_date = "kể từ ngày ký ban hành"
    for pat in eff_patterns[2:]:
        m = re.search(pat, compact, flags=re.I)
        if m:
            effective_date = m.group(1)
            break

    modified_documents = []
    for m in re.finditer(r"(?:sửa đổi,?\s*bổ sung|sửa đổi|thay thế)[^\.]{0,160}?((?:Thông tư|Nghị định|Luật)\s+số\s+[0-9]+/[0-9]{4}/[A-ZĐ\-]+)", compact, flags=re.I):
        value = re.sub(r"\s+", " ", m.group(1)).strip()
        if value not in modified_documents:
            modified_documents.append(value)
    for m in re.finditer(r"([0-9]+/[0-9]{4}/(?:TT-BTC|NĐ-CP|QH[0-9]+))", compact, flags=re.I):
        value = m.group(1).upper()
        if number and value == number.upper():
            continue
        if any(value in old.upper() for old in modified_documents):
            continue
        # Only add bare references when the document clearly says amend/replace near them.
        start = max(0, m.start() - 80)
        near = _normalized_text(compact[start:m.end()+80])
        if any(t in near for t in ["sua doi", "bo sung", "thay the", "bai bo"]):
            modified_documents.append(value)

    title_guess = ""
    title_match = re.search(r"(THÔNG\s+TƯ|NGHỊ\s+ĐỊNH|LUẬT)\s+([^\n]{0,500})", sample, flags=re.I)
    if title_match:
        title_guess = _clean_rag_text(title_match.group(0), max_len=260)

    norm = _normalized_text(compact)
    tags = set([source_type or "knowledge", doc_type])
    tag_map = [
        ("bao cao tai chinh hop nhat", "consolidated_financial_statements"),
        ("thue gtgt", "vat"),
        ("hoa don", "invoice"),
        ("tndn", "corporate_income_tax"),
        ("khau hao", "depreciation"),
        ("loi ich co dong khong kiem soat", "non_controlling_interest"),
        ("loi the thuong mai", "goodwill"),
        ("phu luc", "appendix"),
    ]
    for needle, tag in tag_map:
        if needle in norm:
            tags.add(tag)

    return {
        "version": "v64_document_intelligence",
        "document_type": doc_type,
        "document_number": number,
        "issue_date": issue_date,
        "effective_date": effective_date,
        "title_guess": title_guess,
        "modified_documents": modified_documents[:20],
        "tags": sorted(t for t in tags if t),
    }


def _citation_document_title(src: Dict[str, Any]) -> str:
    meta = src.get("metadata") or {}
    front = meta.get("knowledge_front_matter") or meta.get("front_matter") or {}
    intel = meta.get("document_intelligence") or meta.get("legal_intelligence") or {}
    number = front.get("doc_no") or front.get("document_number") or intel.get("document_number") or ""
    if number:
        if "TT-BTC" in number.upper():
            return f"Thông tư {number}"
        if "NĐ-CP" in number.upper():
            return f"Nghị định {number}"
        return number
    return str(front.get("title") or src.get("title") or "Tài liệu RAG")


_FRIENDLY_LOCAL_SOURCE_TITLES = {
    "accounting_accounts.md": "Hệ thống tài khoản kế toán Finiip",
    "he_thong_tai_khoan.md": "Hệ thống tài khoản kế toán",
    "ke_toan_co_ban.md": "Cẩm nang kế toán cơ bản",
    "accounting_full_playbook_v85.md": "Cẩm nang nghiệp vụ kế toán Finiip",
    "quy_trinh_ke_toan_noi_bo.md": "Quy trình kế toán nội bộ",
    "vat_hoa_don.md": "Cẩm nang VAT và hóa đơn",
    "cau_hoi_thuong_gap.md": "Kho câu hỏi nghiệp vụ thường gặp",
    "tai_san_co_dinh.md": "Cẩm nang tài sản cố định",
    "chi_phi_duoc_tru.md": "Cẩm nang chi phí được trừ",
    "cong_cu_dung_cu.md": "Cẩm nang công cụ dụng cụ",
    "accounting_operations_complete_v110.md": "Sổ tay nghiệp vụ kế toán toàn diện",
    "financial_analysis_and_planning_v110.md": "Phân tích tài chính và kế hoạch dòng tiền",
    "business_management_internal_control_v110.md": "Quản trị và kiểm soát nội bộ",
    "data_excel_reporting_v110.md": "Xử lý dữ liệu, Excel và báo cáo",
    "contract_review_business_v110.md": "Khung rà soát hợp đồng doanh nghiệp",
    "long_question_file_report_policy_v110.md": "Chính sách xử lý câu hỏi dài và báo cáo",
}


def _friendly_source_title(value: Any) -> str:
    """Turn an internal path/technical title into a user-facing source label.

    The frontend should never have to show strings such as
    ``knowledge_base/accounting_accounts.md`` inside the answer bubble.
    """
    raw = str(value or "").strip()
    if not raw:
        return "Kiến thức nghiệp vụ Finiip"
    aliases = {
        "danh mục tài khoản kế toán nội bộ": "Hệ thống tài khoản kế toán Finiip",
        "danh muc tai khoan ke toan noi bo": "Hệ thống tài khoản kế toán Finiip",
        "nguồn nội bộ": "Kiến thức nghiệp vụ Finiip",
        "nguon noi bo": "Kiến thức nghiệp vụ Finiip",
    }
    if raw.lower() in aliases:
        return aliases[raw.lower()]
    path_like = bool(
        re.search(r"\.(md|txt|pdf|docx?|xlsx?|csv|json)$", raw, flags=re.I)
        or raw.replace("\\", "/").lower().startswith(("knowledge_base/", "data/", "docs/", "uploads/"))
    )
    filename = (raw.replace("\\", "/").split("/")[-1] if path_like else raw).lower()
    if filename in _FRIENDLY_LOCAL_SOURCE_TITLES:
        return _FRIENDLY_LOCAL_SOURCE_TITLES[filename]
    base = raw.replace("\\", "/").split("/")[-1] if path_like else raw
    clean = re.sub(r"\.(md|txt|pdf|docx?|xlsx?|csv|json)$", "", base, flags=re.I)
    clean = clean.replace("_", " ").replace("-", " ")
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:1].upper() + clean[1:] if clean else "Kiến thức nghiệp vụ Finiip"


def _citation_from_local_source(source_name: str, index: int = 1, excerpt: str = "") -> Dict[str, Any]:
    return {
        "index": index,
        "title": _friendly_source_title(source_name),
        "document_title": _friendly_source_title(source_name),
        "document_id": source_name or None,
        "chunk_id": None,
        "chunk_no": None,
        "heading": None,
        "page": None,
        "location": "Kho kiến thức nghiệp vụ Finiip",
        "legal_location": "",
        "excerpt": _clean_rag_text(excerpt, max_len=500) if excerpt else "",
        "source_kind": "internal_knowledge",
    }


def _source_cards(citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compact, frontend-ready cards; answer text remains clean and readable."""
    cards: List[Dict[str, Any]] = []
    seen = set()
    for idx, citation in enumerate(citations or [], 1):
        title = _friendly_source_title(citation.get("document_title") or citation.get("title"))
        page = citation.get("page")
        location = str(citation.get("legal_location") or citation.get("location") or "").strip()
        key = (title, str(page or ""), location)
        if key in seen:
            continue
        seen.add(key)
        badge = "Nguồn nội bộ"
        if citation.get("document_id") and citation.get("chunk_id"):
            badge = "Tài liệu RAG"
        if any(token in title.lower() for token in ["thông tư", "nghị định", "luật"]):
            badge = "Văn bản pháp lý"
        cards.append({
            "index": len(cards) + 1,
            "title": title,
            "badge": badge,
            "page": page,
            "location": location or (f"Trang {page}" if page else "Kho kiến thức Finiip"),
            "excerpt": _clean_rag_text(citation.get("excerpt") or "", max_len=320),
            "document_id": citation.get("document_id"),
            "chunk_id": citation.get("chunk_id"),
        })
    return cards[:8]


def _answer_mode_from_question(question: str, answer_mode: str = "auto") -> str:
    mode = (answer_mode or "auto").strip().lower()
    allowed = {"auto", "short", "detailed", "chief_accountant", "with_example", "with_journal", "risk", "source_only"}
    if mode not in allowed:
        mode = "auto"
    if mode != "auto":
        return mode
    q = _normalized_text(question)
    # A journal question is not automatically a long chief-accountant report.
    # Keep it concise unless the user explicitly asks for a process or analysis.
    if any(t in q for t in ["quy trinh", "toan bo", "chi tiet", "giai thich tung buoc", "ke toan truong"]):
        return "chief_accountant"
    if any(t in q for t in ["vi du", "minh hoa"]):
        return "with_example"
    if any(t in q for t in ["rui ro", "kiem tra", "canh bao", "sai sot"]):
        return "risk"
    if any(t in q for t in ["but toan", "dinh khoan", "hach toan", "ghi no", "ghi co"]):
        return "with_journal"
    return "short"


def _is_accounting_workflow_question(question: str, answer_mode: str = "auto") -> bool:
    q = _normalized_text(question)
    explicit_process = any(t in q for t in [
        "quy trinh", "tung buoc", "cac buoc", "luong xu ly", "ke toan truong",
        "kiem soat noi bo", "duyet va ghi so", "xu ly tu dau den cuoi",
    ])
    return explicit_process or _answer_mode_from_question(question, answer_mode) == "chief_accountant"


def _build_accounting_workflow_section(question: str, citations: List[Dict[str, Any]], answer_mode: str = "auto") -> List[str]:
    """Only add a workflow when the user actually asks for one.

    The previous implementation appended consolidation-specific steps (ownership
    ratios, loss of control, group reporting) to ordinary purchase and expense
    questions. That made most RAG answers look unrelated even when retrieval was
    acceptable.
    """
    if not _is_accounting_workflow_question(question, answer_mode):
        return []
    source_refs = ", ".join(f"[{c.get('index')}]" for c in citations[:3]) or "nguồn đã truy xuất"
    return [
        "",
        "Quy trình xử lý đề xuất",
        f"- Bước 1: Xác định đúng bản chất nghiệp vụ và căn cứ áp dụng từ {source_refs}.",
        "- Bước 2: Kiểm tra hợp đồng, hóa đơn/chứng từ, đối tượng, thời điểm và phương thức thanh toán.",
        "- Bước 3: Xác định tài khoản, thuế và số tiền; lập bút toán hoặc kết luận nháp.",
        "- Bước 4: Đối chiếu chính sách kế toán nội bộ và văn bản còn hiệu lực.",
        "- Bước 5: Kế toán phụ trách kiểm tra, sửa nếu cần và duyệt trước khi ghi sổ/kê khai.",
    ]


def _source_only_answer(question: str, sources: List[Dict[str, Any]], citations: List[Dict[str, Any]]) -> str:
    lines = ["Các nguồn RAG phù hợp nhất:", ""]
    for idx, src in enumerate(sources[:8], 1):
        loc = _source_location(src, excerpt=str(src.get("snippet") or src.get("content") or "")[:240])
        lines.append(f"[{idx}] {_citation_document_title(src)} — {loc}")
        lines.append(f"    {_clean_rag_text(src.get('snippet') or src.get('content') or '', max_len=260)}")
    return "\n".join(lines)


def _combine_history(server_history: str, browser_history: str) -> str:
    parts = [p.strip() for p in [server_history, browser_history] if p and p.strip()]
    if not parts:
        return ""
    max_chars = max(3000, min(int(os.getenv("FINIIP_CHAT_CONTEXT_CHARS", "10000")), 30000))
    return "\n\n".join(parts)[-max_chars:]



def _load_local_chat_memory() -> Dict[str, Any]:
    try:
        if not LOCAL_CHAT_MEMORY_PATH.exists():
            return {"messages": []}
        data = json.loads(LOCAL_CHAT_MEMORY_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
            return {"messages": []}
        return data
    except Exception:
        return {"messages": []}


def _save_local_chat_memory(data: Dict[str, Any]) -> None:
    LOCAL_CHAT_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    messages = list(data.get("messages") or [])[-MAX_LOCAL_MEMORY_MESSAGES:]
    payload = {"version": V101_VERSION, "messages": messages}
    tmp = LOCAL_CHAT_MEMORY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(LOCAL_CHAT_MEMORY_PATH)


def _list_local_chat_memory(workspace_id: str, conversation_id: str, limit: int) -> Dict[str, Any]:
    with _LOCAL_CHAT_MEMORY_LOCK:
        data = _load_local_chat_memory()
        items = [
            item for item in data.get("messages", [])
            if item.get("workspace_id") == (workspace_id or "default")
            and item.get("conversation_id") == (conversation_id or "admin")
        ]
    items.sort(key=lambda x: str(x.get("created_at") or ""))
    return {
        "items": items[-max(1, min(limit, 50)):],
        "storage_backend": "local",
        "path": str(LOCAL_CHAT_MEMORY_PATH),
    }


def list_supabase_chat_memory(workspace_id: str = "default", conversation_id: str = "admin", limit: int = 8) -> Dict[str, Any]:
    if not supabase_is_active():
        return _list_local_chat_memory(workspace_id, conversation_id, limit)
    try:
        client = SupabaseRAGClient()
        rows = client.rest("GET", RAG_MEMORY_TABLE, params={
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "conversation_id": f"eq.{conversation_id or 'admin'}",
            "order": "created_at.desc",
            "limit": str(max(1, min(limit, 50))),
        }) or []
        return {"items": list(reversed(rows)), "storage_backend": "supabase", "table": RAG_MEMORY_TABLE}
    except Exception as exc:
        fallback = _list_local_chat_memory(workspace_id, conversation_id, limit)
        fallback["warning"] = f"Supabase memory chưa sẵn sàng, đã dùng local memory: {exc}"
        return fallback


def _format_memory_for_retrieval(items: List[Dict[str, Any]]) -> str:
    out = []
    for item in items[-20:]:
        role = item.get("role") or "user"
        content = _clean_rag_text(item.get("content") or "", max_len=1200)
        if content:
            out.append(f"{role}: {content}")
    return "\n".join(out)


def _save_local_chat_message(workspace_id: str, conversation_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    with _LOCAL_CHAT_MEMORY_LOCK:
        data = _load_local_chat_memory()
        messages = list(data.get("messages") or [])
        messages.append({
            "workspace_id": workspace_id or "default",
            "conversation_id": conversation_id or "admin",
            "role": role,
            "content": str(content)[:12000],
            "metadata": metadata or {},
            "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        })
        data["messages"] = messages[-MAX_LOCAL_MEMORY_MESSAGES:]
        _save_local_chat_memory(data)


def save_supabase_chat_message(workspace_id: str, conversation_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    if not content:
        return
    if not supabase_is_active():
        _save_local_chat_message(workspace_id, conversation_id, role, content, metadata)
        return
    try:
        client = SupabaseRAGClient()
        client.rest("POST", RAG_MEMORY_TABLE, json_body={
            "workspace_id": workspace_id or "default",
            "conversation_id": conversation_id or "admin",
            "role": role,
            "content": str(content)[:12000],
            "metadata": metadata or {},
        }, prefer="return=minimal")
    except Exception:
        _save_local_chat_message(workspace_id, conversation_id, role, content, metadata)


def clear_supabase_chat_memory(workspace_id: str = "default", conversation_id: str = "admin") -> Dict[str, Any]:
    local_deleted = 0
    with _LOCAL_CHAT_MEMORY_LOCK:
        data = _load_local_chat_memory()
        old = list(data.get("messages") or [])
        kept = [
            item for item in old
            if not (
                item.get("workspace_id") == (workspace_id or "default")
                and item.get("conversation_id") == (conversation_id or "admin")
            )
        ]
        local_deleted = len(old) - len(kept)
        data["messages"] = kept
        _save_local_chat_memory(data)

    if not supabase_is_active():
        return {"ok": True, "deleted": local_deleted, "storage_backend": "local"}
    try:
        client = SupabaseRAGClient()
        client.rest("DELETE", RAG_MEMORY_TABLE, params={"workspace_id": f"eq.{workspace_id}", "conversation_id": f"eq.{conversation_id or 'admin'}"})
        return {"ok": True, "workspace_id": workspace_id, "conversation_id": conversation_id, "local_deleted": local_deleted, "storage_backend": "supabase"}
    except Exception as exc:
        return {"ok": local_deleted >= 0, "error": str(exc), "local_deleted": local_deleted, "storage_backend": "local_fallback"}


def _collect_conflict_warnings(question: str, workspace_id: str = "default", sources: Optional[List[Dict[str, Any]]] = None) -> List[str]:
    """Warn when the query/source mentions a document that another uploaded doc amends/replaces."""
    warnings: List[str] = []
    qn = _normalized_text(question)
    mentioned_numbers = set(re.findall(r"\b\d+\s*/\s*\d{4}\s*/\s*(?:tt\s*-\s*btc|nd\s*-\s*cp|qh\d+)\b", qn, flags=re.I))
    mentioned_numbers = {re.sub(r"\s+", "", x).upper().replace("ND-CP", "NĐ-CP") for x in mentioned_numbers}
    for src in sources or []:
        meta = src.get("metadata") or {}
        intel = meta.get("document_intelligence") or meta.get("legal_intelligence") or {}
        num = str(intel.get("document_number") or "").upper()
        if num:
            mentioned_numbers.add(num)
    try:
        docs = list_documents_supabase(workspace_id=workspace_id).get("items", []) if supabase_is_active() else []
    except Exception:
        docs = []
    q_mentions_update = any(t in qn for t in ["sua doi", "thay the", "bai bo", "van ban cu", "quy dinh cu", "thong tu 202"])
    source_new_numbers = set()
    for src in sources or []:
        meta = src.get("metadata") or {}
        intel = meta.get("document_intelligence") or meta.get("legal_intelligence") or {}
        if intel.get("document_number"):
            source_new_numbers.add(str(intel.get("document_number")).upper())

    for doc in docs:
        meta = doc.get("metadata") or {}
        intel = meta.get("document_intelligence") or meta.get("legal_intelligence") or {}
        new_no = str(intel.get("document_number") or doc.get("title") or "")
        new_no_norm = new_no.upper()
        for old in intel.get("modified_documents") or []:
            old_norm = str(old).upper()
            old_hit = any(num in old_norm or old_norm in num for num in mentioned_numbers)
            new_hit = new_no_norm in source_new_numbers and q_mentions_update
            if old_hit or new_hit:
                msg = f"Lưu ý xung đột/cập nhật: {new_no} có nội dung sửa đổi/bổ sung/thay thế {old}. Khi hỏi theo văn bản cũ, cần ưu tiên kiểm tra văn bản mới hơn này."
                if msg not in warnings:
                    warnings.append(msg)
    return warnings[:5]


def _score_eval_answer(actual: str, expected_answer: str = "", expected_source: str = "") -> Dict[str, Any]:
    actual_n = _normalized_text(actual or "")
    expected_n = _normalized_text(expected_answer or "")
    source_n = _normalized_text(expected_source or "")
    score = 0.0
    checks = []
    if expected_n:
        expected_tokens = [t for t in expected_n.split() if len(t) >= 2]
        hit = sum(1 for t in expected_tokens if t in actual_n)
        coverage = hit / max(1, len(expected_tokens))
        score += min(70.0, coverage * 70.0)
        checks.append({"type": "expected_answer", "coverage": round(coverage, 3), "hit": hit, "total": len(expected_tokens)})
    else:
        score += 50.0 if actual_n else 0.0
    if source_n:
        source_tokens = [t for t in source_n.split() if len(t) >= 2]
        hit = sum(1 for t in source_tokens if t in actual_n)
        coverage = hit / max(1, len(source_tokens))
        score += min(20.0, coverage * 20.0)
        checks.append({"type": "expected_source", "coverage": round(coverage, 3), "hit": hit, "total": len(source_tokens)})
    if "nguon" in actual_n or "trang" in actual_n or "dieu" in actual_n:
        score += 10.0
    score = round(min(100.0, score), 2)
    return {"score": score, "passed": score >= 70.0, "checks": checks}


def evaluate_rag_test_cases_supabase(
    cases: List[Dict[str, Any]],
    workspace_id: str = "default",
    answer_mode: str = "short",
    conversation_id: str = "admin_eval",
) -> Dict[str, Any]:
    results = []
    for case in cases[:50]:
        question = str(case.get("question") or "").strip()
        if not question:
            continue
        expected_answer = str(case.get("expected_answer") or "").strip()
        expected_source = str(case.get("expected_source") or "").strip()
        answer = answer_with_supabase_rag(
            question=question,
            workspace_id=workspace_id,
            limit=6,
            history="",
            answer_mode=answer_mode,
            conversation_id=conversation_id,
            save_memory=False,
        ) if supabase_is_active() else {"answer": "Eval Center cần Supabase active để test đúng RAG.", "citations": []}
        score = _score_eval_answer(answer.get("answer") or "", expected_answer, expected_source)
        row = {
            "question": question,
            "expected_answer": expected_answer,
            "expected_source": expected_source,
            "actual_answer": answer.get("answer"),
            "citations": answer.get("citations") or [],
            "score": score["score"],
            "passed": score["passed"],
            "checks": score["checks"],
        }
        results.append(row)
        if supabase_is_active():
            try:
                client = SupabaseRAGClient()
                client.rest("POST", RAG_EVAL_TABLE, json_body={
                    "workspace_id": workspace_id or "default",
                    "question": question,
                    "expected_answer": expected_answer,
                    "expected_source": expected_source,
                    "actual_answer": str(answer.get("answer") or "")[:12000],
                    "score": score["score"],
                    "passed": score["passed"],
                    "payload": {"citations": answer.get("citations") or [], "checks": score["checks"], "answer_mode": answer_mode},
                }, prefer="return=minimal")
            except Exception:
                pass
    passed = sum(1 for r in results if r.get("passed"))
    avg = round(sum(float(r.get("score") or 0) for r in results) / max(1, len(results)), 2)
    return {"version": "v60_eval_center", "workspace_id": workspace_id, "count": len(results), "passed": passed, "failed": len(results)-passed, "avg_score": avg, "items": results}

def add_uploaded_document_supabase(
    *,
    filename: str,
    content: bytes,
    workspace_id: str = "default",
    title: Optional[str] = None,
    source_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Extract text, upload original file to Storage, insert metadata/chunks into Supabase."""
    require_supabase_active()
    client = SupabaseRAGClient()
    extracted = extract_text_from_bytes(filename, content)
    now = _now()
    document_id = _id("doc")
    safe_name = _safe_storage_name(filename)
    object_path = f"rag/{workspace_id or 'default'}/{datetime.utcnow().strftime('%Y/%m/%d')}/{document_id}_{safe_name}"
    client.storage_upload(object_path, content, content_type=_content_type(filename))

    raw_text = normalize_extracted_text_for_rag(extracted.get("text") or "")
    front_matter, body_text = _parse_markdown_front_matter(raw_text) if Path(filename or "").suffix.lower() == ".md" else ({}, raw_text)
    text = body_text or raw_text
    chunks = split_document_into_chunks(text)
    source_type = source_type or str(front_matter.get("source_type") or front_matter.get("doc_type") or "knowledge")
    if source_type in {"circular", "decree", "law", "legal", "tax_legal"}:
        source_type = "accounting_law"
    intelligence = _extract_document_intelligence(filename, title or filename, text, source_type=source_type)
    # Auto-tag obvious official legal/accounting documents while preserving explicit admin choice.
    if source_type == "knowledge" and intelligence.get("document_type") in {"circular", "decree", "legal_document", "accounting_standard"}:
        source_type = "accounting_law"
        intelligence["tags"] = sorted(set((intelligence.get("tags") or []) + ["accounting_law"]))
    meta = dict(metadata or {})
    meta.update({
        "filename": filename,
        "parser": extracted.get("parser"),
        "sha256": extracted.get("sha256"),
        "warnings": extracted.get("warnings") or [],
        "storage_backend": "supabase",
        "storage_bucket": client.bucket,
        "storage_path": object_path,
        "rag_text_normalizer": "v1_vietnamese_legal_spacing",
        "document_intelligence": intelligence,
        "legal_intelligence": intelligence,
        "knowledge_front_matter": front_matter,
    })
    doc = {
        "document_id": document_id,
        "workspace_id": workspace_id or "default",
        "title": title or filename,
        "source_type": source_type,
        "content_sha256": _sha256_text(text),
        "metadata": meta,
        "status": "active",
        "chunk_count": len(chunks),
        "char_count": len(text),
        "storage_bucket": client.bucket,
        "storage_path": object_path,
        "created_at": now,
        "updated_at": now,
    }
    chunk_rows: List[Dict[str, Any]] = []
    for c in chunks:
        chunk_rows.append({
            "chunk_id": _id("chk"),
            "document_id": document_id,
            "workspace_id": doc["workspace_id"],
            "title": doc["title"],
            "source_type": source_type,
            "section": c.get("section"),
            "chunk_no": c.get("chunk_no"),
            "heading": c.get("heading"),
            "content": c.get("content") or "",
            "tokens": sorted(set(_tokens(c.get("content", ""))))[:500],
            "created_at": now,
        })
    client.rest("POST", RAG_DOCUMENTS_TABLE, json_body=doc, prefer="return=minimal")
    if chunk_rows:
        # PostgREST can accept a JSON array. For very large docs, insert in batches.
        for i in range(0, len(chunk_rows), 500):
            client.rest("POST", RAG_CHUNKS_TABLE, json_body=chunk_rows[i:i + 500], prefer="return=minimal")
    audit_supabase("v101_supabase_document_add", doc["workspace_id"], document_id, {"title": doc["title"], "chunks": len(chunk_rows)})
    return {"workspace": doc["workspace_id"], "document": doc, "chunks_added": len(chunk_rows), "extraction": {k: v for k, v in extracted.items() if k != "text"}}


def list_documents_supabase(workspace_id: Optional[str] = None, include_deleted: bool = False) -> Dict[str, Any]:
    require_supabase_active()
    client = SupabaseRAGClient()
    params: Dict[str, Any] = {"select": "*", "order": "updated_at.desc"}
    if workspace_id:
        params["workspace_id"] = f"eq.{workspace_id}"
    if not include_deleted:
        params["status"] = "neq.deleted"
    docs = client.rest("GET", RAG_DOCUMENTS_TABLE, params=params) or []
    items = []
    for doc in docs:
        metadata = doc.get("metadata") or {}
        item = dict(doc)
        item["document_scope"] = metadata.get("document_scope", "knowledge")
        item["filename"] = metadata.get("filename") or doc.get("storage_path") or doc.get("title")
        item["parser"] = metadata.get("parser")
        item["warnings"] = metadata.get("warnings") or []
        item["admin_note"] = metadata.get("admin_note") or ""
        items.append(item)
    return {"version": V101_VERSION, "storage_backend": "supabase", "count": len(items), "items": items}


def get_document_supabase(document_id: str) -> Dict[str, Any]:
    require_supabase_active()
    client = SupabaseRAGClient()
    docs = client.rest("GET", RAG_DOCUMENTS_TABLE, params={"select": "*", "document_id": f"eq.{document_id}", "limit": "1"}) or []
    if not docs:
        raise KeyError(f"Không tìm thấy document_id={document_id} trên Supabase")
    chunks = client.rest("GET", RAG_CHUNKS_TABLE, params={"select": "*", "document_id": f"eq.{document_id}", "order": "chunk_no.asc"}) or []
    return {"document": docs[0], "chunks": chunks, "chunk_count": len(chunks), "storage_backend": "supabase"}


def delete_document_supabase(document_id: str, hard_delete: bool = False) -> Dict[str, Any]:
    require_supabase_active()
    client = SupabaseRAGClient()
    detail = get_document_supabase(document_id)
    doc = detail["document"]
    chunk_count = len(detail.get("chunks") or [])
    client.rest("DELETE", RAG_CHUNKS_TABLE, params={"document_id": f"eq.{document_id}"})
    storage_result = {"ok": None}
    if hard_delete:
        client.rest("DELETE", RAG_DOCUMENTS_TABLE, params={"document_id": f"eq.{document_id}"})
        if doc.get("storage_path"):
            storage_result = client.storage_delete(doc["storage_path"])
    else:
        client.rest("PATCH", RAG_DOCUMENTS_TABLE, params={"document_id": f"eq.{document_id}"}, json_body={"status": "deleted", "chunk_count": 0, "updated_at": _now()}, prefer="return=minimal")
    audit_supabase("v101_supabase_document_delete", doc.get("workspace_id"), document_id, {"hard_delete": hard_delete, "chunks_removed": chunk_count})
    return {"ok": True, "document_id": document_id, "hard_delete": hard_delete, "chunks_removed": chunk_count, "storage_delete": storage_result, "storage_backend": "supabase"}


def reindex_document_supabase(document_id: str) -> Dict[str, Any]:
    require_supabase_active()
    client = SupabaseRAGClient()
    detail = get_document_supabase(document_id)
    doc = detail["document"]
    metadata = doc.get("metadata") or {}
    filename = metadata.get("filename") or doc.get("title") or "document.bin"
    content_text = ""
    extraction: Dict[str, Any] = {}
    if doc.get("storage_path"):
        data = client.storage_download(doc["storage_path"])
        extraction = extract_text_from_bytes(filename, data)
        content_text = extraction.get("text") or ""
    if not content_text:
        old_chunks = detail.get("chunks") or []
        old_chunks.sort(key=lambda c: c.get("chunk_no") or 0)
        content_text = "\n\n".join(c.get("content", "") for c in old_chunks).strip()
    if not content_text:
        raise ValueError("Không có nội dung để re-index từ Supabase. Hãy upload lại tài liệu.")

    content_text = normalize_extracted_text_for_rag(content_text)
    old_chunk_count = len(detail.get("chunks") or [])
    new_chunks = split_document_into_chunks(content_text)
    intelligence = _extract_document_intelligence(filename, doc.get("title") or filename, content_text, source_type=doc.get("source_type") or "knowledge")
    client.rest("DELETE", RAG_CHUNKS_TABLE, params={"document_id": f"eq.{document_id}"})
    chunk_rows = []
    for c in new_chunks:
        chunk_rows.append({
            "chunk_id": _id("chk"),
            "document_id": document_id,
            "workspace_id": doc.get("workspace_id", "default"),
            "title": doc.get("title"),
            "source_type": doc.get("source_type"),
            "section": c.get("section"),
            "chunk_no": c.get("chunk_no"),
            "heading": c.get("heading"),
            "content": c.get("content") or "",
            "tokens": sorted(set(_tokens(c.get("content", ""))))[:500],
            "created_at": _now(),
        })
    if chunk_rows:
        for i in range(0, len(chunk_rows), 500):
            client.rest("POST", RAG_CHUNKS_TABLE, json_body=chunk_rows[i:i + 500], prefer="return=minimal")
    metadata["last_reindexed_at"] = _now()
    metadata["rag_text_normalizer"] = "v1_vietnamese_legal_spacing"
    metadata["document_intelligence"] = intelligence
    metadata["legal_intelligence"] = intelligence
    if extraction:
        metadata["parser"] = extraction.get("parser")
        metadata["warnings"] = extraction.get("warnings") or []
        metadata["sha256"] = extraction.get("sha256") or metadata.get("sha256")
    client.rest("PATCH", RAG_DOCUMENTS_TABLE, params={"document_id": f"eq.{document_id}"}, json_body={
        "status": "active",
        "chunk_count": len(chunk_rows),
        "char_count": len(content_text),
        "content_sha256": _sha256_text(content_text),
        "metadata": metadata,
        "updated_at": _now(),
    }, prefer="return=minimal")
    audit_supabase("v101_supabase_document_reindex", doc.get("workspace_id"), document_id, {"chunks_added": len(chunk_rows), "chunks_removed": old_chunk_count})
    return {"ok": True, "document_id": document_id, "chunks_added": len(chunk_rows), "chunks_removed": old_chunk_count, "extraction": {k: v for k, v in extraction.items() if k != "text"}, "storage_backend": "supabase"}



# ---------------------------------------------------------------------------
# RAG answer synthesizer
# ---------------------------------------------------------------------------
# The admin test box must answer from retrieved chunks, not dump raw chunks.
# These helpers are deterministic/offline so the RAG tester still works without
# an external LLM key. If a stronger LLM synthesizer is added later, keep this
# as the safe fallback.

_PAGE_RE = re.compile(r"---\s*page\s*(\d+)\s*---", re.I)


def _clean_rag_text(text: Any, max_len: int = 900) -> str:
    raw = "" if text is None else str(text)
    raw = normalize_extracted_text_for_rag(raw)
    raw = _PAGE_RE.sub(" ", raw)
    raw = raw.replace("\r", "\n")
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n\s*\n+", "\n\n", raw)
    raw = re.sub(r"\s+([,.;:!?])", r"\1", raw)
    raw = re.sub(r"([,.;:!?])(?=\S)", r"\1 ", raw)
    raw = raw.strip()
    if len(raw) > max_len:
        raw = raw[: max_len - 1].rstrip() + "…"
    return raw

def _source_page(src: Dict[str, Any]) -> Optional[str]:
    for value in [src.get("page"), src.get("heading"), src.get("content"), src.get("snippet")]:
        if value is None:
            continue
        m = _PAGE_RE.search(str(value))
        if m:
            return m.group(1)
        m = re.search(r"\bpage\s*(\d+)\b", str(value), re.I)
        if m:
            return m.group(1)
    return None


def _source_location(src: Dict[str, Any], excerpt: str = "") -> str:
    parts: List[str] = []
    structural = _extract_structural_location(src, excerpt=excerpt)
    if structural:
        parts.append(structural)
    page = _source_page(src)
    if page:
        parts.append(f"trang {page}")
    if src.get("chunk_no") is not None:
        parts.append(f"chunk {src.get('chunk_no')}")
    if parts:
        return " — ".join(parts)
    if src.get("heading"):
        return str(src.get("heading"))[:80]
    return "nguồn RAG"


def _split_answer_candidates(text: str) -> List[str]:
    """Split Markdown/PDF text into self-contained, answerable passages.

    V109 split numbered-list markers (``1.``) away from their content and could
    rank a heading as the whole answer. V110 groups each heading with its body,
    keeps list items intact and only emits passages that contain real evidence.
    """
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = raw.splitlines()

    sections: List[tuple[str, List[str]]] = []
    heading = ""
    body: List[str] = []

    def flush() -> None:
        nonlocal body
        cleaned = [line for line in body if line.strip()]
        if cleaned:
            sections.append((heading, cleaned))
        body = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if body and body[-1] != "":
                body.append("")
            continue
        heading_match = re.match(r"^#{1,6}\s+(.+?)\s*#*$", line)
        if heading_match:
            flush()
            heading = re.sub(r"[*_`]+", "", heading_match.group(1)).strip()
            continue
        # Keep list item content together; remove only presentation Markdown.
        line = re.sub(r"^[-*•]\s+", "- ", line)
        line = re.sub(r"^(\d{1,3})[.)]\s+", r"\1. ", line)
        line = re.sub(r"[*_`]+", "", line).strip()
        if line:
            body.append(line)
    flush()

    if not sections and raw.strip():
        sections = [("", [_clean_rag_text(raw, max_len=30000)])]

    out: List[str] = []
    max_len = 760
    for section_heading, section_lines in sections:
        units: List[str] = []
        prose = ""
        for line in section_lines + [""]:
            if not line:
                if prose:
                    units.append(prose.strip())
                    prose = ""
                continue
            is_list = bool(re.match(r"^(?:-|\d{1,3}\.)\s+", line))
            if is_list:
                if prose:
                    units.append(prose.strip())
                    prose = ""
                units.append(line)
            else:
                if len(prose) + len(line) + 1 <= 520:
                    prose = (prose + " " + line).strip()
                else:
                    if prose:
                        units.append(prose.strip())
                    prose = line

        expanded: List[str] = []
        for unit in units:
            if len(unit) <= 620:
                expanded.append(unit)
                continue
            pieces = re.split(r"(?<=[.;:!?])\s+", unit)
            buf = ""
            for piece in pieces:
                piece = piece.strip()
                if not piece:
                    continue
                if len(buf) + len(piece) + 1 <= 620:
                    buf = (buf + " " + piece).strip()
                else:
                    if buf:
                        expanded.append(buf)
                    buf = piece[:620].strip()
            if buf:
                expanded.append(buf)

        prefix = f"{section_heading}. " if section_heading else ""
        buffer = ""
        for unit in expanded:
            candidate_unit = unit.strip()
            if not candidate_unit:
                continue
            if len(prefix) + len(buffer) + len(candidate_unit) + 2 <= max_len:
                buffer = (buffer + "\n" + candidate_unit).strip()
            else:
                candidate = (prefix + buffer).strip()
                if len(_tokens(candidate)) >= 3 and not re.fullmatch(r"\d+[.)]?", candidate):
                    out.append(candidate)
                buffer = candidate_unit
        candidate = (prefix + buffer).strip()
        if len(_tokens(candidate)) >= 3 and not re.fullmatch(r"\d+[.)]?", candidate):
            out.append(candidate)

    # Stable de-duplication after Markdown normalization.
    deduped: List[str] = []
    seen: set[str] = set()
    for candidate in out:
        clean = _clean_rag_text(candidate, max_len=max_len).strip()
        key = _normalized_text(clean) if "_normalized_text" in globals() else " ".join(_tokens(clean))
        if not clean or key in seen:
            continue
        seen.add(key)
        deduped.append(clean)
    return deduped


def _normalized_text(text: str) -> str:
    return " ".join(_tokens(text))


def _query_has_any(normalized_query: str, terms: List[str]) -> bool:
    return any(t in normalized_query for t in terms)


def _expand_query_text(query: str, history: str = "") -> str:
    """Expand only with synonyms; never inject an answer into the query.

    Older code inserted fixed values such as a specific circular number, a fixed
    effective date and a 90-day deadline. Those values biased retrieval toward
    one document and caused unrelated questions to return the same chunks.
    """
    base = str(query or "").strip()
    qn = _normalized_text(base)
    additions: List[str] = []
    synonym_groups = [
        (["hieu luc", "ap dung tu", "khi nao co hieu luc"], "ngày có hiệu lực thời điểm áp dụng"),
        (["thoi han", "cham nhat", "bao nhieu ngay", "han nop"], "thời hạn hạn nộp ngày tháng"),
        (["sua doi", "bo sung", "thay the"], "văn bản sửa đổi bổ sung thay thế"),
        (["vat dau vao", "gtgt dau vao", "khau tru"], "thuế giá trị gia tăng đầu vào điều kiện khấu trừ"),
        (["khong co hoa don", "thieu hoa don"], "thiếu hóa đơn chứng từ hợp lệ hồ sơ bổ sung"),
        (["mua hang", "nhap hang"], "mua hàng hóa nhập kho nhà cung cấp"),
        (["chua thanh toan", "mua chiu"], "công nợ phải trả người bán nhà cung cấp"),
        (["ban hang", "doanh thu"], "bán hàng doanh thu khách hàng"),
        (["chua thu tien", "ban chiu"], "công nợ phải thu khách hàng"),
        (["tu dong ghi so", "auto post"], "không tự động ghi sổ cần xác nhận phê duyệt"),
        (["quy trinh"], "các bước xử lý kiểm tra phê duyệt"),
    ]
    for triggers, expansion in synonym_groups:
        if _query_has_any(qn, triggers):
            additions.append(expansion)

    # Preserve exact high-signal identifiers without manufacturing new ones.
    for m in re.finditer(
        r"(?:điều|dieu)\s*\d+[a-zđ]?|(?:khoản|khoan)\s*\d+|(?:mã|ma)\s*số\s*\d+|"
        r"\b\d{1,4}/\d{4}/[A-ZĐ-]{2,20}\b|(?:tài\s*khoản|tai\s*khoan|tk)\s*\d{3,4}",
        base,
        flags=re.I,
    ):
        additions.append(m.group(0))

    followup_terms = ["dieu do", "noi tren", "cai tren", "cau truoc", "truoc do", "van de do"]
    if history and any(t in qn for t in followup_terms):
        additions.append("Ngữ cảnh hội thoại trước: " + str(history)[-2500:])

    unique: List[str] = []
    for item in [base, *additions]:
        item = str(item or "").strip()
        if item and item not in unique:
            unique.append(item)
    return "\n".join(unique)


def _is_formula_question(question: str) -> bool:
    # Do not let the formula router swallow a request that explicitly asks for
    # hạch toán/định khoản. Journal routing has higher priority.
    if _is_journal_question(question):
        return False
    q = _normalized_text(question)
    math_terms = [
        "tinh", "cong thuc", "bao nhieu", "vat", "gtgt", "khau hao", "phan bo", "tndn", "thue",
        "fifo", "binh quan", "loi nhuan", "bien loi nhuan", "gross", "net", "payroll", "luong",
        "hoa von", "lai suat", "tra gop", "khoan vay", "ty le tang", "roe", "roa", "he so thanh toan",
        "npv", "irr", "wacc"
    ]
    has_operator_expression = bool(re.search(r"\d\s*[+\-*/^]\s*\d", question or ""))
    return (any(t in q for t in math_terms) or has_operator_expression) and bool(re.search(r"\d", question or ""))


def _try_formula_answer(question: str) -> Optional[Dict[str, Any]]:
    """Answer deterministic math/accounting formula questions before RAG.

    RAG is for official documents. Formula questions should not depend on a
    random chunk if the numbers are already in the question. This wrapper uses
    the existing V85 solver and returns None when the solver says the question is
    unclear.
    """
    if not _is_formula_question(question):
        return None
    try:
        solved = solve_text_question(question)
    except Exception:
        return None
    answer = str(solved.get("answer") or "").strip()
    if not answer or "chuyển sang tra cứu" in answer.lower():
        return None
    return {
        "answer": "Chế độ tính toán/công thức:\n\n" + answer + "\n\nLưu ý: kết quả tính là nháp, cần đối chiếu chính sách kế toán và chứng từ thực tế trước khi ghi sổ.",
        "citations": [],
        "answer_mode": "formula_engine",
        "formula_result": solved,
    }


def _wants_long_answer(question: str, answer_mode: str = "auto") -> bool:
    mode = _answer_mode_from_question(question, answer_mode)
    # A journal-entry request should stay concise unless the user explicitly asks
    # for a detailed explanation or workflow.
    if mode in {"detailed", "chief_accountant", "with_example", "risk"}:
        return True
    q = _normalized_text(question)
    return any(t in q for t in [
        "chi tiet", "noi dai", "giai thich", "quy trinh", "lo trinh", "toan bo",
        "phan tich", "vi du", "buoc", "ke toan truong", "huong dan",
        "cach ", "gom nhung", "gom cac", "noi dung nao"
    ]) or len(str(question or "")) >= 180

_JOURNAL_TERMS = (
    "hach toan", "dinh khoan", "but toan", "ghi no", "ghi co", "no tk", "co tk",
)

_RETRIEVAL_STOPWORDS = {
    "doanh", "nghiep", "cong", "ty", "thi", "nhu", "the", "nao", "la", "duoc",
    "cua", "va", "voi", "trong", "khi", "mot", "cac", "cho", "can", "theo",
    "hoi", "ve", "gi", "hay", "neu", "tren", "duoi", "nay", "do", "truong",
    "hop", "su", "dung", "noi", "dung", "xin", "cho", "biet", "phai",
}

# Multi-word concepts are much safer than isolated words such as "tài sản",
# "doanh nghiệp" or "hàng hóa" that occur in almost every accounting PDF.
_CONCEPT_GROUPS: Dict[str, List[str]] = {
    "account_lookup": ["tai khoan", "tk"],
    "purchase": ["mua hang", "mua hang hoa", "nhap hang", "nhap kho"],
    "unpaid": ["chua thanh toan", "mua chiu", "phai tra nguoi ban", "cong no nha cung cap"],
    "sale": ["ban hang", "doanh thu", "xuat hoa don"],
    "uncollected": ["chua thu tien", "ban chiu", "phai thu khach hang"],
    "vat_input": ["vat dau vao", "gtgt dau vao", "thue gtgt dau vao"],
    "vat_deduction": ["khau tru", "dieu kien khau tru"],
    "vat_rate": ["thue suat vat", "thue suat gtgt", "vat bao nhieu phan tram"],
    "invoice_missing": ["khong co hoa don", "thieu hoa don", "chua co hoa don"],
    "journal": ["hach toan", "dinh khoan", "but toan", "ghi no", "ghi co"],
    "procedure": ["quy trinh", "cac buoc", "luong xu ly"],
    "auto_post": ["tu dong ghi so", "auto post", "khong tu ghi so"],
    "fixed_asset": ["tai san co dinh", "tscd"],
    "tools": ["cong cu dung cu", "ccdc"],
    "prepaid": ["chi phi tra truoc", "phan bo"],
    "effective_date": ["hieu luc", "ap dung tu"],
    "deadline": ["thoi han", "han nop", "cham nhat", "bao nhieu ngay"],
    "penalty": ["muc phat", "xu phat", "phat bao nhieu"],
    "signer": ["nguoi ky", "ai ky", "ky ban hanh"],
}


def _concepts_in_text(text: str) -> List[str]:
    n = _normalized_text(text)
    found: List[str] = []
    for name, phrases in _CONCEPT_GROUPS.items():
        if any(p in n for p in phrases):
            found.append(name)
    return found


def _extract_legal_identifiers(text: str) -> List[str]:
    raw = str(text or "")
    identifiers: List[str] = []
    patterns = [
        r"\b\d{1,4}/\d{4}/[A-ZĐ-]{2,20}\b",
        r"(?i)\b(?:điều|dieu)\s*\d+[a-zđ]?\b",
        r"(?i)(?<!tài )(?<!tai )\b(?:khoản|khoan)\s*\d+\b",
        r"(?i)\b(?:mã|ma)\s*số\s*\d+\b",
    ]
    for pattern in patterns:
        for value in re.findall(pattern, raw):
            normalized = _normalized_text(value)
            if normalized and normalized not in identifiers:
                identifiers.append(normalized)
    return identifiers


def _is_journal_question(question: str) -> bool:
    q = _normalized_text(question)
    return any(term in q for term in _JOURNAL_TERMS)


def _is_unpaid_purchase_question(question: str) -> bool:
    q = _normalized_text(question)
    purchase = any(term in q for term in [
        "mua hang", "mua hang hoa", "nhap hang", "nhap kho", "mua chiu",
    ])
    unpaid = any(term in q for term in [
        "chua thanh toan", "mua chiu", "cong no nha cung cap",
        "phai tra nguoi ban", "no nha cung cap",
    ])
    return purchase and unpaid


def _is_unpaid_sale_question(question: str) -> bool:
    q = _normalized_text(question)
    sale = any(term in q for term in ["ban hang", "ban san pham", "xuat hoa don", "doanh thu"])
    unpaid = any(term in q for term in ["chua thu tien", "ban chiu", "khach hang no", "phai thu khach hang"])
    return sale and unpaid


def _meaningful_query_tokens(text: str) -> List[str]:
    return [
        token for token in _tokens(text)
        if len(token) >= 2 and token not in _RETRIEVAL_STOPWORDS
    ]


def _account_codes_from_question(question: str) -> List[str]:
    """Extract explicit account codes such as ``TK 641`` or ``Tài khoản 641``.

    Account numbers are high-signal identifiers. A query for TK 641 must never
    be answered from a chunk that only happens to contain generic words such as
    ``tài khoản`` or ``trường hợp``.
    """
    text = str(question or "")
    patterns = [
        r"(?i)\b(?:tài\s*khoản|tai\s*khoan|tk|số\s*hiệu\s*tài\s*khoản|so\s*hieu\s*tai\s*khoan)\s*[:#-]?\s*(\d{3,4})\b",
    ]
    found: List[str] = []
    for pattern in patterns:
        for code in re.findall(pattern, text):
            normalized = str(int(code)) if code.isdigit() else code
            if normalized not in found:
                found.append(normalized)
    return found


def _text_contains_account_code(text: str, code: str) -> bool:
    """Return True only when *code* is written as an accounting account.

    A bare number is not enough. PDF page numbers, amounts, years and table
    cells may contain the same digits as an account code. Explicit account
    lookups therefore require ``TK``/``Tài khoản`` or a real chart-of-accounts
    row such as ``641 - Chi phí bán hàng``.
    """
    raw = str(text or "")
    normalized = _normalized_text(raw)
    escaped = re.escape(str(code))

    # Strong prose forms: "TK 641", "Tài khoản 641", or
    # "Số hiệu tài khoản 641".
    if re.search(
        rf"\b(?:tk|tai khoan|so hieu tai khoan)\s*[:#-]?\s*{escaped}\b",
        normalized,
        flags=re.I,
    ):
        return True

    # A chart-of-accounts row may omit the words "tài khoản", but it must have
    # a separator and a textual account name. Never accept a bare number merely
    # because several words happen to follow it.
    if re.search(
        rf"(?:^|[\n\r]|#{{1,6}}\s*)\s*{escaped}\s*[-—:]\s*[A-Za-zÀ-ỹĐđ][^\n\r.;]{{2,120}}",
        raw,
        flags=re.I,
    ):
        return True

    # PDF extraction sometimes flattens headings into one long line. Keep that
    # fallback strict by requiring a separator and an accounting noun phrase.
    account_name_prefixes = (
        "chi phi|doanh thu|hang hoa|tien |phai |thue |tai san|von |"
        "hao mon|cong cu|nguyen lieu|thanh pham|gia von"
    )
    if re.search(
        rf"\b{escaped}\s*[-—:]\s*(?:{account_name_prefixes})\b",
        normalized,
        flags=re.I,
    ):
        return True

    return False

def _source_relevance_metrics(question: str, source: Dict[str, Any]) -> Dict[str, Any]:
    """Strict relevance and answerability gate.

    A chunk is accepted only when it matches the subject of the question and it
    contains the kind of evidence the question asks for. This prevents "mức
    phạt bao nhiêu" from being answered by a paragraph that merely says
    "thiếu hóa đơn", and prevents TK 641 from matching a random occurrence of
    the words "tài khoản".
    """
    q_tokens = _meaningful_query_tokens(question)
    unique_q = set(q_tokens)
    haystack = " ".join([
        str(source.get("title") or ""),
        str(source.get("heading") or ""),
        str(source.get("content") or source.get("snippet") or ""),
    ])
    h_norm = _normalized_text(haystack)
    h_tokens = set(_tokens(haystack))
    overlap = sorted(unique_q & h_tokens)
    coverage = len(overlap) / max(1, len(unique_q))
    score = float(source.get("score") or 0)
    answerability = float(source.get("answerability_score") or 0)

    q_concepts = _concepts_in_text(question)
    h_concepts = _concepts_in_text(haystack)
    concept_overlap = sorted(set(q_concepts) & set(h_concepts))
    phrase_hits = 0
    qn = _normalized_text(question)
    meaningful = _meaningful_query_tokens(question)
    for n in (4, 3, 2):
        for i in range(max(0, len(meaningful) - n + 1)):
            phrase = " ".join(meaningful[i:i+n])
            if len(phrase) >= 7 and phrase in h_norm:
                phrase_hits += 1
                break

    # Generic baseline. Short questions need high coverage or an exact phrase;
    # longer questions need at least three meaningful overlaps.
    if len(unique_q) <= 3:
        accepted = coverage >= 0.67 or phrase_hits > 0 or bool(concept_overlap)
    else:
        accepted = len(overlap) >= 3 and coverage >= 0.30
        accepted = accepted or (len(overlap) >= 2 and phrase_hits > 0 and coverage >= 0.22)
        accepted = accepted or (len(concept_overlap) >= 2 and len(overlap) >= 2)
    accepted = bool(accepted and score >= 3)
    reason = "semantic_subject_gate"

    account_codes = _account_codes_from_question(question)
    matched_codes: List[str] = []
    if account_codes:
        matched_codes = [code for code in account_codes if _text_contains_account_code(haystack, code)]
        accepted = bool(matched_codes)
        reason = "account_query_requires_exact_account_code"

    # Exact legal identifiers are mandatory when the user names them.
    q_legal = _extract_legal_identifiers(question)
    h_legal = set(_extract_legal_identifiers(haystack))
    missing_legal = [identifier for identifier in q_legal if identifier not in h_legal]
    if q_legal and missing_legal:
        accepted = False
        reason = "missing_exact_legal_identifier"

    if _is_unpaid_purchase_question(question):
        purchase_anchor = any(x in h_norm for x in [
            "mua hang", "nhap hang", "nhap kho", "no tk 156", "no 156", "tai khoan 156",
        ])
        payable_anchor = any(x in h_norm for x in [
            "chua thanh toan", "mua chiu", "phai tra nguoi ban", "cong no nha cung cap",
            "co tk 331", "co 331", "tai khoan 331",
        ])
        accepted = purchase_anchor and payable_anchor
        reason = "unpaid_purchase_requires_purchase_and_payable_anchors"
    elif _is_unpaid_sale_question(question):
        revenue_anchor = any(x in h_norm for x in ["ban hang", "doanh thu", "co tk 511", "co 511"])
        receivable_anchor = any(x in h_norm for x in ["chua thu tien", "ban chiu", "phai thu khach hang", "no tk 131", "no 131"])
        accepted = revenue_anchor and receivable_anchor
        reason = "unpaid_sale_requires_revenue_and_receivable_anchors"
    elif _is_journal_question(question):
        journal_signal = bool(re.search(r"\b(?:no|co)\s*(?:tk\s*)?\d{3,4}\b", h_norm)) or any(
            x in h_norm for x in ["hach toan", "dinh khoan", "but toan"]
        )
        accepted = bool(accepted and journal_signal)
        reason = "journal_question_requires_journal_evidence"

    # Answer-type requirements.
    if "penalty" in q_concepts:
        has_penalty = any(x in h_norm for x in ["muc phat", "xu phat", "phat tien", "bi phat"])
        has_penalty_number = bool(re.search(r"\b\d[\d\s.,]*(?:dong|trieu|ty|%)\b", h_norm))
        accepted = bool(accepted and has_penalty and has_penalty_number)
        reason = "penalty_question_requires_penalty_amount"
    if "deadline" in q_concepts:
        has_deadline_phrase = any(x in h_norm for x in ["thoi han", "han nop", "cham nhat", "ngay nop"])
        has_time_value = bool(re.search(
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d+\s*(?:ngay|thang|nam)\b",
            h_norm,
        ))
        accepted = bool(accepted and has_deadline_phrase and has_time_value)
        reason = "deadline_question_requires_deadline_and_duration"
    if "effective_date" in q_concepts:
        has_effective_phrase = any(x in h_norm for x in ["hieu luc", "ap dung tu", "co hieu luc tu"])
        has_time_value = bool(re.search(
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\bngay\s+\d{1,2}\s+thang\s+\d{1,2}\s+nam\s+\d{4}\b",
            h_norm,
        ))
        accepted = bool(accepted and has_effective_phrase and has_time_value)
        reason = "effective_date_requires_effective_phrase_and_date"
    if "signer" in q_concepts:
        has_signer = any(x in h_norm for x in ["nguoi ky", "ky thay", "ky ban hanh", "kt ", "tl "])
        accepted = bool(accepted and has_signer)
        reason = "signer_question_requires_signer_evidence"

    source_policy = _source_governance_policy(question, source)
    if not source_policy.get("accepted"):
        accepted = False
        reason = str(source_policy.get("reason") or "source_governance_rejected")

    return {
        "accepted": bool(accepted),
        "coverage": round(coverage, 3),
        "overlap_count": len(overlap),
        "matched_terms": overlap[:30],
        "phrase_hits": phrase_hits,
        "query_concepts": q_concepts,
        "matched_concepts": concept_overlap,
        "reason": reason,
        "account_codes": account_codes,
        "matched_account_codes": matched_codes,
        "query_legal_identifiers": q_legal,
        "missing_legal_identifiers": missing_legal,
        "answerability_score": answerability,
        "source_policy": source_policy,
        "source_priority": source_policy.get("priority", 0),
        "source_status": source_policy.get("status"),
        "source_effective_from": source_policy.get("effective_from"),
        "source_warnings": source_policy.get("warnings") or [],
    }


def _rag_confidence(sources: List[Dict[str, Any]]) -> str:
    if not sources:
        return "low_without_relevant_sources"
    top = sources[0]
    score = float(top.get("score") or 0)
    coverage = float(top.get("relevance_coverage") or 0)
    phrase_hits = int(top.get("relevance_phrase_hits") or 0)
    concepts = len(top.get("relevance_matched_concepts") or [])
    policy = top.get("source_policy") or _source_governance_policy("", top)
    if policy.get("warnings"):
        return "medium_grounded_source_with_policy_warning"
    if (coverage >= 0.60 and score >= 10) or phrase_hits >= 2 or concepts >= 3:
        return "high_grounded_sources"
    if coverage >= 0.30 and score >= 5:
        return "medium_grounded_sources"
    return "low_weak_sources"



_CURATED_ACCOUNT_USAGE: Dict[str, str] = {
    "111": "Phản ánh tiền mặt hiện có và tình hình thu, chi tiền mặt tại quỹ.",
    "112": "Phản ánh tiền gửi ngân hàng và các khoản thu, chi qua ngân hàng.",
    "121": "Phản ánh chứng khoán mua vào để kinh doanh trong ngắn hạn.",
    "128": "Phản ánh các khoản đầu tư nắm giữ đến ngày đáo hạn như tiền gửi có kỳ hạn hoặc cho vay.",
    "131": "Phản ánh các khoản phải thu của khách hàng từ bán hàng hóa, thành phẩm và cung cấp dịch vụ.",
    "1331": "Phản ánh thuế GTGT đầu vào của hàng hóa, dịch vụ được khấu trừ khi đủ điều kiện.",
    "1332": "Phản ánh thuế GTGT đầu vào của tài sản cố định được khấu trừ khi đủ điều kiện.",
    "136": "Phản ánh các khoản phải thu giữa doanh nghiệp và các đơn vị nội bộ.",
    "138": "Phản ánh các khoản phải thu khác ngoài phải thu khách hàng và phải thu nội bộ.",
    "141": "Phản ánh khoản tạm ứng cho người lao động và tình hình thanh toán tạm ứng.",
    "151": "Phản ánh trị giá hàng mua đã thuộc quyền sở hữu nhưng còn đang đi đường.",
    "152": "Phản ánh nguyên liệu, vật liệu hiện có và tình hình nhập, xuất, tồn kho.",
    "153": "Phản ánh công cụ, dụng cụ hiện có và tình hình nhập, xuất, tồn kho.",
    "154": "Phản ánh chi phí sản xuất, kinh doanh còn dở dang.",
    "155": "Phản ánh thành phẩm hiện có và tình hình nhập, xuất kho thành phẩm.",
    "156": "Phản ánh trị giá hàng hóa hiện có và tình hình nhập, xuất, tồn kho hàng hóa.",
    "157": "Phản ánh trị giá hàng đã gửi đi bán nhưng chưa được xác định là đã bán.",
    "211": "Phản ánh nguyên giá và biến động của tài sản cố định hữu hình.",
    "213": "Phản ánh nguyên giá và biến động của tài sản cố định vô hình.",
    "214": "Phản ánh giá trị hao mòn lũy kế của tài sản cố định và bất động sản đầu tư.",
    "217": "Phản ánh nguyên giá và biến động của bất động sản đầu tư.",
    "228": "Phản ánh các khoản đầu tư góp vốn vào đơn vị khác.",
    "229": "Phản ánh dự phòng tổn thất tài sản như dự phòng giảm giá đầu tư, tồn kho hoặc nợ phải thu khó đòi.",
    "241": "Phản ánh chi phí đầu tư xây dựng cơ bản, mua sắm hoặc sửa chữa lớn tài sản còn dở dang.",
    "242": "Phản ánh chi phí đã phát sinh nhưng được phân bổ dần vào nhiều kỳ kế toán.",
    "243": "Phản ánh tài sản thuế thu nhập hoãn lại.",
    "244": "Phản ánh tài sản đem cầm cố, thế chấp, ký quỹ hoặc ký cược.",
    "331": "Phản ánh các khoản phải trả cho người bán, nhà cung cấp hoặc người nhận thầu.",
    "3331": "Phản ánh thuế GTGT đầu ra phải nộp và tình hình nộp thuế GTGT.",
    "3334": "Phản ánh thuế thu nhập doanh nghiệp phải nộp và đã nộp.",
    "3335": "Phản ánh thuế thu nhập cá nhân đã khấu trừ và phải nộp.",
    "3338": "Phản ánh các loại thuế khác phải nộp ngân sách nhà nước.",
    "334": "Phản ánh tiền lương, tiền công và các khoản khác phải trả người lao động.",
    "335": "Phản ánh chi phí phải trả đã tính vào chi phí kỳ này nhưng chưa thực chi.",
    "336": "Phản ánh các khoản phải trả giữa doanh nghiệp và các đơn vị nội bộ.",
    "338": "Phản ánh các khoản phải trả, phải nộp khác.",
    "3382": "Phản ánh kinh phí công đoàn phải trích và phải nộp.",
    "3383": "Phản ánh bảo hiểm xã hội phải trích và phải nộp.",
    "3384": "Phản ánh bảo hiểm y tế phải trích và phải nộp.",
    "3386": "Phản ánh bảo hiểm thất nghiệp phải trích và phải nộp.",
    "341": "Phản ánh các khoản vay và nợ thuê tài chính.",
    "343": "Phản ánh tình hình phát hành, thanh toán và giá trị trái phiếu phát hành.",
    "344": "Phản ánh tiền nhận ký quỹ, ký cược của tổ chức hoặc cá nhân khác.",
    "352": "Phản ánh các khoản dự phòng phải trả được ghi nhận theo điều kiện áp dụng.",
    "353": "Phản ánh quỹ khen thưởng, phúc lợi và tình hình sử dụng quỹ.",
    "411": "Phản ánh vốn góp của chủ sở hữu và biến động vốn đầu tư.",
    "414": "Phản ánh quỹ đầu tư phát triển của doanh nghiệp.",
    "421": "Phản ánh lợi nhuận sau thuế chưa phân phối hoặc lỗ lũy kế.",
    "511": "Phản ánh doanh thu bán hàng và cung cấp dịch vụ.",
    "515": "Phản ánh doanh thu hoạt động tài chính như lãi tiền gửi, lãi cho vay hoặc cổ tức được chia.",
    "521": "Phản ánh các khoản giảm trừ doanh thu như chiết khấu thương mại, giảm giá hoặc hàng bán bị trả lại.",
    "611": "Phản ánh trị giá hàng mua trong kỳ khi áp dụng phương pháp kiểm kê định kỳ.",
    "621": "Phản ánh chi phí nguyên liệu, vật liệu trực tiếp dùng cho sản xuất.",
    "622": "Phản ánh chi phí nhân công trực tiếp.",
    "623": "Phản ánh chi phí sử dụng máy thi công.",
    "627": "Phản ánh chi phí sản xuất chung tại phân xưởng hoặc bộ phận sản xuất.",
    "631": "Phản ánh giá thành sản xuất khi áp dụng phương pháp kiểm kê định kỳ.",
    "632": "Phản ánh giá vốn của hàng hóa, thành phẩm hoặc dịch vụ đã bán.",
    "635": "Phản ánh chi phí tài chính như lãi vay, lỗ tỷ giá hoặc chiết khấu thanh toán.",
    "641": "Phản ánh chi phí bán hàng như nhân viên bán hàng, quảng cáo, tiếp thị, hoa hồng, vận chuyển giao hàng và dịch vụ mua ngoài phục vụ bán hàng.",
    "642": "Phản ánh chi phí quản lý doanh nghiệp như lương quản lý, văn phòng, dịch vụ mua ngoài, khấu hao bộ phận quản lý và các chi phí quản lý chung.",
    "711": "Phản ánh các khoản thu nhập khác ngoài hoạt động kinh doanh thông thường.",
    "811": "Phản ánh các khoản chi phí khác ngoài hoạt động kinh doanh thông thường.",
    "821": "Phản ánh chi phí thuế thu nhập doanh nghiệp hiện hành và hoãn lại.",
    "911": "Dùng để kết chuyển doanh thu, thu nhập và chi phí nhằm xác định kết quả kinh doanh.",
}


def _curated_account_usage(code: str) -> str:
    return _CURATED_ACCOUNT_USAGE.get(str(code), "")


def _extract_account_definition(text: str, code: str) -> Optional[Dict[str, str]]:
    """Extract the name and usage of one account from a knowledge chunk."""
    raw = str(text or "")
    if not raw or not _text_contains_account_code(raw, code):
        return None

    label_pattern = re.compile(rf"(?:tài\s*khoản|tai\s*khoan|tk)\s*{re.escape(code)}\b", re.I)
    best: Optional[Dict[str, str]] = None

    for match in label_pattern.finditer(raw):
        section = raw[match.start(): match.start() + 1000]
        # Stop before the next account heading/definition.
        remainder = section[match.end() - match.start():]
        next_account = re.search(
            rf"(?:tài\s*khoản|tai\s*khoan|tk)\s*(?!{re.escape(code)}\b)\d{{3,4}}\b",
            remainder,
            flags=re.I,
        )
        if next_account:
            section = section[: (match.end() - match.start()) + next_account.start()]

        compact = re.sub(r"\s+", " ", section).strip(" #\t\r\n-—:")
        if not compact:
            continue

        name = ""
        name_match = re.search(
            rf"(?:tài\s*khoản|tai\s*khoan|tk)\s*{re.escape(code)}\s*[-—:]\s*"
            r"(.+?)(?=\s+(?:dùng|sử dụng|phản ánh)\b|[.?#]|$)",
            compact,
            flags=re.I,
        )
        if name_match:
            name = name_match.group(1).strip(" -—:.;")

        usage = ""
        # Prefer a declarative sentence and ignore a FAQ heading such as
        # "Tài khoản 641 dùng khi nào?".
        direct_pattern = re.compile(
            rf"(?:tài\s*khoản|tai\s*khoan|tk)\s*{re.escape(code)}\s+"
            r"(?:được\s+)?(dùng|sử dụng)\s+(.+?)(?=[.!?](?:\s|$)|$)",
            re.I,
        )
        for usage_match in direct_pattern.finditer(compact):
            tail = usage_match.group(2).strip(" -—:.;")
            if re.fullmatch(r"(?:trong\s+)?(?:trường\s+hợp\s+)?(?:khi\s+)?nào", tail, flags=re.I):
                continue
            if len(tail) >= 8:
                usage = f"Dùng {tail}"
                break

        if not usage:
            generic = re.search(
                r"\b(dùng|sử dụng)\s+(.+?)(?=[.!?](?:\s|$)|$)",
                compact,
                flags=re.I,
            )
            if generic:
                tail = generic.group(2).strip(" -—:.;")
                if not re.fullmatch(r"(?:trong\s+)?(?:trường\s+hợp\s+)?(?:khi\s+)?nào", tail, flags=re.I):
                    usage = f"Dùng {tail}"

        if not usage:
            reflected = re.search(r"\bphản\s+ánh\s+(.+?)(?=[.!?](?:\s|$)|$)", compact, flags=re.I)
            if reflected:
                usage = "Phản ánh " + reflected.group(1).strip(" -—:.;")

        # Some concise chart files write the description directly after the
        # account name without a verb, e.g. "TK 641 — Chi phí bán hàng\nChi
        # phí marketing...".
        if not usage and name_match:
            tail = compact[name_match.end():].strip(" -—:.;")
            tail = re.split(r"\b(?:ví dụ|example)\b", tail, maxsplit=1, flags=re.I)[0].strip()
            first_sentence = re.split(r"[.!?]", tail, maxsplit=1)[0].strip()
            if len(first_sentence) >= 8:
                usage = first_sentence

        quality = (2 if usage else 0) + (1 if name else 0)
        candidate = {
            "name": name,
            "usage": usage,
            "section": compact[:520],
            "quality": str(quality),
        }
        if best is None or int(candidate["quality"]) > int(best["quality"]):
            best = candidate
        if quality >= 3:
            break

    return best


def _build_account_lookup_answer(
    question: str,
    sources: List[Dict[str, Any]],
    base_answer: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Answer explicit TK/account lookups without letting generic PDF text win."""
    codes = _account_codes_from_question(question)
    if not codes:
        return None

    base_sources = base_answer.get("sources") or base_answer.get("knowledge_sources") or []
    answer_blocks: List[str] = []
    citations: List[Dict[str, Any]] = []
    local_source_names: List[str] = []
    found_from_supabase = False

    for code in codes:
        supabase_candidates: List[Dict[str, Any]] = []
        local_candidates: List[Dict[str, Any]] = []

        for src in sources:
            content = str(src.get("content") or src.get("snippet") or "")
            definition = _extract_account_definition(content, code)
            if definition:
                supabase_candidates.append({"definition": definition, "source": src, "kind": "supabase"})

        for src in base_sources:
            content = str(src.get("content") or src.get("snippet") or "")
            definition = _extract_account_definition(content, code)
            if definition:
                local_candidates.append({"definition": definition, "source": src, "kind": "local"})

        # An exact Supabase definition has priority. Otherwise use the curated
        # local accounting knowledge. Never use a generic Supabase paragraph.
        candidates = supabase_candidates or local_candidates
        if not candidates:
            # Last safe fallback for explicit account-code lookups. A question like
            # "Tài khoản 641 được sử dụng trong trường hợp nào?" must not be
            # answered from generic RAG chunks about "tài khoản" in financial
            # statements. If Supabase/local chunks do not contain an exact
            # definition, answer from the curated chart of accounts instead.
            curated_name = str(ACCOUNT_NAMES.get(code) or "").strip()
            if curated_name:
                usage = _curated_account_usage(code) or f"Dùng theo đúng nội dung của tài khoản {code} – {curated_name}; cần đối chiếu hệ thống tài khoản và chính sách kế toán áp dụng của doanh nghiệp."
                answer_blocks.append(f"TK {code} – {curated_name}.\n\n{usage.rstrip('.')}.")
                local_source_names.append("Danh mục tài khoản kế toán nội bộ")
            continue

        # Merge the best name and the fullest usage sentence. Chunk boundaries
        # can truncate one source after "nhân", while a FAQ source contains the
        # complete sentence but omits the formal account name.
        name_candidate = max(
            (c for c in candidates if c["definition"].get("name")),
            key=lambda c: len(str(c["definition"].get("name") or "")),
            default=None,
        )
        usage_candidate = max(
            (c for c in candidates if c["definition"].get("usage")),
            key=lambda c: len(str(c["definition"].get("usage") or "")),
            default=None,
        )
        chosen = usage_candidate or name_candidate
        if chosen is None:
            continue

        name = str((name_candidate or chosen)["definition"].get("name") or "").strip()
        usage = str((usage_candidate or chosen)["definition"].get("usage") or "").strip()

        # The bundled chart is the canonical wording for account lookups. Use
        # retrieved passages for evidence, but never let a truncated PDF/Markdown
        # chunk produce malformed text such as "Chi phí ... quả".
        curated_name = str(ACCOUNT_NAMES.get(code) or "").strip()
        curated_usage = _curated_account_usage(code).strip()
        if curated_name:
            name = curated_name
        if curated_usage:
            usage = curated_usage

        if name and usage:
            block = f"TK {code} – {name}.\n\n{usage.rstrip('.')}."
        elif name:
            block = f"TK {code} – {name}."
        elif usage:
            block = f"TK {code}: {usage.rstrip('.')}."
        else:
            continue
        answer_blocks.append(block)

        if chosen["kind"] == "supabase":
            found_from_supabase = True
            src = chosen["source"]
            definition = chosen["definition"]
            citations.append({
                "index": len(citations) + 1,
                "title": src.get("title"),
                "document_title": _citation_document_title(src),
                "document_id": src.get("document_id"),
                "chunk_id": src.get("chunk_id"),
                "chunk_no": src.get("chunk_no"),
                "heading": src.get("heading"),
                "page": _source_page(src),
                "location": _source_location(src, excerpt=definition.get("section") or ""),
                "legal_location": _extract_structural_location(src, excerpt=definition.get("section") or ""),
                "excerpt": definition.get("section") or "",
            })
        else:
            src = chosen["source"]
            source_name = str(src.get("source") or src.get("title") or "").strip()
            if source_name and source_name not in local_source_names:
                local_source_names.append(source_name)

    if not answer_blocks:
        return None

    answer = "\n\n".join(answer_blocks)
    if not citations and local_source_names:
        citations = [
            _citation_from_local_source(name, index=index)
            for index, name in enumerate(local_source_names[:3], 1)
        ]

    return {
        "answer": answer,
        "citations": citations,
        "answer_mode": "account_lookup_exact",
        "confidence": (
            "high_exact_account_source" if found_from_supabase
            else "medium_curated_account_knowledge"
        ),
    }



def _build_accounting_journal_answer(question: str, base_answer: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create a concise accounting answer before free-form RAG synthesis."""
    if not _is_journal_question(question):
        return None

    if _is_unpaid_purchase_question(question):
        return {
            "answer": (
                "Khi doanh nghiệp mua hàng hóa nhập kho nhưng chưa thanh toán cho người bán:\n\n"
                "- Nợ TK 156: Giá mua hàng hóa chưa có thuế GTGT.\n"
                "- Nợ TK 1331: Thuế GTGT đầu vào được khấu trừ, nếu đủ điều kiện.\n"
                "- Có TK 331: Tổng số tiền phải trả người bán.\n\n"
                "Nếu thuế GTGT không được khấu trừ thì ghi toàn bộ giá thanh toán vào Nợ TK 156 và Có TK 331.\n\n"
                "Đây là bút toán tham khảo; số tiền và việc khấu trừ thuế cần đối chiếu hóa đơn, phiếu nhập kho và chứng từ thực tế."
            ),
            "answer_mode": "accounting_journal_rule",
            "confidence": "high_accounting_rule_engine",
            "rule_id": "PUR_002_OVERRIDE",
        }

    if _is_unpaid_sale_question(question):
        return {
            "answer": (
                "Khi doanh nghiệp bán hàng nhưng chưa thu tiền khách hàng:\n\n"
                "- Nợ TK 131: Tổng số tiền khách hàng phải thanh toán.\n"
                "- Có TK 511: Doanh thu chưa có thuế GTGT.\n"
                "- Có TK 3331: Thuế GTGT đầu ra, nếu thuộc đối tượng chịu thuế.\n\n"
                "Đồng thời ghi nhận giá vốn theo chứng từ xuất kho: Nợ TK 632 / Có TK 156."
            ),
            "answer_mode": "accounting_journal_rule",
            "confidence": "high_accounting_rule_engine",
            "rule_id": "SALES_002_OVERRIDE",
        }

    solver = base_answer.get("solver") or {}
    matched = solver.get("matched_rule") or {}
    if not matched.get("matched"):
        try:
            solver = analyze_transaction(question)
            matched = solver.get("matched_rule") or {}
        except Exception:
            matched = {}
    rule = matched.get("rule") or {}
    debit = str(rule.get("debit_account") or "").strip()
    credit = str(rule.get("credit_account") or "").strip()
    if not (matched.get("matched") and debit and credit):
        return None

    q = _normalized_text(question)
    if any(x in q for x in ["chua thanh toan", "mua chiu", "no nha cung cap", "phai tra nguoi ban"]):
        credit = "331"
    elif any(x in q for x in ["chuyen khoan", "ngan hang", "uy nhiem chi"]):
        credit = "112"
    elif any(x in q for x in ["tien mat", "bang tien mat"]):
        credit = "111"

    category = rule.get("category") or matched.get("category") or "Nghiệp vụ kế toán"
    debit_name = ACCOUNT_NAMES.get(debit) or rule.get("debit_name") or "tài khoản ghi Nợ"
    credit_name = ACCOUNT_NAMES.get(credit) or rule.get("credit_name") or "tài khoản ghi Có"
    lines = [f"Nhận diện nghiệp vụ: {category}.", "", f"- Nợ TK {debit}: {debit_name}."]
    has_vat = any(x in q for x in ["vat", "gtgt", "thue gia tri gia tang"])
    if has_vat and debit not in {"3331", "3334", "3335", "334", "338", "341", "411", "421", "911"}:
        vat_account = "1332" if debit in {"211", "213", "217", "241"} else "1331"
        lines.append(f"- Nợ TK {vat_account}: Thuế GTGT đầu vào được khấu trừ, nếu đủ điều kiện.")
    lines.append(f"- Có TK {credit}: {credit_name}.")

    tax_notes = rule.get("tax_notes") or []
    risk_flags = rule.get("risk_flags") or []
    notes: List[str] = []
    if isinstance(tax_notes, str):
        notes.append(tax_notes)
    else:
        notes.extend(str(x) for x in tax_notes if x)
    if isinstance(risk_flags, str):
        notes.append(risk_flags)
    else:
        notes.extend(str(x) for x in risk_flags if x)
    if notes:
        lines.extend(["", "Lưu ý: " + " ".join(notes[:2])])
    lines.extend([
        "",
        "Bút toán trên là bản nháp; cần xác định giá chưa thuế, thuế GTGT, tổng thanh toán và kiểm tra hóa đơn/chứng từ trước khi ghi sổ.",
    ])
    return {
        "answer": "\n".join(lines),
        "answer_mode": "accounting_journal_rule",
        "confidence": "medium_accounting_rule_engine",
        "rule_id": rule.get("rule_id"),
    }


def _journal_support_citations(question: str, sources: List[Dict[str, Any]], max_items: int = 3) -> List[Dict[str, Any]]:
    excerpts = _ranked_excerpts(question, sources, max_items=max_items) if sources else []
    citations: List[Dict[str, Any]] = []
    for idx, item in enumerate(excerpts, 1):
        src = item.get("source") or {}
        citations.append({
            "index": idx,
            "title": src.get("title"),
            "document_title": _citation_document_title(src),
            "document_id": src.get("document_id"),
            "chunk_id": src.get("chunk_id"),
            "chunk_no": src.get("chunk_no"),
            "heading": src.get("heading"),
            "page": _source_page(src),
            "location": _source_location(src, excerpt=item.get("text") or ""),
            "legal_location": _extract_structural_location(src, excerpt=item.get("text") or ""),
            "excerpt": item.get("text"),
            "source_status": src.get("source_status") or _source_governance_policy(question, src).get("status"),
            "effective_from": src.get("source_effective_from") or _source_governance_policy(question, src).get("effective_from"),
            "source_warnings": src.get("source_warnings") or _source_governance_policy(question, src).get("warnings") or [],
            "source_authority": (_source_knowledge_metadata(src).get("authority") or "curated_internal"),
        })
    return citations


def _extract_structural_location(src: Dict[str, Any], excerpt: str = "") -> str:
    """Best-effort legal citation: Điều/Khoản/Điểm/Phụ lục + page/chunk.

    This does not require a schema migration. It derives legal locations from
    the chunk heading/content and the selected excerpt.
    """
    heading = str(src.get("heading") or "")
    content = str(src.get("content") or src.get("snippet") or "")
    text = normalize_extracted_text_for_rag("\n".join([heading, content]))
    target_pos = len(text)
    if excerpt:
        needle = _clean_rag_text(excerpt, max_len=90)[:70].strip()
        if needle:
            found = text.find(needle)
            if found >= 0:
                target_pos = found
    window = text[: min(len(text), target_pos + 700)]
    local_window = text[max(0, target_pos - 500): min(len(text), target_pos + 700)]

    # Prefer the underlying article being amended (e.g. "Sửa đổi, bổ sung Điều 6")
    # because users expect citations like Điều 6, not only Điều 1 of the amending circular.
    amended = list(re.finditer(r"(?:Sửa đổi|Bổ sung|Sửa đổi,\s*bổ sung)[^\n]{0,80}?((?:khoản\s+\d+\s+)?Điều\s+\d+)", window, flags=re.I))
    if amended:
        loc = amended[-1].group(1).strip()
        return re.sub(r"\s+", " ", loc) + " (được sửa đổi, bổ sung)"

    patterns = [
        r"((?:điểm\s+[a-zđ]\s+)?khoản\s+\d+\s+Điều\s+\d+)",
        r"(khoản\s+\d+\s+Điều\s+\d+)",
        r"(Điều\s+\d+[^\n\"]{0,120})",
        r"(PHỤ\s+LỤC\s+[IVXLC\d]+[^\n]{0,120})",
        r"(Mẫu\s+số\s+[A-Z0-9\-/ ]{2,40})",
        r"(Mã\s+số\s+\d+)",
    ]
    matches: List[str] = []
    for pattern in patterns:
        for m in re.finditer(pattern, window, flags=re.I):
            matches.append(m.group(1).strip())
        if matches:
            break
    if not matches:
        for pattern in patterns:
            m = re.search(pattern, local_window, flags=re.I)
            if m:
                matches.append(m.group(1).strip())
                break
    if matches:
        loc = re.sub(r"\s+", " ", matches[-1])
        loc = loc.strip(" .;:")
        if len(loc) > 130:
            loc = loc[:127].rstrip() + "…"
        return loc
    return ""


def _candidate_score(question: str, candidate: str) -> int:
    account_codes = _account_codes_from_question(question)
    if account_codes and not any(_text_contains_account_code(candidate, code) for code in account_codes):
        return 0

    q_tokens = set(_tokens(question))
    c_tokens = set(_tokens(candidate))
    if not q_tokens or not c_tokens:
        return 0
    qn = " ".join(q_tokens)
    cn = _normalized_text(candidate)
    score = len(q_tokens & c_tokens)

    # Intent bonuses for Vietnamese accounting/legal Q&A.
    hint_pairs = [
        (("hieu luc", "ap dung"), ("hieu luc", "ap dung", "ngay ky", "01 01 2026"), 10),
        (("thoi han", "nop", "cham nhat", "bao nhieu ngay"), ("cham nhat", "90 ngay", "ket thuc ky ke toan"), 12),
        (("sua doi", "thong tu nao", "thong tu"), ("202 2014 tt btc", "sua doi bo sung"), 8),
        (("loi ich co dong khong kiem soat", "ma so", "chi tieu"), ("loi ich co dong khong kiem soat", "ma so 429", "von chu so huu"), 12),
        (("loi the thuong mai", "ma so 279"), ("loi the thuong mai", "ma so 279", "tai san"), 12),
        (("ket qua kinh doanh", "cong ty con", "quyen kiem soat", "ban cong ty con", "mat quyen kiem soat"), ("cong ty me nam quyen kiem soat", "cham dut quyen kiem soat"), 12),
        (("bo sung", "chi tieu", "bao cao tai chinh hop nhat"), ("bo sung chi tieu", "ma so", "bao cao"), 8),
        (("khau hao", "tscd", "bdsdt"), ("khau hao tscd", "bdsdt", "ma so 02"), 8),
        (("du phong", "trich lap", "hoan nhap"), ("cac khoan du phong", "ma so 03", "trich lap", "hoan nhap"), 8),
        (("co tuc", "loi nhuan duoc chia"), ("thu lai tien cho vay", "co tuc", "loi nhuan duoc chia", "ma so 27"), 8),
    ]
    for q_hints, c_hints, bonus in hint_pairs:
        if any(h in qn for h in q_hints) and any(h in cn for h in c_hints):
            score += bonus
    if _normalized_text(question) and _normalized_text(question) in cn:
        score += 6
    return score


def _ranked_excerpts(question: str, sources: List[Dict[str, Any]], max_items: int = 3) -> List[Dict[str, Any]]:
    ranked: List[Dict[str, Any]] = []
    for src_index, src in enumerate(sources[: max(6, max_items)], 1):
        content = src.get("content") or src.get("snippet") or ""
        for candidate in _split_answer_candidates(content):
            candidate_norm = _normalized_text(candidate)
            question_norm = _normalized_text(question)
            if candidate.strip().endswith("?") or (candidate_norm and candidate_norm == question_norm):
                continue
            score = _candidate_score(question, candidate)
            if score <= 0:
                continue
            ranked.append({
                "score": score + max(0, 6 - src_index),
                "text": _clean_rag_text(candidate, max_len=520),
                "source": src,
            })
    ranked.sort(key=lambda x: (x["score"], len(x["text"])), reverse=True)

    selected: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in ranked:
        normalized = _normalized_text(item["text"][:220])
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        selected.append(item)
        if len(selected) >= max_items:
            break

    # Never dump a whole chunk when no sentence can answer the question.
    # Returning an empty list is safer: the caller will explicitly say that the
    # uploaded documents do not contain enough evidence.
    return selected


def _direct_answer_from_excerpts(question: str, excerpts: List[Dict[str, Any]]) -> Optional[str]:
    qn = _normalized_text(question)

    def first_matching(*needles: str, require_all: bool = False) -> Optional[str]:
        for excerpt in excerpts:
            text = str(excerpt.get("text") or "")
            en = _normalized_text(text)
            matched = all(n in en for n in needles) if require_all else any(n in en for n in needles)
            if matched:
                return text
        return None

    account_codes = _account_codes_from_question(question)
    if account_codes:
        for code in account_codes:
            for excerpt in excerpts:
                text = str(excerpt.get("text") or "")
                if _text_contains_account_code(text, code):
                    return text
        return None

    concepts = set(_concepts_in_text(question))
    if {"vat_input", "vat_deduction"} <= concepts:
        for excerpt in excerpts:
            en = _normalized_text(excerpt.get("text") or "")
            if any(x in en for x in ["vat dau vao", "gtgt dau vao", "thue gtgt dau vao"]) and any(
                x in en for x in ["hoa don", "chung tu", "dieu kien", "khau tru"]
            ):
                return excerpt.get("text")
    if "auto_post" in concepts:
        match = first_matching("khong tu ghi so", "chua co xac nhan", "can xac nhan", "ke toan xac nhan")
        if match:
            return match
    if "invoice_missing" in concepts:
        match = first_matching("thieu hoa don", "khong co hoa don", "chua co hoa don")
        if match:
            return match
    if "effective_date" in concepts:
        match = first_matching("hieu luc", "ap dung tu")
        if match:
            return match
    if "deadline" in concepts:
        match = first_matching("thoi han", "cham nhat", "han nop")
        if match:
            return match
    if "penalty" in concepts:
        # Relevance gating already requires a penalty amount.
        match = first_matching("muc phat", "xu phat", "phat tien")
        if match:
            return match
    if "signer" in concepts:
        match = first_matching("nguoi ky", "ky ban hanh", "ky thay")
        if match:
            return match

    # For ordinary short questions, return the highest-ranked sentence only
    # when it has a meaningful score. This is safer than dumping several chunks.
    if excerpts and float(excerpts[0].get("score") or 0) >= 3:
        return str(excerpts[0].get("text") or "")
    return None


def _needs_accounting_human_review_warning(question: str) -> bool:
    q = _normalized_text(question)
    risk_terms = [
        "hach toan", "dinh khoan", "ghi so", "quyet toan", "ke khai", "nop thue",
        "xu ly nghiep vu", "chung tu", "hoa don", "chi phi", "khau tru", "tndn",
        "gtgt", "luong", "bhxh", "tai san", "khau hao", "cong no", "bao cao tai chinh",
    ]
    lookup_terms = ["thong tu nao", "sua doi", "hieu luc", "trang", "phu luc", "mau so", "ma so", "thoi han"]
    return any(t in q for t in risk_terms) and not ("thong tu" in q and any(t in q for t in lookup_terms))


def _build_rag_answer_from_sources(question: str, sources: List[Dict[str, Any]], *, storage_label: str, history: str = "", answer_mode: str = "auto", conflict_warnings: Optional[List[str]] = None) -> Dict[str, Any]:
    formula = _try_formula_answer(question)
    if formula:
        return formula
    selected_mode = _answer_mode_from_question(question, answer_mode)
    long_mode = _wants_long_answer(question, selected_mode)
    excerpts = _ranked_excerpts(question, sources, max_items=6 if long_mode else 3)
    citations: List[Dict[str, Any]] = []
    for idx, item in enumerate(excerpts, 1):
        src = item.get("source") or {}
        citations.append({
            "index": idx,
            "title": src.get("title"),
            "document_title": _citation_document_title(src),
            "document_id": src.get("document_id"),
            "chunk_id": src.get("chunk_id"),
            "chunk_no": src.get("chunk_no"),
            "heading": src.get("heading"),
            "page": _source_page(src),
            "location": _source_location(src, excerpt=item.get("text") or ""),
            "legal_location": _extract_structural_location(src, excerpt=item.get("text") or ""),
            "excerpt": item.get("text"),
        })

    if not excerpts:
        return {
            "answer": "Chưa tìm thấy đoạn tài liệu phù hợp trong RAG để trả lời chắc chắn. Hãy thử hỏi rõ hơn hoặc kiểm tra lại việc index tài liệu.",
            "citations": [],
            "answer_mode": "no_rag_source",
        }

    if selected_mode == "source_only":
        return {
            "answer": _source_only_answer(question, sources, citations),
            "citations": citations,
            "answer_mode": "source_only",
        }

    direct = _direct_answer_from_excerpts(question, excerpts)
    if direct and not long_mode:
        citations = citations[:1]
        legal = citations[0].get("legal_location") if citations else ""
        prefix = f"Theo {legal}, " if legal else ""
        answer_lines = [
            f"Dựa trên tài liệu đã nạp trong {storage_label}, câu trả lời là:",
            "",
            f"{prefix}{_clean_rag_text(direct, max_len=700)} [1]",
        ]
    elif long_mode:
        answer_lines = [
            f"Dựa trên tài liệu đã nạp trong {storage_label}, tớ tổng hợp câu trả lời chi tiết như sau:",
            "",
            "1. Kết luận nhanh",
        ]
        if direct:
            answer_lines.append(f"- {_clean_rag_text(direct, max_len=700)} [1]")
        else:
            answer_lines.append(f"- Nội dung liên quan nhất nằm trong {len(excerpts)} đoạn RAG dưới đây; cần đọc cùng nguồn để tránh hiểu sai phạm vi áp dụng.")
        answer_lines.extend(["", "2. Căn cứ chính trong tài liệu"] )
        for idx, item in enumerate(excerpts, 1):
            src = item.get("source") or {}
            loc = _source_location(src, excerpt=item.get("text") or "")
            answer_lines.append(f"- [{idx}] {loc}: {_clean_rag_text(item.get('text'), max_len=620)}")
        answer_lines.extend([
            "",
            "3. Cách hiểu / cách áp dụng",
            "- Ưu tiên áp dụng đúng phạm vi của văn bản được nạp trong RAG, không suy rộng sang nghiệp vụ không có căn cứ trong nguồn.",
            "- Nếu câu hỏi là nghiệp vụ thực tế, cần ghép thêm chứng từ, chính sách kế toán nội bộ, kỳ kế toán và đối tượng liên quan trước khi đưa ra bút toán cuối cùng.",
        ])
        answer_lines.extend(_build_accounting_workflow_section(question, citations, selected_mode))
    else:
        answer_lines = [
            f"Dựa trên tài liệu đã nạp trong {storage_label}, các ý liên quan nhất là:",
            "",
        ]
        for idx, item in enumerate(excerpts, 1):
            src = item.get("source") or {}
            legal = _extract_structural_location(src, excerpt=item.get("text") or "")
            legal_prefix = f"{legal}: " if legal else ""
            answer_lines.append(f"{idx}. {legal_prefix}{_clean_rag_text(item.get('text'), max_len=560)} [{idx}]")

    source_policy_warnings: List[str] = []
    for citation in citations:
        for warning in citation.get("source_warnings") or []:
            if warning not in source_policy_warnings:
                source_policy_warnings.append(warning)
    if source_policy_warnings:
        answer_lines.extend(["", "Lưu ý về hiệu lực và độ đầy đủ của nguồn:"])
        for warning in source_policy_warnings:
            answer_lines.append(f"- {warning}")

    if conflict_warnings:
        answer_lines.extend(["", "Cảnh báo văn bản / conflict checker:"])
        for w in conflict_warnings:
            answer_lines.append(f"- {w}")

    if _needs_accounting_human_review_warning(question):
        answer_lines.extend([
            "",
            "Lưu ý: đây là câu trả lời nháp theo tài liệu RAG; trước khi ghi sổ/quyết toán vẫn cần đối chiếu chứng từ, chính sách công ty và người kế toán phụ trách duyệt.",
        ])
    return {
        "answer": "\n".join(answer_lines),
        "citations": citations,
        "answer_mode": selected_mode,
    }


def _hybrid_chunk_score(query: str, chunk: Dict[str, Any]) -> Dict[str, Any]:
    q_tokens = _meaningful_query_tokens(query)
    q_counter = Counter(q_tokens)
    haystack = " ".join([
        str(chunk.get("title") or ""),
        str(chunk.get("heading") or ""),
        str(chunk.get("content") or ""),
    ])
    h_norm = _normalized_text(haystack)
    c_tokens_list = _tokens(haystack)
    c_tokens = set(c_tokens_list)
    c_counter = Counter(c_tokens_list)

    overlap_terms = [t for t in q_counter if t in c_tokens]
    lexical = sum(min(q_counter[t], c_counter.get(t, 1)) for t in overlap_terms)
    coverage_ratio = len(set(overlap_terms)) / max(1, len(set(q_tokens)))
    coverage = coverage_ratio * 10

    phrase_bonus = 0
    for n in (5, 4, 3, 2):
        for i in range(max(0, len(q_tokens) - n + 1)):
            phrase = " ".join(q_tokens[i:i+n])
            if len(phrase) >= 7 and phrase in h_norm:
                phrase_bonus += min(8, n * 2)
                break

    account_code_bonus = 0
    for code in _account_codes_from_question(query):
        if _text_contains_account_code(haystack, code):
            account_code_bonus += 30

    legal_bonus = 0
    q_legal = _extract_legal_identifiers(query)
    h_legal = set(_extract_legal_identifiers(haystack))
    for identifier in q_legal:
        if identifier in h_legal:
            legal_bonus += 20

    q_concepts = set(_concepts_in_text(query))
    h_concepts = set(_concepts_in_text(haystack))
    concept_matches = sorted(q_concepts & h_concepts)
    concept_bonus = 4 * len(concept_matches)

    title_heading = _normalized_text(" ".join([str(chunk.get("title") or ""), str(chunk.get("heading") or "")]))
    title_bonus = 0
    for token in set(q_tokens):
        if len(token) >= 3 and token in title_heading:
            title_bonus += 1.5

    source_policy = _source_governance_policy(query, chunk)
    source_priority = float(source_policy.get("priority") or 0)
    score = lexical + coverage + phrase_bonus + account_code_bonus + legal_bonus + concept_bonus + title_bonus + source_priority
    return {
        "score": round(float(score), 3),
        "lexical": lexical,
        "coverage": round(float(coverage), 3),
        "coverage_ratio": round(float(coverage_ratio), 3),
        "phrase_bonus": phrase_bonus,
        "account_code_bonus": account_code_bonus,
        "legal_bonus": legal_bonus,
        "concept_bonus": concept_bonus,
        "title_bonus": round(title_bonus, 3),
        "source_priority": source_priority,
        "source_policy": source_policy,
        "matched_concepts": concept_matches,
        "matched_terms": sorted(overlap_terms)[:30],
    }


def search_documents_supabase(
    query: str,
    workspace_id: str = "default",
    source_types: Optional[List[str]] = None,
    limit: int = 6,
    history: str = "",
) -> Dict[str, Any]:
    require_supabase_active()
    client = SupabaseRAGClient()
    retrieval_query = _expand_query_text(query, history=history)
    # Lightweight hybrid lexical/semantic search in Python. This keeps V101
    # independent of pgvector, while still improving long Vietnamese questions.
    params: Dict[str, Any] = {"select": "*", "workspace_id": f"eq.{workspace_id}", "order": "created_at.desc", "limit": "3000"}
    if source_types:
        joined = ",".join(source_types)
        params["source_type"] = f"in.({joined})"
    chunks = client.rest("GET", RAG_CHUNKS_TABLE, params=params) or []
    doc_ids = sorted({c.get("document_id") for c in chunks if c.get("document_id")})
    active_docs: Dict[str, Dict[str, Any]] = {}
    if doc_ids:
        safe_ids = ",".join(doc_ids[:1000])
        docs = client.rest("GET", RAG_DOCUMENTS_TABLE, params={"select": "document_id,status,metadata", "document_id": f"in.({safe_ids})"}) or []
        active_docs = {d.get("document_id"): d for d in docs if d.get("status") == "active"}

    results: List[Dict[str, Any]] = []
    for chunk in chunks:
        if chunk.get("document_id") not in active_docs:
            continue
        score_chunk = dict(chunk)
        score_chunk["metadata"] = (active_docs.get(chunk.get("document_id")) or {}).get("metadata", {})
        breakdown = _hybrid_chunk_score(retrieval_query, score_chunk)
        score = float(breakdown["score"])
        if score <= 0:
            continue
        content = chunk.get("content") or ""
        result = {
            "score": score,
            "score_breakdown": breakdown,
            "retrieval_mode": "hybrid_lexical_semantic_v54",
            "chunk_id": chunk.get("chunk_id"),
            "document_id": chunk.get("document_id"),
            "title": chunk.get("title"),
            "source_type": chunk.get("source_type"),
            "section": chunk.get("section"),
            "chunk_no": chunk.get("chunk_no"),
            "heading": chunk.get("heading"),
            "page": _source_page({"content": content, "heading": chunk.get("heading")}),
            "location": _source_location(chunk, excerpt=content[:260]),
            "snippet": _clean_rag_text(content, max_len=700),
            "content": content,
            "metadata": (active_docs.get(chunk.get("document_id")) or {}).get("metadata", {}),
        }
        results.append(result)

    # Rerank top candidates by sentence-level answerability, then reject chunks
    # that only match generic words such as "doanh nghiệp" or "hàng hóa".
    relevant_results: List[Dict[str, Any]] = []
    rejected_low_relevance = 0
    for r in results:
        excerpts = _ranked_excerpts(query, [r], max_items=1)
        if excerpts:
            r["answerability_score"] = excerpts[0].get("score", 0)
            r["score"] = round(float(r["score"]) + float(r["answerability_score"]) * 0.6, 3)
        else:
            r["answerability_score"] = 0
        relevance = _source_relevance_metrics(query, r)
        r["relevance_coverage"] = relevance["coverage"]
        r["relevance_overlap_count"] = relevance["overlap_count"]
        r["relevance_matched_terms"] = relevance["matched_terms"]
        r["relevance_phrase_hits"] = relevance.get("phrase_hits", 0)
        r["relevance_query_concepts"] = relevance.get("query_concepts") or []
        r["relevance_matched_concepts"] = relevance.get("matched_concepts") or []
        r["relevance_reason"] = relevance["reason"]
        r["query_account_codes"] = relevance.get("account_codes") or []
        r["matched_account_codes"] = relevance.get("matched_account_codes") or []
        r["query_legal_identifiers"] = relevance.get("query_legal_identifiers") or []
        r["missing_legal_identifiers"] = relevance.get("missing_legal_identifiers") or []
        r["source_policy"] = relevance.get("source_policy") or {}
        r["source_priority"] = relevance.get("source_priority", 0)
        r["source_status"] = relevance.get("source_status")
        r["source_effective_from"] = relevance.get("source_effective_from")
        r["source_warnings"] = relevance.get("source_warnings") or []
        if relevance["accepted"]:
            relevant_results.append(r)
        else:
            rejected_low_relevance += 1

    # Relevance must dominate authority. Authority is a quality tie-breaker, not
    # permission for an unrelated official/legal paragraph to outrank an exact
    # internal playbook passage. The policy weight is already included in score.
    relevant_results.sort(
        key=lambda r: (
            float(r.get("score") or 0),
            float(r.get("answerability_score") or 0),
            float(r.get("relevance_coverage") or 0),
            float(r.get("source_priority") or 0),
        ),
        reverse=True,
    )
    return {
        "version": V101_VERSION,
        "storage_backend": "supabase",
        "query": query,
        "retrieval_query": retrieval_query,
        "workspace_id": workspace_id,
        "results": relevant_results[:limit],
        "count": len(relevant_results[:limit]),
        "total_candidates": len(results),
        "relevant_candidates": len(relevant_results),
        "rejected_low_relevance": rejected_low_relevance,
        "retrieval_mode": "grounded_hybrid_v102_strict_relevance_answerability",
    }


def _build_curated_accounting_knowledge_answer(question: str) -> Optional[Dict[str, Any]]:
    """Structured answers for workflows, comparisons and checklists."""
    q = _normalized_text(question)
    concepts = set(_concepts_in_text(question))

    # Current-law guardrails for the bundled V107 knowledge set. These common
    # questions should not depend on a lucky chunk boundary or stale uploaded
    # note. The detailed source text remains available for citations.
    if any(x in q for x in ["thong tu 58 2026", "58 2026 tt btc", "tt 58 2026"]):
        effective = date(2026, 7, 1)
        today = date.today()
        if any(x in q for x in ["hieu luc", "ap dung", "tu ngay nao", "hien nay", "da co hieu luc", "khi nao"]):
            status_sentence = (
                "Tính đến hôm nay, Thông tư này chưa có hiệu lực."
                if today < effective
                else "Tính đến hôm nay, Thông tư này đã có hiệu lực."
            )
            return {
                "answer": (
                    "Thông tư 58/2026/TT-BTC có hiệu lực từ ngày 01/07/2026 và áp dụng cho các năm tài chính bắt đầu từ hoặc sau ngày này. "
                    f"{status_sentence}\n\n"
                    "Thông tư hướng dẫn chế độ kế toán cho doanh nghiệp siêu nhỏ. Khi áp dụng cần kiểm tra doanh nghiệp có đúng đối tượng và năm tài chính có bắt đầu trong thời gian hiệu lực hay không."
                ),
                "answer_mode": "legal_effective_date_guarded",
                "confidence": "high_named_legal_source",
                "source_titles": ["knowledge_base/global/accounting/thong_tu_58_2026_dnsn.md"],
                "source_policy_warnings": ["Bản Markdown đi kèm là bản trích xuất một phần; cần đối chiếu bản chính thức khi xử lý điều khoản chi tiết."],
            }

    vat_input_question = (
        ("vat dau vao" in q or "gtgt dau vao" in q)
        and any(x in q for x in ["khau tru", "dieu kien", "duoc khau tru"])
    )
    if vat_input_question:
        return {
            "answer": (
                "Để xem xét khấu trừ VAT đầu vào, cần kiểm tra đồng thời:\n\n"
                "1. Có hóa đơn GTGT hoặc chứng từ nộp thuế hợp pháp.\n"
                "2. Hàng hóa, dịch vụ mua vào phục vụ hoạt động sản xuất, kinh doanh hàng hóa/dịch vụ chịu thuế GTGT.\n"
                "3. Với hàng hóa, dịch vụ mua vào từng lần có giá trị từ 5.000.000 đồng trở lên, đã gồm VAT, phải có chứng từ thanh toán không dùng tiền mặt, trừ trường hợp pháp luật có quy định ngoại lệ.\n"
                "4. Thông tin hóa đơn, hợp đồng, nghiệm thu/nhập kho và chứng từ thanh toán phải thống nhất.\n\n"
                "AI chỉ nên gợi ý TK 1331/1332 khi hồ sơ đủ căn cứ; nếu thiếu hóa đơn hoặc chưa rõ phương thức thanh toán thì cần đánh dấu chờ review."
            ),
            "answer_mode": "current_vat_input_conditions",
            "confidence": "high_curated_current_tax_knowledge",
            "source_titles": ["knowledge_base/vat_hoa_don.md"],
        }

    tndn_question = any(x in q for x in ["chi phi duoc tru", "tndn", "thu nhap doanh nghiep"])
    raw_ascii = "".join(
        ch for ch in unicodedata.normalize("NFKD", str(question or "").lower())
        if not unicodedata.combining(ch)
    ).replace("đ", "d")
    amount_million_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*trieu\b", raw_ascii)
    amount_million = float(amount_million_match.group(1).replace(",", ".")) if amount_million_match else None
    cash_risk = (
        any(x in q for x in ["tien mat", "thanh toan bang tien mat"])
        and amount_million is not None
        and amount_million >= 5
    )
    if tndn_question and ("dieu kien" in q or "duoc tru" in q or cash_risk):
        extra = (
            "\n\nVới tình huống thanh toán tiền mặt từ 5 triệu đồng trở lên cho một lần mua, đây là dấu hiệu rủi ro: khoản chi có thể không đáp ứng điều kiện thanh toán không dùng tiền mặt. Cần kiểm tra ngoại lệ và hồ sơ thực tế trước khi kết luận."
            if cash_risk else ""
        )
        return {
            "answer": (
                "Một khoản chi thường được xem xét là chi phí được trừ khi tính thuế TNDN khi:\n\n"
                "1. Khoản chi thực tế phát sinh và liên quan đến hoạt động sản xuất, kinh doanh.\n"
                "2. Có hóa đơn, chứng từ hợp pháp.\n"
                "3. Với từng lần mua hàng hóa, dịch vụ có giá trị từ 5.000.000 đồng trở lên, đã gồm VAT, phải có chứng từ thanh toán không dùng tiền mặt, trừ trường hợp được pháp luật loại trừ.\n"
                "4. Hồ sơ có thể giải trình được mục đích, đối tượng, nội dung và người phê duyệt."
                + extra
            ),
            "answer_mode": "current_tndn_deductibility_conditions",
            "confidence": "high_curated_current_tax_knowledge",
            "source_titles": ["knowledge_base/global/legal/chi_phi_duoc_tru.md"],
        }

    if any(x in q for x in ["laptop", "may tinh", "thiet bi van phong"]) and any(x in q for x in ["18 trieu", "duoi 30 trieu", "co phai tai san co dinh", "tscd", "hach toan"]):
        return {
            "answer": (
                "Nếu laptop có nguyên giá 18 triệu đồng thì riêng tiêu chí giá trị chưa đạt ngưỡng 30 triệu đồng để ghi nhận là tài sản cố định hữu hình. Thông thường doanh nghiệp xem xét ghi nhận là công cụ dụng cụ hoặc chi phí trả trước.\n\n"
                "Bút toán tham khảo khi mua có VAT đủ điều kiện:\n"
                "- Nợ TK 153 hoặc 242: giá chưa VAT.\n"
                "- Nợ TK 1331: VAT đầu vào được khấu trừ.\n"
                "- Có TK 111/112/331: theo phương thức thanh toán.\n\n"
                "Khi phân bổ: Nợ 641 nếu dùng cho bán hàng, Nợ 642 nếu dùng cho quản lý, hoặc Nợ 627 nếu dùng cho sản xuất; Có 242. Cần xác định thời gian sử dụng, ngày đưa vào dùng, bộ phận sử dụng và chính sách phân bổ của doanh nghiệp."
            ),
            "answer_mode": "fixed_asset_ccdc_classification",
            "confidence": "high_curated_accounting_knowledge",
            "source_titles": [
                "knowledge_base/global/legal/tai_san_co_dinh.md",
                "knowledge_base/global/accounting/cong_cu_dung_cu.md",
            ],
        }

    if "procedure" in concepts and any(x in q for x in ["giao dich", "ghi nhan", "nguoi dung", "ke toan truong", "ghi so"]):
        return {
            "answer": (
                "Quy trình ghi nhận giao dịch kế toán đề xuất:\n\n"
                "1. Người dùng nhập mô tả giao dịch, số tiền, ngày giao dịch, phương thức thanh toán và chứng từ.\n"
                "2. Hệ thống xác định bản chất nghiệp vụ: mua, bán, thu, chi, công nợ, tài sản, lương hoặc thuế.\n"
                "3. AI đề xuất tài khoản Nợ/Có và xử lý VAT nếu có.\n"
                "4. AI kiểm tra rủi ro: thiếu hóa đơn, sai phương thức thanh toán, thiếu dữ liệu hoặc nghiệp vụ nhạy cảm.\n"
                "5. Kế toán kiểm tra và xác nhận hoặc sửa bút toán nháp.\n"
                "6. Hệ thống lưu bút toán ở trạng thái chờ duyệt.\n"
                "7. Kế toán trưởng/người có thẩm quyền duyệt rồi mới ghi sổ.\n\n"
                "AI không được tự ghi sổ khi chưa có xác nhận."
            ),
            "answer_mode": "accounting_workflow",
            "confidence": "high_curated_internal_process",
            "source_titles": ["knowledge_base/quy_trinh_ke_toan_noi_bo.md", "knowledge_base/ke_toan_co_ban.md"],
        }

    if {"fixed_asset", "tools", "prepaid"}.issubset(concepts) or all(x in q for x in ["tai san co dinh", "cong cu dung cu", "chi phi tra truoc"]):
        return {
            "answer": (
                "So sánh ngắn:\n\n"
                "- Tài sản cố định: tài sản đáp ứng điều kiện ghi nhận theo chính sách áp dụng; ghi nhận vào TK 211/213 và trích khấu hao qua TK 214.\n"
                "- Công cụ dụng cụ: chưa đủ điều kiện ghi nhận TSCĐ; khi mua có thể ghi TK 153, sau đó xuất dùng và theo dõi phân bổ.\n"
                "- Chi phí trả trước: khoản chi đã phát sinh nhưng liên quan nhiều kỳ; ghi TK 242 và phân bổ dần vào 627/641/642 tùy bộ phận sử dụng.\n\n"
                "Điểm phân biệt chính là điều kiện ghi nhận tài sản, thời gian hưởng lợi và cách phân bổ/khấu hao."
            ),
            "answer_mode": "accounting_comparison",
            "confidence": "high_curated_accounting_knowledge",
            "source_titles": ["knowledge_base/accounting_full_playbook_v85.md"],
        }

    if "cong cu dung cu" in q and "phan bo" in q and any(x in q for x in ["quan ly", "bo phan quan ly"]):
        return {
            "answer": (
                "Khi phân bổ công cụ dụng cụ cho bộ phận quản lý doanh nghiệp:\n\n"
                "- Nợ TK 642: Chi phí quản lý doanh nghiệp.\n"
                "- Có TK 242: Chi phí trả trước.\n\n"
                "Nếu CCDC vẫn đang theo dõi ở TK 153 thì trước hết cần thực hiện bước xuất dùng/chuyển sang theo dõi phân bổ theo chính sách của doanh nghiệp."
            ),
            "answer_mode": "accounting_journal_rule",
            "confidence": "high_curated_accounting_knowledge",
            "source_titles": ["knowledge_base/accounting_full_playbook_v85.md"],
        }

    if "chi phi duoc tru" in q and ("vat dau vao" in q or "khau tru" in q):
        return {
            "answer": (
                "Để đồng thời xem xét chi phí được trừ và khấu trừ VAT đầu vào, cần kiểm tra tối thiểu:\n\n"
                "1. Khoản chi thực tế phát sinh và liên quan đến hoạt động kinh doanh.\n"
                "2. Có hóa đơn/chứng từ hợp lệ.\n"
                "3. Hàng hóa, dịch vụ phục vụ hoạt động chịu thuế GTGT để xem xét khấu trừ VAT.\n"
                "4. Đáp ứng điều kiện thanh toán theo quy định áp dụng.\n"
                "5. Hồ sơ thống nhất giữa hợp đồng/đề nghị mua, nghiệm thu hoặc nhập kho, hóa đơn và chứng từ thanh toán.\n\n"
                "Cần đánh giá riêng điều kiện khấu trừ VAT và điều kiện chi phí được trừ; không tự động coi hai kết luận là giống nhau."
            ),
            "answer_mode": "tax_conditions_combined",
            "confidence": "high_curated_tax_knowledge",
            "source_titles": ["knowledge_base/vat_hoa_don.md", "knowledge_base/global/legal/chi_phi_duoc_tru.md"],
        }

    if "laptop" in q and "ban hang" in q and "quan ly" in q and "phan bo" in q:
        return {
            "answer": (
                "Nếu laptop được theo dõi qua TK 242 và phân bổ dần:\n\n"
                "- Dùng cho bộ phận bán hàng: Nợ TK 641 / Có TK 242.\n"
                "- Dùng cho bộ phận quản lý doanh nghiệp: Nợ TK 642 / Có TK 242.\n\n"
                "Khi mua ban đầu có thể ghi Nợ TK 153 hoặc 242, Nợ TK 1331 nếu VAT đủ điều kiện, Có 111/112/331 tùy phương thức thanh toán."
            ),
            "answer_mode": "department_allocation_comparison",
            "confidence": "high_curated_accounting_knowledge",
            "source_titles": ["knowledge_base/accounting_full_playbook_v85.md"],
        }

    if "tiep khach" in q and any(x in q for x in ["checklist", "kiem tra", "truoc khi ghi nhan"]):
        return {
            "answer": (
                "Checklist trước khi ghi nhận chi phí tiếp khách:\n\n"
                "1. Xác định mục đích kinh doanh và bộ phận sử dụng chi phí.\n"
                "2. Kiểm tra đề nghị/phê duyệt chi, hóa đơn và chứng từ kèm theo.\n"
                "3. Kiểm tra nội dung hóa đơn, ngày, thông tin người bán và số tiền.\n"
                "4. Kiểm tra phương thức thanh toán và chứng từ ngân hàng nếu thuộc trường hợp phải thanh toán không dùng tiền mặt.\n"
                "5. Xác định tài khoản phù hợp: thường 641 nếu phục vụ bán hàng hoặc 642 nếu phục vụ quản lý.\n"
                "6. Tách VAT đầu vào chỉ khi đủ điều kiện khấu trừ.\n"
                "7. Đánh dấu review vì đây là khoản chi nhạy cảm về thuế và lưu hồ sơ giải trình."
            ),
            "answer_mode": "accounting_risk_checklist",
            "confidence": "high_curated_risk_knowledge",
            "source_titles": ["knowledge_base/accounting_full_playbook_v85.md", "knowledge_base/vat_hoa_don.md"],
        }

    if "vat_rate" in concepts and any(x in q for x in ["moi loai", "tat ca", "toan bo"]):
        return {
            "answer": (
                "Không thể áp dụng một thuế suất VAT duy nhất cho mọi loại hàng hóa, dịch vụ. "
                "Các tài liệu hiện có không cung cấp bảng phân loại thuế suất đầy đủ, nên hệ thống không tự chọn một tỷ lệ chung. "
                "Cần xác định cụ thể hàng hóa/dịch vụ, thời điểm áp dụng và văn bản thuế tương ứng."
            ),
            "answer_mode": "no_universal_vat_rate",
            "confidence": "high_safe_scope_control",
            "source_titles": [],
        }

    return None


def _search_local_grounded_knowledge(question: str, limit: int = 8) -> List[Dict[str, Any]]:
    """Search every local knowledge file using the same strict gate as Supabase.

    The older V85 search ranked whole 900-character chunks by raw token overlap,
    so a question about auto-posting could rank a fixed-asset document above the
    exact internal-control sentence. This paragraph-level search fixes that.
    """
    knowledge_dir = ROOT_DIR / "knowledge_base"
    if not knowledge_dir.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for path in knowledge_dir.rglob("*.md"):
        try:
            raw_text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        front_matter, text = _parse_markdown_front_matter(raw_text)
        rel = str(path.relative_to(ROOT_DIR))
        doc_type = str(front_matter.get("doc_type") or "").lower()
        q_norm = _normalized_text(question)
        if doc_type in {"knowledge_changelog", "release_notes"} and not any(
            token in q_norm for token in ["changelog", "thay doi", "phien ban", "v110"]
        ):
            continue
        if path.name.lower().startswith("readme") and not any(
            token in q_norm for token in ["readme", "huong dan kho kien thuc", "cau truc kho kien thuc"]
        ):
            continue
        for index, candidate_text in enumerate(_split_answer_candidates(text)):
            if len(candidate_text) < 12:
                continue
            chunk = {
                "title": rel,
                "heading": "",
                "content": candidate_text,
                "tokens": _tokens(candidate_text),
                "metadata": {"knowledge_front_matter": front_matter},
            }
            breakdown = _hybrid_chunk_score(question, chunk)
            row: Dict[str, Any] = {
                "score": float(breakdown.get("score") or 0),
                "score_breakdown": breakdown,
                "answerability_score": _candidate_score(question, candidate_text),
                "chunk_id": f"local-{rel}-{index}",
                "document_id": rel,
                "title": rel,
                "source_type": "local_knowledge",
                "chunk_no": index,
                "heading": "",
                "snippet": _clean_rag_text(candidate_text, max_len=700),
                "content": candidate_text,
                "metadata": {"knowledge_front_matter": front_matter},
            }
            relevance = _source_relevance_metrics(question, row)
            row["relevance_coverage"] = relevance.get("coverage", 0)
            row["relevance_phrase_hits"] = relevance.get("phrase_hits", 0)
            row["relevance_matched_concepts"] = relevance.get("matched_concepts") or []
            row["relevance_reason"] = relevance.get("reason")
            row["source_policy"] = relevance.get("source_policy") or {}
            row["source_priority"] = relevance.get("source_priority", 0)
            row["source_status"] = relevance.get("source_status")
            row["source_effective_from"] = relevance.get("source_effective_from")
            row["source_warnings"] = relevance.get("source_warnings") or []
            if relevance.get("accepted"):
                rows.append(row)
    rows.sort(
        key=lambda row: (
            float(row.get("score") or 0),
            float(row.get("answerability_score") or 0),
            float(row.get("relevance_coverage") or 0),
            float(row.get("source_priority") or 0),
        ),
        reverse=True,
    )
    # Deduplicate near-identical snippets.
    selected: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = _normalized_text(str(row.get("content") or ""))[:180]
        if not key or key in seen:
            continue
        seen.add(key)
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def _local_sources_from_base_answer(question: str, base_answer: Dict[str, Any], limit: int = 6) -> List[Dict[str, Any]]:
    rows = base_answer.get("knowledge_sources") or base_answer.get("sources") or []
    accepted: List[Dict[str, Any]] = []
    for index, row in enumerate(rows, 1):
        content = str(row.get("content") or row.get("snippet") or "")
        source_name = str(row.get("source") or row.get("title") or "knowledge_base")
        candidate: Dict[str, Any] = {
            "score": float(row.get("score") or 0) + 3,
            "answerability_score": 0,
            "chunk_id": f"local-{index}",
            "document_id": source_name,
            "title": source_name,
            "source_type": "local_knowledge",
            "chunk_no": row.get("chunk_index"),
            "heading": "",
            "snippet": _clean_rag_text(content, max_len=700),
            "content": content,
            "metadata": {},
        }
        excerpts = _ranked_excerpts(question, [candidate], max_items=1)
        candidate["answerability_score"] = excerpts[0].get("score", 0) if excerpts else 0
        relevance = _source_relevance_metrics(question, candidate)
        candidate["relevance_coverage"] = relevance.get("coverage", 0)
        candidate["relevance_phrase_hits"] = relevance.get("phrase_hits", 0)
        candidate["relevance_matched_concepts"] = relevance.get("matched_concepts") or []
        candidate["relevance_reason"] = relevance.get("reason")
        if relevance.get("accepted"):
            accepted.append(candidate)
    accepted.sort(
        key=lambda x: (
            float(x.get("answerability_score") or 0),
            float(x.get("relevance_coverage") or 0),
            float(x.get("score") or 0),
        ),
        reverse=True,
    )
    return accepted[:limit]


def _no_evidence_answer(question: str) -> str:
    q = _normalized_text(question)
    if "penalty" in _concepts_in_text(question):
        return (
            "Không tìm thấy trong các tài liệu đã nạp đoạn nào nêu rõ mức xử phạt và số tiền phạt cho trường hợp này. "
            "Mình sẽ không tự đoán mức phạt; cần bổ sung đúng văn bản xử phạt hoặc hỏi kèm tên văn bản, điều và khoản."
        )
    if "deadline" in _concepts_in_text(question) or "effective_date" in _concepts_in_text(question):
        return (
            "Không tìm thấy trong các tài liệu đã nạp ngày hiệu lực hoặc thời hạn cụ thể đủ để trả lời chắc chắn. "
            "Mình sẽ không tự suy đoán ngày/thời hạn."
        )
    if "signer" in _concepts_in_text(question):
        return "Không tìm thấy thông tin người ký trong các đoạn tài liệu đã nạp; mình sẽ không tự đoán tên người ký."
    if _account_codes_from_question(question):
        codes = ", ".join(f"TK {c}" for c in _account_codes_from_question(question))
        return f"Không tìm thấy định nghĩa chính xác của {codes} trong nguồn đã nạp và danh mục tài khoản nội bộ."
    return (
        "Chưa tìm thấy đoạn tài liệu đủ liên quan và đủ thông tin để trả lời câu hỏi này. "
        "Mình đã loại các đoạn chỉ trùng từ chung để tránh trả lời sai."
    )




# V59-V62: follow-up resolver, intent router, emotional tone and answer gate.
_FOLLOWUP_PREFIXES = (
    "con ", "còn ", "the ", "thế ", "vay ", "vậy ", "neu ", "nếu ",
    "truong hop tren", "trường hợp trên", "cai tren", "cái trên", "no thi", "nó thì",
)


def _last_user_message(items: List[Dict[str, Any]], browser_history: str = "") -> str:
    for item in reversed(items or []):
        if str(item.get("role") or "").lower() == "user" and str(item.get("content") or "").strip():
            return str(item.get("content")).strip()
    # Supported frontend history formats:
    # - [1] Q: ...\nA: ...
    # - user: ...\nassistant: ... (product chat API)
    matches = re.findall(r"(?:^|\n)(?:\[\d+\]\s*)?Q:\s*(.+?)(?=\nA:|\n\n|$)", browser_history or "", flags=re.I | re.S)
    if matches:
        return matches[-1].strip()
    role_matches = re.findall(
        r"(?:^|\n)user:\s*(.+?)(?=\n(?:assistant|user):|$)",
        browser_history or "",
        flags=re.I | re.S,
    )
    return role_matches[-1].strip() if role_matches else ""


def _is_followup_question(question: str) -> bool:
    q = _normalized_text(question)
    tokens = _tokens(question)
    if not q:
        return False
    normalized_prefixes = [_normalized_text(prefix) for prefix in _FOLLOWUP_PREFIXES]
    if any(q == prefix or q.startswith(prefix + " ") for prefix in normalized_prefixes if prefix):
        return True
    if len(tokens) <= 9 and any(term in q for term in ["thi sao", "the nao", "cai do", "o tren", "tiep di", "con nua", "khac gi"]):
        return True
    bare_account_followup = re.fullmatch(
        r"(?:(?:con|tk|tai khoan)\s+)?\d{3,4}(?:\s+thi\s+sao)?[?!.]*",
        q,
    )
    if len(tokens) <= 5 and bare_account_followup:
        return True
    return False


def _resolve_followup_question(question: str, items: List[Dict[str, Any]], browser_history: str = "") -> Dict[str, Any]:
    previous = _last_user_message(items, browser_history)
    if not previous or not _is_followup_question(question):
        return {"question": question, "used": False, "previous_question": previous}

    current_codes = _account_codes_from_question(question)
    previous_codes = _account_codes_from_question(previous)
    previous_norm = _normalized_text(previous)
    q_norm = _normalized_text(question)

    # In account follow-ups users often type only "Còn 642 thì sao?".
    if not current_codes and (previous_codes or "tai khoan" in previous_norm or "tk " in previous_norm):
        bare_codes = re.findall(r"\b(\d{3,4})\b", q_norm)
        current_codes = [code for code in bare_codes if 100 <= int(code) <= 9999]

    if current_codes and (previous_codes or "tai khoan" in previous_norm or "tk " in previous_norm):
        code = current_codes[0]
        if any(term in previous_norm for term in ["su dung", "dung de", "la gi", "hach toan chi phi"]):
            resolved = f"Tài khoản {code} được sử dụng trong trường hợp nào?"
        else:
            resolved = f"Giải thích tài khoản {code} và cách sử dụng trong kế toán."
        return {"question": resolved, "used": True, "previous_question": previous, "strategy": "account_followup"}

    # If the new condition changes payment status, remove the contradictory old
    # phrase instead of concatenating both "chưa thanh toán" and "đã thanh toán".
    bank_payment = any(term in q_norm for term in ["thanh toan bang ngan hang", "bang ngan hang", "chuyen khoan", "tk 112"])
    cash_payment = any(term in q_norm for term in ["thanh toan bang tien mat", "bang tien mat", "tk 111"])
    if bank_payment or cash_payment:
        prior = re.sub(r"(?i)\b(chưa|chua)\s+thanh\s+toán\b|\b(chưa|chua)\s+thanh\s+toan\b", "", previous)
        prior = re.sub(r"\s+", " ", prior).strip(" .?")
        method = "chuyển khoản ngân hàng" if bank_payment else "tiền mặt"
        resolved = f"{prior}. Doanh nghiệp thanh toán ngay bằng {method}. Hãy nêu bút toán phù hợp."
        return {"question": resolved, "used": True, "previous_question": previous, "strategy": "payment_method_followup"}

    if q_norm.startswith("neu ") or any(term in q_norm for term in ["co hoa don", "khong co hoa don"]):
        resolved = f"Tình huống trước: {previous}\nĐiều kiện bổ sung: {question}\nHãy trả lời cho tình huống đã cập nhật."
        return {"question": resolved, "used": True, "previous_question": previous, "strategy": "condition_followup"}

    resolved = f"Câu hỏi trước: {previous}\nCâu hỏi nối tiếp: {question}\nHãy trả lời đúng phần nối tiếp trong cùng ngữ cảnh."
    return {"question": resolved, "used": True, "previous_question": previous, "strategy": "generic_followup"}


def _conversation_route(question: str) -> Dict[str, Any]:
    q = _normalized_text(question)
    tokens = _tokens(question)
    if not q:
        return {"route": "clarify", "confidence": 1.0, "reason": "empty"}

    accounting_terms = [
        "hach toan", "dinh khoan", "but toan", "tai khoan", "tk ", "vat", "gtgt", "hoa don",
        "thue", "chi phi", "doanh thu", "cong no", "khau hao", "tscd", "ccdc", "luong",
        "bhxh", "nhap kho", "xuat kho", "thanh toan", "ke toan", "bao cao tai chinh",
    ]
    legal_terms = ["thong tu", "nghi dinh", "dieu ", "khoan ", "quy dinh", "phap luat", "muc phat", "thoi han"]
    if any(term in q for term in accounting_terms) or _account_codes_from_question(question):
        return {"route": "accounting_rag", "confidence": 0.96, "reason": "accounting_terms"}
    if any(term in q for term in legal_terms):
        return {"route": "knowledge_rag", "confidence": 0.95, "reason": "legal_or_policy_terms"}

    if any(term in q for term in ["met qua", "mệt quá", "stress", "ap luc", "áp lực", "chan qua", "chán quá", "roi qua", "rối quá", "khong biet lam sao", "không biết làm sao"]):
        return {"route": "emotional_support", "confidence": 0.94, "reason": "emotion_signal"}
    if q in {"chao", "xin chao", "hello", "hi", "alo", "hey", "chao finiip", "xin chao finiip"} or (len(tokens) <= 3 and q.startswith("chao")):
        return {"route": "greeting", "confidence": 0.99, "reason": "greeting"}
    if any(q == term or q.startswith(term + " ") for term in ["cam on", "cảm ơn", "thanks", "thank you"]):
        return {"route": "thanks", "confidence": 0.99, "reason": "thanks"}
    if any(q == term or q.startswith(term + " ") for term in ["tam biet", "tạm biệt", "bye", "hen gap lai"]):
        return {"route": "goodbye", "confidence": 0.99, "reason": "goodbye"}
    if any(term in q for term in ["ban la ai", "finiip la ai", "gioi thieu ve ban", "ten ban la gi"]):
        return {"route": "identity", "confidence": 0.99, "reason": "identity_question"}
    if any(term in q for term in ["ban lam duoc gi", "ban co the lam gi", "co the giup gi", "ho tro duoc gi", "giup toi", "huong dan su dung", "co chuc nang gi"]):
        return {"route": "help", "confidence": 0.9, "reason": "capability_question"}
    if len(tokens) <= 2:
        return {"route": "clarify", "confidence": 0.72, "reason": "too_short"}
    return {"route": "general_knowledge", "confidence": 0.62, "reason": "default_general_question"}


def _natural_conversation_answer(route: str, question: str, previous_question: str = "") -> str:
    q = _normalized_text(question)
    if route == "greeting":
        return (
            "Xin chào, tôi là Finiip — trợ lý AI thuộc CTCP IIP Việt Nam. "
            "Tôi có thể hỗ trợ bạn về kế toán, thuế, hóa đơn, định khoản, tính toán nghiệp vụ, "
            "đọc và phân tích tài liệu, lập hoặc xuất báo cáo, kiểm tra rủi ro và hướng dẫn quy trình từng bước.\n\n"
            "Bạn đang muốn xử lý công việc nào trước?"
        )
    if route == "identity":
        return (
            "Tôi là Finiip, trợ lý AI thuộc CTCP IIP Việt Nam, được xây dựng để hỗ trợ công việc kế toán và vận hành doanh nghiệp. "
            "Tôi có thể ghi nhớ mạch hội thoại trong cùng cuộc trò chuyện, phân tích câu hỏi dài, tính toán, gợi ý bút toán, "
            "đọc tài liệu và lập báo cáo. Với nội dung pháp lý hoặc số liệu quan trọng, tôi sẽ ưu tiên căn cứ từ tài liệu đã được nạp và nói rõ khi chưa đủ dữ liệu."
        )
    if route == "thanks":
        return "Không có gì nhé. Mình sẽ giữ đúng ngữ cảnh đang làm để bạn không phải nhắc lại từ đầu."
    if route == "goodbye":
        return "Được rồi, nghỉ một chút nhé. Lần sau quay lại mình sẽ tiếp tục theo đúng mạch công việc này."
    if route == "emotional_support":
        if any(term in q for term in ["roi", "rối", "khong biet", "không biết"]):
            return "Mình hiểu, lúc nhiều lỗi dồn lại rất dễ bị rối. Bạn gửi đúng một lỗi hoặc một màn hình đang vướng trước; mình sẽ tách nhỏ và xử lý cùng bạn, không cần làm tất cả một lúc."
        return "Nghe có vẻ bạn đang khá mệt và áp lực. Mình ở đây; mình có thể chia việc thành từng bước nhỏ để bạn xử lý nhẹ hơn."
    if route == "help":
        return (
            "Tôi có thể hỗ trợ bạn các nhóm công việc chính sau:\n\n"
            "1. Kế toán nghiệp vụ: giải thích tài khoản, gợi ý định khoản, kiểm tra Nợ/Có, công nợ, kho, tài sản cố định, CCDC, lương và khóa sổ.\n"
            "2. Thuế và hóa đơn: VAT, điều kiện khấu trừ, chi phí được trừ, chứng từ cần có và cảnh báo rủi ro.\n"
            "3. Tính toán: VAT xuôi/ngược, khấu hao, phân bổ, giá vốn, lợi nhuận và các bài toán có số liệu.\n"
            "4. Báo cáo: đọc dữ liệu, phân tích báo cáo tài chính, lập bản tóm tắt, checklist và xuất báo cáo theo yêu cầu.\n"
            "5. Tài liệu và RAG: đọc PDF/Word/Excel, trả lời theo nguồn, tóm tắt văn bản và hướng dẫn quy trình dài.\n"
            "6. Hỗ trợ hệ thống: phân tích lỗi backend/frontend, API, database và hướng dẫn triển khai từng bước.\n\n"
            "Bạn chỉ cần mô tả công việc bằng câu tự nhiên, kể cả câu hỏi dài hoặc câu hỏi nối tiếp."
        )
    if route == "clarify":
        return "Tôi chưa đủ ngữ cảnh để hiểu chính xác. Bạn đang muốn hỏi nghiệp vụ kế toán, tính toán, hỏi theo tài liệu, lập báo cáo hay xử lý một lỗi trong hệ thống?"
    return ""


def _normalize_local_search_results(query: str, raw: Dict[str, Any], limit: int) -> Dict[str, Any]:
    accepted: List[Dict[str, Any]] = []
    rejected = 0
    for row in raw.get("results") or []:
        item = dict(row)
        item["content"] = item.get("content") or item.get("snippet") or ""
        item["retrieval_mode"] = "local_strict_relevance_v106"
        excerpts = _ranked_excerpts(query, [item], max_items=1)
        item["answerability_score"] = excerpts[0].get("score", 0) if excerpts else 0
        relevance = _source_relevance_metrics(query, item)
        item["relevance_coverage"] = relevance.get("coverage", 0)
        item["relevance_overlap_count"] = relevance.get("overlap_count", 0)
        item["relevance_matched_terms"] = relevance.get("matched_terms") or []
        item["relevance_phrase_hits"] = relevance.get("phrase_hits", 0)
        item["relevance_matched_concepts"] = relevance.get("matched_concepts") or []
        item["relevance_reason"] = relevance.get("reason")
        if relevance.get("accepted"):
            accepted.append(item)
        else:
            rejected += 1
    accepted.sort(key=lambda x: (float(x.get("answerability_score") or 0), float(x.get("relevance_coverage") or 0), float(x.get("score") or 0)), reverse=True)
    return {
        "version": V101_VERSION,
        "storage_backend": "local",
        "query": query,
        "retrieval_query": query,
        "workspace_id": raw.get("workspace_id") or "default",
        "results": accepted[:limit],
        "count": len(accepted[:limit]),
        "total_candidates": len(raw.get("results") or []),
        "relevant_candidates": len(accepted),
        "rejected_low_relevance": rejected,
        "retrieval_mode": "local_grounded_strict_v106",
    }


def _answer_quality_gate(question: str, resolved_question: str, result: Dict[str, Any]) -> Dict[str, Any]:
    answer = str(result.get("answer") or "").strip()
    citations = result.get("citations") or []
    confidence = str(result.get("confidence") or "")
    issues: List[str] = []
    forced = False

    concepts = set(_concepts_in_text(resolved_question))
    exact_fact = bool(concepts & {"penalty", "deadline", "effective_date", "signer"})
    if exact_fact and not citations and not confidence.startswith("high_curated"):
        answer = _no_evidence_answer(resolved_question)
        result["answer_mode"] = "quality_gate_no_evidence"
        result["confidence"] = "low_quality_gate_no_evidence"
        issues.append("exact_fact_without_citation")
        forced = True

    requested_codes = _account_codes_from_question(resolved_question)
    if requested_codes and result.get("answer_mode") == "account_lookup":
        missing = [code for code in requested_codes if not _text_contains_account_code(answer, code)]
        if missing:
            answer = _no_evidence_answer(resolved_question)
            result["confidence"] = "low_quality_gate_account_mismatch"
            issues.append("requested_account_missing:" + ",".join(missing))
            forced = True

    # Citation markers must refer to an existing citation.
    markers = [int(x) for x in re.findall(r"\[(\d+)\]", answer)]
    max_citation = len(citations)
    invalid_markers = sorted({m for m in markers if m < 1 or m > max_citation}) if markers else []
    if invalid_markers:
        for marker in invalid_markers:
            answer = answer.replace(f"[{marker}]", "")
        issues.append("invalid_citation_markers_removed")

    if not answer:
        answer = _no_evidence_answer(resolved_question)
        result["confidence"] = "low_empty_answer"
        issues.append("empty_answer")
        forced = True

    result["answer"] = answer.strip()
    result["quality_gate"] = {
        "passed": not forced,
        "issues": issues,
        "citation_count": len(citations),
        "requested_account_codes": requested_codes,
    }
    result["needs_human_review"] = bool(
        forced
        or str(result.get("confidence") or "").startswith("low")
        or exact_fact
        or result.get("answer_mode") in {"risk", "chief_accountant", "with_journal"}
    )
    return result

# V58: Conversation Persona Layer -------------------------------------------------
# Keep factual RAG/accounting logic unchanged, then lightly rewrite the final
# surface text so the assistant feels less robotic while staying safe.
def _apply_conversation_persona(question: str, answer: str, *, confidence: str = "", answer_mode: str = "", route: str = "") -> str:
    raw = str(answer or "").strip()
    if not raw:
        return raw
    if route in {"greeting", "identity", "thanks", "goodbye", "emotional_support", "help", "clarify"}:
        return raw

    q = _normalized_text(question)
    conf = str(confidence or "").lower()
    mode = str(answer_mode or "").lower()
    if mode in {"source_only", "formula_engine"}:
        return raw

    replacements = {
        "Dựa trên tài liệu đã nạp trong Supabase RAG, câu trả lời là:": "Mình đối chiếu tài liệu và thấy như sau:",
        "Dựa trên tài liệu đã nạp trong knowledge_base nội bộ, câu trả lời là:": "Mình đối chiếu knowledge nội bộ và thấy như sau:",
        "Dựa trên tài liệu đã nạp trong Supabase RAG, các ý liên quan nhất là:": "Các ý liên quan nhất mình tìm được là:",
        "Dựa trên tài liệu đã nạp trong knowledge_base nội bộ, các ý liên quan nhất là:": "Các ý liên quan nhất mình tìm được là:",
        "Dựa trên tài liệu đã nạp trong Supabase RAG, tớ tổng hợp câu trả lời chi tiết như sau:": "Mình tổng hợp lại cho dễ theo dõi:",
        "Dựa trên tài liệu đã nạp trong knowledge_base nội bộ, tớ tổng hợp câu trả lời chi tiết như sau:": "Mình tổng hợp lại cho dễ theo dõi:",
        "Hệ thống sẽ không tự": "Mình sẽ không tự",
        "Hệ thống đã loại": "Mình đã loại",
    }
    text = raw
    for old, new in replacements.items():
        text = text.replace(old, new)

    low_conf = conf.startswith("low") or "without" in conf or "no_relevant" in conf or "no_answerable" in conf
    if low_conf:
        if not text.lower().startswith(("mình", "chưa", "không")):
            text = "Mình chưa đủ căn cứ để kết luận chắc chắn.\n\n" + text
        if "nạp thêm" not in _normalized_text(text):
            text += "\n\nBạn nên nạp thêm đúng tài liệu nguồn hoặc cung cấp chi tiết còn thiếu; mình sẽ kiểm tra lại theo nguồn đó."
        return text.strip()

    is_accounting = any(t in q for t in ["hach toan", "dinh khoan", "tai khoan", "tk ", "but toan", "chi phi", "vat", "gtgt"])
    if is_accounting and not text.startswith(("Mình", "Theo", "TK ", "Tài khoản")):
        text = "Mình đi thẳng vào phần cần dùng nhé:\n\n" + text
    return text.strip()


def _contextual_followup_prompt(question: str, route: str, answer_mode: str = "") -> str:
    q = _normalized_text(question)
    if route == "formula":
        return "Tôi còn có thể giúp bạn kiểm tra lại công thức, thay số khác hoặc trình bày thành bảng tính."
    if any(term in q for term in ["hach toan", "dinh khoan", "but toan", "tai khoan", "tk "]):
        return "Tôi còn có thể giúp bạn lập bút toán theo số tiền cụ thể, kiểm tra chứng từ và chỉ ra rủi ro thường gặp."
    if any(term in q for term in ["bao cao", "bctc", "loi nhuan", "doanh thu", "chi phi", "dong tien"]):
        return "Tôi còn có thể giúp bạn chuyển phần này thành checklist, bảng phân tích hoặc nội dung báo cáo."
    if any(term in q for term in ["thue", "vat", "gtgt", "hoa don", "thong tu", "nghi dinh", "quy dinh"]):
        return "Tôi còn có thể giúp bạn đối chiếu điều kiện áp dụng, hồ sơ cần lưu và các điểm rủi ro."
    if str(answer_mode or "").lower() in {"chief_accountant", "detailed", "risk", "with_example"}:
        return "Tôi còn có thể giúp bạn rút gọn nội dung này thành quy trình thực hiện hoặc checklist kiểm soát."
    return "Tôi còn có thể giúp bạn làm rõ phần nào hoặc tiếp tục xử lý bước tiếp theo?"


def _append_contextual_followup(question: str, answer: str, *, route: str, answer_mode: str = "", confidence: str = "") -> str:
    text = str(answer or "").strip()
    if not text or route in {"greeting", "identity", "thanks", "goodbye", "emotional_support", "help", "clarify"}:
        return text
    normalized = _normalized_text(text)
    if any(term in normalized[-260:] for term in ["toi con co the giup", "ban muon toi", "ban can toi"]):
        return text
    if str(confidence or "").lower().startswith("low"):
        return text
    return text + "\n\n" + _contextual_followup_prompt(question, route, answer_mode)


def _llm_mode() -> str:
    mode = str(os.getenv("FINIIP_LLM_MODE", "auto") or "auto").strip().lower()
    return mode if mode in {"auto", "always", "off"} else "auto"


def _llm_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY")) and _llm_mode() != "off"


def _llm_should_run(route: str, answer_mode: str, citations: List[Dict[str, Any]]) -> bool:
    if not _llm_available():
        return False
    if _llm_mode() == "always":
        return route not in {"formula", "greeting", "identity", "thanks", "goodbye", "emotional_support", "help", "clarify"}
    return route == "general_knowledge" or bool(citations) or str(answer_mode or "").lower() in {
        "detailed", "chief_accountant", "with_example", "risk"
    }


def _llm_source_context(citations: List[Dict[str, Any]]) -> str:
    blocks: List[str] = []
    for citation in (citations or [])[:8]:
        idx = citation.get("index") or len(blocks) + 1
        title = _friendly_source_title(citation.get("document_title") or citation.get("title"))
        location = citation.get("legal_location") or citation.get("location") or ""
        excerpt = _clean_rag_text(citation.get("excerpt") or "", max_len=1800)
        blocks.append(f"[{idx}] {title} — {location}\n{excerpt}")
    return "\n\n".join(blocks)


def _maybe_llm_enhance(
    *,
    question: str,
    resolved_question: str,
    history: str,
    route: str,
    answer_mode: str,
    deterministic_answer: str,
    citations: List[Dict[str, Any]],
) -> Optional[str]:
    """Use the configured LLM as a synthesis/general-knowledge layer.

    Official accounting/legal answers remain grounded in retrieved excerpts.
    When no source exists, the model may answer general knowledge but must not
    invent current laws, rates, deadlines or penalties.
    """
    if not _llm_should_run(route, answer_mode, citations):
        return None
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        sources = _llm_source_context(citations)
        grounded = bool(sources.strip())
        request_plan = analyze_request(resolved_question)
        history_chars = int(os.getenv("FINIIP_LLM_HISTORY_CHARS", os.getenv("FINIIP_CHAT_CONTEXT_CHARS", "16000")))
        max_output_tokens = int(os.getenv("FINIIP_LLM_MAX_OUTPUT_TOKENS", "4000"))
        system = (
            "Bạn là Finiip, trợ lý AI thuộc CTCP IIP Việt Nam. "
            "Trả lời bằng tiếng Việt tự nhiên, tận tâm, rõ ràng và đúng trọng tâm. "
            "Bạn giỏi kế toán, thuế, báo cáo, tính toán nghiệp vụ, phân tích tài liệu và hỗ trợ kỹ thuật. "
            "Luôn ghi nhớ ngữ cảnh hội thoại được cung cấp. Với câu hỏi dài, hãy lập kế hoạch, trả lời đủ từng phần, "
            "chia kết luận, cách làm, công thức/số liệu, ví dụ và lưu ý; không được bỏ sót yêu cầu. "
            "Không tự bịa dữ kiện, văn bản, điều khoản, thuế suất, mức phạt hoặc thời hạn. "
            "Không chèn đường dẫn file nội bộ hoặc mục 'Nguồn nội bộ' vào cuối câu trả lời; nguồn sẽ được giao diện hiển thị riêng. "
            "Nếu có nguồn đánh số [1], [2], chỉ dùng thông tin trong nguồn và có thể gắn ký hiệu [n] ngay sau ý quan trọng."
        )
        if not grounded:
            system += (
                " Khi không có nguồn, bạn có thể trả lời kiến thức phổ thông và hỗ trợ suy luận; "
                "nhưng với quy định hiện hành hoặc thông tin cần cập nhật, phải nói rõ cần kiểm tra nguồn chính thức."
            )
        user = (
            f"NGỮ CẢNH GẦN ĐÂY:\n{str(history or '')[-5000:]}\n\n"
            f"CÂU HỎI GỐC:\n{question}\n\n"
            f"CÂU HỎI ĐÃ GIẢI NGỮ CẢNH:\n{resolved_question}\n\n"
            f"CÂU TRẢ LỜI NỀN TỪ ENGINE:\n{deterministic_answer}\n\n"
            f"NGUỒN ĐÃ TRUY XUẤT:\n{sources or '(không có nguồn RAG phù hợp)'}\n\n"
            "Hãy viết câu trả lời cuối cùng. Không lặp lại danh sách nguồn ở cuối."
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.15,
            max_tokens=max_output_tokens,
        )
        text = str(response.choices[0].message.content or "").strip()
        if not text:
            return None
        if grounded:
            markers = {int(x) for x in re.findall(r"\[(\d+)\]", text)}
            valid = set(range(1, len(citations) + 1))
            for marker in markers - valid:
                text = text.replace(f"[{marker}]", "")
        return text.strip()
    except Exception:
        return None


def answer_with_supabase_rag(question: str, workspace_id: str = "default", limit: int = 6, history: str = "", answer_mode: str = "auto", conversation_id: str = "admin", save_memory: bool = True, allow_llm: bool = True) -> Dict[str, Any]:
    """Unified conversational answer service for both Supabase and local mode.

    V59: persistent context + follow-up resolution
    V60: intent routing
    V61: answer quality gate
    V62: stable conversation metadata for frontend/admin UI
    """
    memory_result = list_supabase_chat_memory(
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        limit=20,
    ) if save_memory else {"items": [], "storage_backend": "disabled"}
    memory_items = memory_result.get("items") or []
    server_history = _format_memory_for_retrieval(memory_items)
    combined_history = _combine_history(server_history, history)
    followup = _resolve_followup_question(question, memory_items, history)
    resolved_question = followup.get("question") or question
    route_info = _conversation_route(resolved_question)
    route = route_info.get("route") or "knowledge_rag"

    natural_answer = _natural_conversation_answer(route, question, followup.get("previous_question") or "")
    if natural_answer:
        result = {
            "version": V101_VERSION,
            "workspace_id": workspace_id,
            "conversation_id": conversation_id,
            "question": question,
            "resolved_question": resolved_question,
            "followup_context_used": bool(followup.get("used")),
            "followup_strategy": followup.get("strategy"),
            "answer": natural_answer,
            "citations": [],
            "answer_mode": "conversation",
            "requested_answer_mode": answer_mode,
            "conversation_route": route,
            "intent_confidence": route_info.get("confidence"),
            "intent_reason": route_info.get("reason"),
            "enterprise_sources": [],
            "local_knowledge_sources": [],
            "base_sources": [],
            "confidence": "high_conversation_intent",
            "needs_human_review": False,
            "storage_backend": memory_result.get("storage_backend") or ("supabase" if supabase_is_active() else "local"),
            "evidence_backend": "not_required",
            "retrieval_mode": "conversation_router",
            "conversation_memory_used": bool(combined_history),
            "persistent_memory_count": len(memory_items),
            "quality_gate": {"passed": True, "issues": [], "citation_count": 0},
            "source_cards": [],
            "source_presentation": "separate_cards",
            "llm_used": False,
        }
        if save_memory:
            save_supabase_chat_message(workspace_id, conversation_id, "user", question, {"route": route})
            save_supabase_chat_message(workspace_id, conversation_id, "assistant", natural_answer, {"route": route, "confidence": result["confidence"]})
        return result

    formula = _try_formula_answer(resolved_question)
    if formula:
        result = {
            "version": V101_VERSION,
            "workspace_id": workspace_id,
            "conversation_id": conversation_id,
            "question": question,
            "resolved_question": resolved_question,
            "followup_context_used": bool(followup.get("used")),
            "followup_strategy": followup.get("strategy"),
            "answer": formula["answer"],
            "citations": [],
            "answer_mode": formula.get("answer_mode"),
            "requested_answer_mode": answer_mode,
            "conversation_route": "formula",
            "intent_confidence": 0.99,
            "enterprise_sources": [],
            "local_knowledge_sources": [],
            "base_sources": [],
            "confidence": "high_formula_engine",
            "needs_human_review": True,
            "storage_backend": "supabase" if supabase_is_active() else "local",
            "evidence_backend": "formula_engine",
            "retrieval_mode": "formula_engine",
            "conversation_memory_used": bool(combined_history),
            "persistent_memory_count": len(memory_items),
            "formula_result": formula.get("formula_result"),
        }
        result = _answer_quality_gate(question, resolved_question, result)
        result["answer"] = _append_contextual_followup(
            question,
            result.get("answer") or "",
            route="formula",
            answer_mode=result.get("answer_mode") or "",
            confidence=result.get("confidence") or "",
        )
        result["source_cards"] = []
        result["source_presentation"] = "separate_cards"
        result["llm_used"] = False
        if save_memory:
            save_supabase_chat_message(workspace_id, conversation_id, "user", question, {"route": "formula", "resolved_question": resolved_question})
            save_supabase_chat_message(workspace_id, conversation_id, "assistant", result["answer"], {"confidence": result["confidence"]})
        return result

    request_analysis = analyze_request(resolved_question)
    selected_mode = _answer_mode_from_question(resolved_question, answer_mode)
    if request_analysis.get("is_complex") and selected_mode == "auto":
        selected_mode = "chief_accountant"
    base_answer = ask_accounting_ai(resolved_question, limit=max(limit, 8))
    journal_answer = _build_accounting_journal_answer(resolved_question, base_answer)
    curated_answer = _build_curated_accounting_knowledge_answer(resolved_question)

    if supabase_is_active():
        search_result = search_documents_supabase(
            resolved_question,
            workspace_id=workspace_id,
            limit=max(limit, 8 if _wants_long_answer(resolved_question, selected_mode) else limit),
            history=combined_history,
        )
    else:
        raw_local = search_documents_local(
            query=resolved_question,
            workspace_id=workspace_id,
            limit=max(limit * 4, 20),
        )
        search_result = _normalize_local_search_results(resolved_question, raw_local, max(limit, 8))

    uploaded_sources = search_result.get("results") or []
    local_sources = _search_local_grounded_knowledge(resolved_question, limit=max(limit, 8))
    if not local_sources:
        local_sources = _local_sources_from_base_answer(resolved_question, base_answer, limit=max(limit, 8))

    evidence_sources = uploaded_sources[:limit] or local_sources[:limit]
    if uploaded_sources:
        evidence_backend = "Supabase RAG" if supabase_is_active() else "RAG local"
    else:
        evidence_backend = "knowledge_base nội bộ"
    conflict_warnings = _collect_conflict_warnings(
        resolved_question,
        workspace_id=workspace_id,
        sources=uploaded_sources[:limit],
    ) if uploaded_sources and supabase_is_active() else []

    account_lookup = _build_account_lookup_answer(resolved_question, uploaded_sources[:limit], base_answer)
    if account_lookup:
        synthesized = {
            "answer": account_lookup["answer"],
            "citations": account_lookup.get("citations", []),
            "answer_mode": account_lookup.get("answer_mode"),
        }
        confidence = account_lookup.get("confidence") or "medium_curated_account_knowledge"
    elif curated_answer:
        source_titles = curated_answer.get("source_titles") or []
        citations = [
            {
                "index": index, "title": _friendly_source_title(title), "document_title": _friendly_source_title(title), "document_id": title,
                "chunk_id": None, "chunk_no": None, "heading": None, "page": None,
                "location": "Kho kiến thức nghiệp vụ Finiip", "legal_location": "", "excerpt": "", "source_kind": "internal_knowledge",
            }
            for index, title in enumerate(source_titles, 1)
        ]
        answer_text = curated_answer["answer"]
        synthesized = {"answer": answer_text, "citations": citations, "answer_mode": curated_answer.get("answer_mode")}
        confidence = curated_answer.get("confidence") or "high_curated_accounting_knowledge"
    elif journal_answer:
        citations = _journal_support_citations(resolved_question, evidence_sources, max_items=3)
        answer_text = journal_answer["answer"]
        synthesized = {"answer": answer_text, "citations": citations, "answer_mode": journal_answer.get("answer_mode")}
        confidence = (
            "high_accounting_rule_with_grounded_sources"
            if citations and str(journal_answer.get("confidence") or "").startswith("high")
            else journal_answer.get("confidence") or "medium_accounting_rule_engine"
        )
    elif evidence_sources:
        synthesized = _build_rag_answer_from_sources(
            resolved_question,
            evidence_sources,
            storage_label=evidence_backend,
            history=combined_history,
            answer_mode=selected_mode,
            conflict_warnings=conflict_warnings,
        )
        if not synthesized.get("citations") or synthesized.get("answer_mode") == "no_rag_source":
            synthesized = {"answer": _no_evidence_answer(resolved_question), "citations": [], "answer_mode": "no_answerable_evidence"}
            confidence = "low_without_answerable_evidence"
        else:
            confidence = _rag_confidence(evidence_sources)
    else:
        synthesized = {"answer": _no_evidence_answer(resolved_question), "citations": [], "answer_mode": "no_relevant_evidence"}
        confidence = "low_without_relevant_sources"

    result = {
        "version": V101_VERSION,
        "workspace_id": workspace_id,
        "conversation_id": conversation_id,
        "question": question,
        "resolved_question": resolved_question,
        "followup_context_used": bool(followup.get("used")),
        "followup_strategy": followup.get("strategy"),
        "previous_question": followup.get("previous_question") if followup.get("used") else None,
        "answer": synthesized["answer"],
        "citations": synthesized.get("citations", []),
        "answer_mode": synthesized.get("answer_mode"),
        "requested_answer_mode": answer_mode,
        "conversation_route": route,
        "intent_confidence": route_info.get("confidence"),
        "intent_reason": route_info.get("reason"),
        "enterprise_sources": uploaded_sources[:limit],
        "local_knowledge_sources": local_sources[:limit],
        "base_sources": base_answer.get("knowledge_sources") or base_answer.get("sources") or [],
        "confidence": confidence,
        "needs_human_review": True,
        "storage_backend": "supabase" if supabase_is_active() else "local",
        "memory_backend": memory_result.get("storage_backend"),
        "evidence_backend": evidence_backend if evidence_sources else "none",
        "retrieval_mode": search_result.get("retrieval_mode"),
        "retrieval_query": search_result.get("retrieval_query"),
        "retrieval_rejected_low_relevance": search_result.get("rejected_low_relevance", 0),
        "conversation_memory_used": bool(combined_history),
        "persistent_memory_count": len(memory_items),
        "conflict_warnings": conflict_warnings,
        "accounting_rule_id": journal_answer.get("rule_id") if journal_answer else None,
        "account_lookup_codes": _account_codes_from_question(resolved_question) if account_lookup else [],
        "request_analysis": request_analysis,
    }
    enhanced = _maybe_llm_enhance(
        question=question,
        resolved_question=resolved_question,
        history=combined_history,
        route=route,
        answer_mode=result.get("answer_mode") or selected_mode,
        deterministic_answer=result.get("answer") or "",
        citations=result.get("citations") or [],
    ) if allow_llm else None
    if enhanced:
        result["answer"] = enhanced
        result["llm_used"] = True
        result["llm_model"] = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        if route == "general_knowledge" and not result.get("citations"):
            result["confidence"] = "medium_llm_general_knowledge"
            result["answer_mode"] = "llm_general_knowledge"
    else:
        result["llm_used"] = False
        result["answer"] = _apply_conversation_persona(
            question,
            result.get("answer") or "",
            confidence=result.get("confidence") or "",
            answer_mode=result.get("answer_mode") or "",
            route=route,
        )
    result = _answer_quality_gate(question, resolved_question, result)
    result["answer"] = _append_contextual_followup(
        question,
        result.get("answer") or "",
        route=route,
        answer_mode=result.get("answer_mode") or "",
        confidence=result.get("confidence") or "",
    )
    result["source_cards"] = _source_cards(result.get("citations") or [])
    result["source_presentation"] = "separate_cards"

    if save_memory:
        save_supabase_chat_message(
            workspace_id,
            conversation_id,
            "user",
            question,
            {"answer_mode": selected_mode, "route": route, "resolved_question": resolved_question},
        )
        save_supabase_chat_message(
            workspace_id,
            conversation_id,
            "assistant",
            result["answer"],
            {
                "citations": result.get("citations") or [],
                "confidence": result.get("confidence"),
                "quality_gate": result.get("quality_gate"),
            },
        )
    return result


def audit_supabase(event_type: str, workspace_id: Optional[str], document_id: Optional[str], payload: Dict[str, Any]) -> None:
    try:
        client = SupabaseRAGClient()
        client.rest("POST", RAG_AUDIT_TABLE, json_body={
            "event_type": event_type,
            "workspace_id": workspace_id,
            "document_id": document_id,
            "payload": payload,
        }, prefer="return=minimal")
    except Exception:
        # Auditing should not block document operations.
        return
