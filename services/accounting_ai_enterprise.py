"""Finiip Accounting AI Enterprise Layer (V86-V99).

This module extends the V85 deterministic accounting core into a practical
backend layer for accounting AI workflows:

V86  Document/RAG ingestion and source-cited answers
V87  Invoice/document text extraction and OCR-friendly parsing
V88  Journal entry creation and CSV/Excel-style exports
V89  Review queue for accountant approval and feedback learning
V90  Tax/accounting risk checker
V91  Smart follow-up questions
V92  End-to-end accounting agent pipeline
V93  Multi-company/workspace profile support
V94  Training/evaluation dashboard
V95  PostgreSQL/Supabase schema blueprint
V96  Frontend API contract generator
V97  Management/accounting reports
V98  Company memory/profile policies
V99  Production/security readiness checks

The implementation is offline-first and uses a local JSON store so it can run
immediately in the current project. When the product moves to Supabase/Postgres,
the function names and response shapes can stay stable while the storage layer
is swapped.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import unicodedata
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from services.accounting_ai_full import (
    ACCOUNT_NAMES,
    analyze_transaction,
    ask_accounting_ai,
    format_vnd,
    journal_totals,
    norm,
    parse_money,
    parse_percent,
    rule_catalog,
    solve_formula,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
EXPORT_DIR = DATA_DIR / "exports"
UPLOAD_DIR = DATA_DIR / "accounting_uploads_v86"
STORE_PATH = DATA_DIR / "accounting_enterprise_store_v86_v99.json"
AUDIT_LOG_PATH = DATA_DIR / "accounting_enterprise_audit_v86_v99.jsonl"

ENTERPRISE_VERSION = "v86_v99_enterprise_accounting_ai"

DEFAULT_STORE: Dict[str, Any] = {
    "version": ENTERPRISE_VERSION,
    "workspaces": {},
    "documents": {},
    "chunks": {},
    "review_items": {},
    "journal_entries": {},
    "feedback": [],
    "evaluation_runs": [],
    "company_memory": {},
}

SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".log", ".xml", ".html", ".htm"}


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _today() -> str:
    return date.today().isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:14]}"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        if isinstance(value, str):
            parsed = parse_money(value)
            if parsed is not None:
                return float(parsed)
        return float(value)
    except Exception:
        return default


def _round_money(value: Any) -> float:
    return round(_safe_float(value), 2)


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def load_store() -> Dict[str, Any]:
    _ensure_dirs()
    if not STORE_PATH.exists():
        save_store(DEFAULT_STORE.copy())
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = DEFAULT_STORE.copy()
    for key, value in DEFAULT_STORE.items():
        data.setdefault(key, value.copy() if isinstance(value, dict) else list(value) if isinstance(value, list) else value)
    data["version"] = ENTERPRISE_VERSION
    return data


def save_store(store: Dict[str, Any]) -> None:
    _ensure_dirs()
    tmp = STORE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STORE_PATH)


def audit(event_type: str, payload: Dict[str, Any]) -> None:
    _ensure_dirs()
    record = {"ts": _now(), "event_type": event_type, "payload": payload}
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def reset_enterprise_store() -> Dict[str, Any]:
    """Testing/dev helper: reset V86-V99 local store."""
    store = DEFAULT_STORE.copy()
    store["workspaces"] = {}
    store["documents"] = {}
    store["chunks"] = {}
    store["review_items"] = {}
    store["journal_entries"] = {}
    store["feedback"] = []
    store["evaluation_runs"] = []
    store["company_memory"] = {}
    save_store(store)
    return {"ok": True, "store_path": str(STORE_PATH), "version": ENTERPRISE_VERSION}


# ---------------------------------------------------------------------------
# V93/V98 - Workspace and company memory
# ---------------------------------------------------------------------------


def default_workspace_policy() -> Dict[str, Any]:
    return {
        "accounting_regime": "TT200/2014 hoặc chính sách nội bộ tùy doanh nghiệp",
        "currency": "VND",
        "asset_capitalization_threshold": 30_000_000,
        "default_vat_rate": 0.10,
        "expense_accounts": {
            "marketing": "641",
            "sales": "641",
            "admin": "642",
            "production": "627",
            "financial": "635",
        },
        "prepaid_allocation_default_months": 12,
        "ccdc_allocation_default_months": 24,
        "require_non_cash_payment_above": 20_000_000,
        "review_threshold_amount": 20_000_000,
        "auto_post_allowed": False,
    }


def create_or_update_workspace(
    workspace_id: str,
    name: Optional[str] = None,
    tax_code: Optional[str] = None,
    policy: Optional[Dict[str, Any]] = None,
    chart_of_accounts: Optional[Dict[str, str]] = None,
    users: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    store = load_store()
    current = store["workspaces"].get(workspace_id, {})
    merged_policy = default_workspace_policy()
    merged_policy.update(current.get("policy", {}))
    if policy:
        merged_policy.update(policy)
    workspace = {
        "workspace_id": workspace_id,
        "name": name or current.get("name") or workspace_id,
        "tax_code": tax_code if tax_code is not None else current.get("tax_code"),
        "policy": merged_policy,
        "chart_of_accounts": chart_of_accounts or current.get("chart_of_accounts") or ACCOUNT_NAMES,
        "users": users if users is not None else current.get("users", []),
        "created_at": current.get("created_at") or _now(),
        "updated_at": _now(),
    }
    store["workspaces"][workspace_id] = workspace
    store["company_memory"].setdefault(workspace_id, [])
    save_store(store)
    audit("workspace_upsert", {"workspace_id": workspace_id})
    return workspace


def get_workspace(workspace_id: str = "default") -> Dict[str, Any]:
    store = load_store()
    if workspace_id not in store["workspaces"]:
        return create_or_update_workspace(workspace_id, name="Default Accounting Workspace")
    return store["workspaces"][workspace_id]


def list_workspaces() -> Dict[str, Any]:
    store = load_store()
    if not store["workspaces"]:
        create_or_update_workspace("default", name="Default Accounting Workspace")
        store = load_store()
    return {"version": ENTERPRISE_VERSION, "items": list(store["workspaces"].values()), "count": len(store["workspaces"])}


def remember_company_fact(workspace_id: str, fact: str, category: str = "policy", source: str = "user") -> Dict[str, Any]:
    store = load_store()
    get_workspace(workspace_id)
    store = load_store()
    item = {"memory_id": _id("mem"), "workspace_id": workspace_id, "category": category, "fact": fact, "source": source, "created_at": _now()}
    store["company_memory"].setdefault(workspace_id, []).append(item)
    save_store(store)
    audit("company_memory_add", {"workspace_id": workspace_id, "memory_id": item["memory_id"]})
    return item


def list_company_memory(workspace_id: str = "default") -> Dict[str, Any]:
    store = load_store()
    return {"workspace_id": workspace_id, "items": store.get("company_memory", {}).get(workspace_id, [])}


# ---------------------------------------------------------------------------
# V86 - Document extraction, chunking, RAG-style index/search
# ---------------------------------------------------------------------------


def normalize_extracted_text_for_rag(text: str) -> str:
    """Make extracted PDF/DOC text easier to read and chunk.

    Many Vietnamese legal PDFs contain a text layer where words are glued
    together (for example ``HàNội,ngày20tháng4``). The normalizer keeps the
    original content faithful, but adds safe whitespace/newlines around legal
    headings, page markers, punctuation, and number/word boundaries so Admin UI
    previews and RAG chunks are human-readable.
    """
    s = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not s.strip():
        return ""

    # Keep page markers on their own lines before other cleanup runs.
    s = re.sub(r"\s*---\s*page\s*(\d+)\s*---\s*", r"\n\n--- page \1 ---\n", s, flags=re.I)

    # Targeted legal-PDF fixes for common Vietnamese official document headers.
    replacements = {
        "CỘNGHÒAXÃHỘICHỦNGHĨAVIỆTNAM": "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM",
        "CỘNGHÒA": "CỘNG HÒA",
        "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAMĐộc": "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc",
        "Độclập": "Độc lập",
        "Tựdo": "Tự do",
        "Hạnhphúc": "Hạnh phúc",
        "BỘTÀICHÍNH": "BỘ TÀI CHÍNH",
        "BỘ TÀICHÍNH": "BỘ TÀI CHÍNH",
        "TÀICHÍNH": "TÀI CHÍNH",
        "BÁO CÁOTÀICHÍNH": "BÁO CÁO TÀI CHÍNH",
        "BÁO CÁOTÀI CHÍNH": "BÁO CÁO TÀI CHÍNH",
        "HỢP NHẤTCăn": "HỢP NHẤT\nCăn",
        "SỬAĐỔI": "SỬA ĐỔI",
        "THÔNG TƯSỬA": "THÔNG TƯ\nSỬA",
        "THÔNG TƯ SỬA": "THÔNG TƯ\nSỬA",
        "HàNội": "Hà Nội",
        "ngày20tháng4năm2026": "ngày 20 tháng 4 năm 2026",
        "TT-BTCHà": "TT-BTC\nHà",
        "2026THÔNG TƯ": "2026\n\nTHÔNG TƯ",
        "---------------Số": "\nSố",
        "-------CỘNG": "\nCỘNG",
        "Nơi nhận:-": "Nơi nhận:\n-",
        "sốđiều": "số điều",
        "chứcnăng": "chức năng",
        "Nghịđịnh": "Nghị định",
        "pháplập": "pháp lập",
        "phápluật": "pháp luật",
        "trữquốc": "trữ quốc",
        "BÀYBÁO": "BÀY BÁO",
    }
    for old, new in replacements.items():
        s = s.replace(old, new)

    # Space between Vietnamese letters and numbers: ngày20 -> ngày 20, 2026THÔNG -> 2026 THÔNG.
    letter = r"A-Za-zÀ-ỹĐđ"
    s = re.sub(fr"(?<=[{letter}])(?=\d)", " ", s)
    s = re.sub(fr"(?<=\d)(?=[{letter}])", " ", s)

    # Add a space after punctuation if the next character is a letter.
    s = re.sub(fr"([,:;.!?])(?=[{letter}])", r"\1 ", s)

    # Add a soft boundary between lowercase and uppercase words: phúcSố -> phúc Số.
    # Use explicit Vietnamese lowercase/uppercase alphabets; a raw Unicode range
    # like à-ỹ also contains uppercase accented characters and would split words
    # such as CỘNG into CỘ NG.
    lower_vn = "a-záàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ"
    upper_vn = "A-ZÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴĐ"
    s = re.sub(fr"(?<=[{lower_vn}])(?=[{upper_vn}])", " ", s)

    # Put legal structural markers on separate lines. This improves chunking.
    s = re.sub(r"\s*(BỘ\s+TÀI\s+CHÍNH)\s*", r"\n\1\n", s, flags=re.I)
    s = re.sub(r"\s*(CỘNG\s+HÒA\s+XÃ\s+HỘI\s+CHỦ\s+NGHĨA\s+VIỆT\s+NAM)\s*", r"\n\1\n", s, flags=re.I)
    s = re.sub(r"\s*(Độc\s+lập\s*-\s*Tự\s+do\s*-\s*Hạnh\s+phúc)\s*", r"\n\1\n", s, flags=re.I)
    s = re.sub(r"(?<!\n)(Số\s*:\s*\d+)", r"\n\1", s, flags=re.I)
    s = re.sub(r"(?<!\n)(THÔNG\s+TƯ)\s*", r"\n\n\1\n", s, flags=re.I)
    s = re.sub(r"(?<!\n)(Điều\s+\d+\s*\.)", r"\n\n\1", s, flags=re.I)
    s = re.sub(r"(?<!\n)(PHỤ\s+LỤC\s+[IVXLC\d]+)", r"\n\n\1", s, flags=re.I)
    s = re.sub(r"(?<!\n)(Nơi\s+nhận\s*:)", r"\n\n\1", s, flags=re.I)

    # Normalize hyphen separators and bullets without destroying table content.
    s = re.sub(r"\n\s*-(?!-)\s*", "\n- ", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def extract_text_from_bytes(filename: str, content: bytes) -> Dict[str, Any]:
    """Extract text from common accounting upload formats.

    Supported best-effort formats: txt/md/csv/json/html, PDF via pypdf if
    installed, DOCX via python-docx if installed, XLSX via openpyxl if installed.
    Image OCR is intentionally optional because OCR engines vary by environment.
    """
    filename = filename or "upload.txt"
    suffix = Path(filename).suffix.lower()
    sha = _sha256_bytes(content)
    text = ""
    parser = "binary_fallback"
    warnings: List[str] = []

    if suffix in SUPPORTED_TEXT_EXTENSIONS or not suffix:
        for enc in ("utf-8", "utf-8-sig", "cp1258", "latin-1"):
            try:
                text = content.decode(enc)
                parser = f"text/{enc}"
                break
            except Exception:
                continue
    elif suffix in {".pdf", ".docx", ".xlsx", ".xlsm"}:
        try:
            from services.rag_v66_v67 import read_upload_bytes
            text = read_upload_bytes(filename, content)
            parser = "finiip-v110-reader"
        except Exception as exc:
            warnings.append(f"Không đọc được file bằng Finiip V110 reader: {exc}")
    elif suffix in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
        try:
            from PIL import Image  # type: ignore
            import pytesseract  # type: ignore

            image = Image.open(io.BytesIO(content))
            text = pytesseract.image_to_string(image, lang="vie+eng")
            parser = "pytesseract"
        except Exception as exc:
            warnings.append(f"Không OCR được ảnh trong môi trường hiện tại: {exc}")

    if not text:
        # Keep small binary marker for traceability, but not raw bytes.
        text = f"[Không trích xuất được text tự động từ {filename}. sha256={sha}]"
        warnings.append("File cần OCR/parser chuyên dụng hoặc upload bản text/PDF có text layer.")

    text = normalize_extracted_text_for_rag(text)

    return {
        "filename": filename,
        "extension": suffix,
        "sha256": sha,
        "parser": parser,
        "text": text,
        "char_count": len(text),
        "warnings": warnings,
    }


def split_document_into_chunks(text: str, max_chars: int = 1200, overlap: int = 160) -> List[Dict[str, Any]]:
    """Chunk by headings/articles first, then by paragraph/char budget."""
    clean = normalize_extracted_text_for_rag(text or "")
    if not clean:
        return []

    # Split before legal/accounting structural headings.
    boundary = re.compile(r"(?=\n\s*(?:#{1,6}\s+|Điều\s+\d+|Khoản\s+\d+|Mục\s+\d+|Chương\s+[IVXLC\d]+|Article\s+\d+))", re.I)
    sections = [s.strip() for s in boundary.split("\n" + clean) if s.strip()]
    chunks: List[Dict[str, Any]] = []
    section_idx = 0
    for section in sections:
        section_idx += 1
        heading = section.split("\n", 1)[0].strip()[:180]
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", section) if p.strip()]
        buf = ""
        for p in paragraphs:
            if len(buf) + len(p) + 2 <= max_chars:
                buf = (buf + "\n\n" + p).strip()
            else:
                if buf:
                    chunks.append({"section": section_idx, "heading": heading, "content": buf})
                # hard split long paragraphs
                start = 0
                while len(p) - start > max_chars:
                    part = p[start:start + max_chars]
                    chunks.append({"section": section_idx, "heading": heading, "content": part})
                    start += max_chars - overlap
                buf = p[start:].strip()
        if buf:
            chunks.append({"section": section_idx, "heading": heading, "content": buf})
    for i, c in enumerate(chunks, 1):
        c["chunk_no"] = i
        c["word_count"] = len(c["content"].split())
    return chunks


def classify_document(title: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    q = norm(" ".join([title or "", text[:4000] or "", json.dumps(metadata or {}, ensure_ascii=False)]))
    if any(k in q for k in ["hoa don", "invoice", "mau so", "ky hieu", "tong tien thanh toan"]):
        return "invoice"
    if any(k in q for k in ["thue", "gtgt", "tndn", "tncn", "khau tru", "hoa don dien tu"]):
        return "tax_legal"
    if any(k in q for k in ["quy trinh", "phe duyet", "noi bo", "kiem soat", "workflow"]):
        return "internal_process"
    if any(k in q for k in ["sao ke", "ngan hang", "statement"]):
        return "bank_statement"
    if any(k in q for k in ["bang luong", "bhxh", "luong"]):
        return "payroll"
    if any(k in q for k in ["so cai", "nhat ky chung", "bang can doi", "cong no"]):
        return "accounting_book"
    return "knowledge"


def add_document(
    title: str,
    content: str,
    workspace_id: str = "default",
    source_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    workspace = get_workspace(workspace_id)
    store = load_store()
    metadata = metadata or {}
    source_type = source_type or classify_document(title, content, metadata)
    document_id = _id("doc")
    content_hash = _sha256_text(content)
    chunks = split_document_into_chunks(content)
    doc = {
        "document_id": document_id,
        "workspace_id": workspace_id,
        "title": title,
        "source_type": source_type,
        "content_sha256": content_hash,
        "metadata": metadata,
        "status": "active",
        "chunk_count": len(chunks),
        "char_count": len(content or ""),
        "created_at": _now(),
        "updated_at": _now(),
    }
    store["documents"][document_id] = doc
    for c in chunks:
        chunk_id = _id("chk")
        store["chunks"][chunk_id] = {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "workspace_id": workspace_id,
            "title": title,
            "source_type": source_type,
            "section": c["section"],
            "chunk_no": c["chunk_no"],
            "heading": c["heading"],
            "content": c["content"],
            "tokens": sorted(set(_tokens(c["content"])))[:500],
            "created_at": _now(),
        }
    save_store(store)
    audit("document_add", {"workspace_id": workspace_id, "document_id": document_id, "chunk_count": len(chunks)})
    return {"workspace": workspace["workspace_id"], "document": doc, "chunks_added": len(chunks)}


def add_uploaded_document(
    filename: str,
    content: bytes,
    workspace_id: str = "default",
    title: Optional[str] = None,
    source_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    extracted = extract_text_from_bytes(filename, content)
    _ensure_dirs()
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(filename).name) or "upload.bin"
    saved_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{safe_name}"
    saved_path = UPLOAD_DIR / saved_name
    saved_path.write_bytes(content)
    meta = dict(metadata or {})
    meta.update({
        "filename": filename,
        "saved_path": str(saved_path.relative_to(ROOT_DIR)),
        "parser": extracted["parser"],
        "sha256": extracted["sha256"],
        "warnings": extracted["warnings"],
    })
    result = add_document(
        title=title or filename,
        content=extracted["text"],
        workspace_id=workspace_id,
        source_type=source_type,
        metadata=meta,
    )
    result["extraction"] = {k: v for k, v in extracted.items() if k != "text"}
    return result


def _tokens(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-zA-Z0-9_]+", norm(text)) if len(t) > 1]


def search_documents(
    query: str,
    workspace_id: str = "default",
    source_types: Optional[List[str]] = None,
    limit: int = 6,
) -> Dict[str, Any]:
    store = load_store()
    source_types = source_types or []
    q_tokens = _tokens(query)
    q_counter = Counter(q_tokens)
    results: List[Dict[str, Any]] = []
    for chunk in store.get("chunks", {}).values():
        if chunk.get("workspace_id") != workspace_id:
            continue
        doc = store.get("documents", {}).get(chunk.get("document_id"), {})
        if doc.get("status") != "active":
            continue
        if source_types and chunk.get("source_type") not in source_types:
            continue
        haystack = norm(" ".join([chunk.get("title", ""), chunk.get("heading", ""), chunk.get("content", "")]))
        c_tokens = set(chunk.get("tokens") or _tokens(haystack))
        lexical = sum(1 for t in q_tokens if t in c_tokens)
        phrase_bonus = 4 if norm(query) and norm(query) in haystack else 0
        important_bonus = 0
        for term in ["vat", "gtgt", "tndn", "hoa don", "khau hao", "cong no", "luong", "bhxh", "tai san"]:
            if term in norm(query) and term in haystack:
                important_bonus += 2
        score = lexical + phrase_bonus + important_bonus
        if score <= 0:
            continue
        snippet = chunk.get("content", "")[:700]
        results.append({
            "score": score,
            "chunk_id": chunk.get("chunk_id"),
            "document_id": chunk.get("document_id"),
            "title": chunk.get("title"),
            "source_type": chunk.get("source_type"),
            "heading": chunk.get("heading"),
            "chunk_no": chunk.get("chunk_no"),
            "snippet": snippet,
            "metadata": doc.get("metadata", {}),
        })
    results.sort(key=lambda r: (r["score"], r["title"] or ""), reverse=True)
    return {"query": query, "workspace_id": workspace_id, "count": len(results[:limit]), "results": results[:limit]}


def answer_with_enterprise_rag(question: str, workspace_id: str = "default", limit: int = 6) -> Dict[str, Any]:
    enterprise_sources = search_documents(question, workspace_id=workspace_id, limit=limit)["results"]
    base_answer = ask_accounting_ai(question, limit=limit)
    if enterprise_sources:
        bullets = []
        for src in enterprise_sources[:4]:
            bullets.append(f"- Theo {src['title']} / {src['heading']}: {src['snippet'][:240].strip()}")
        answer = (
            "Dựa trên tài liệu đã nạp trong workspace và bộ rule kế toán hiện có:\n"
            + "\n".join(bullets)
            + "\n\nGợi ý xử lý: cần đối chiếu chứng từ, chính sách công ty và người kế toán duyệt trước khi ghi sổ."
        )
    else:
        answer = base_answer.get("answer") or "Chưa có nguồn nội bộ phù hợp. Hãy upload thông tư/quy trình/chứng từ rồi hỏi lại."
    return {
        "version": ENTERPRISE_VERSION,
        "workspace_id": workspace_id,
        "question": question,
        "answer": answer,
        "enterprise_sources": enterprise_sources,
        "base_sources": base_answer.get("sources", []),
        "confidence": "medium" if enterprise_sources else "low_without_enterprise_sources",
        "needs_human_review": True,
    }


# ---------------------------------------------------------------------------
# V87 - Invoice/document parser
# ---------------------------------------------------------------------------


def _first_match(patterns: Sequence[str], text: str, flags: int = re.I) -> Optional[str]:
    for p in patterns:
        m = re.search(p, text, flags)
        if m:
            return (m.group(1) if m.groups() else m.group(0)).strip()
    return None


def parse_invoice_text(text: str) -> Dict[str, Any]:
    raw = text or ""
    normalized = norm(raw)
    invoice_no = _first_match([
        r"(?:số|so|invoice\s*no\.?|no\.?|số hóa đơn|so hoa don)\s*[:#-]?\s*([A-Z0-9\-/\.]+)",
        r"(?:mẫu số|mau so).*?(?:ký hiệu|ky hieu).*?(?:số|so)\s*[:#-]?\s*([A-Z0-9\-/\.]+)",
    ], raw)
    serial = _first_match([r"(?:ký hiệu|ky hieu|serial)\s*[:#-]?\s*([A-Z0-9\-/\.]+)"], raw)
    date_text = _first_match([
        r"(?:ngày|ngay|date)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(\d{4}-\d{2}-\d{2})",
    ], raw)
    seller_tax_code = _first_match([
        r"(?:mã số thuế|ma so thue|mst)\s*(?:người bán|nguoi ban|seller)?\s*[:#-]?\s*([0-9\-]{10,15})"
    ], raw)
    # try buyer MST after buyer marker
    buyer_tax_code = None
    buyer_part = re.split(r"người mua|nguoi mua|buyer", raw, flags=re.I)
    if len(buyer_part) > 1:
        buyer_tax_code = _first_match([r"(?:mã số thuế|ma so thue|mst)\s*[:#-]?\s*([0-9\-]{10,15})"], buyer_part[-1])

    seller_name = _first_match([
        r"(?:đơn vị bán hàng|don vi ban hang|người bán|nguoi ban|seller)\s*[:#-]?\s*(.+)",
    ], raw)
    buyer_name = _first_match([
        r"(?:đơn vị mua hàng|don vi mua hang|người mua|nguoi mua|buyer)\s*[:#-]?\s*(.+)",
    ], raw)

    total_before_tax = None
    tax_amount = None
    total_payment = None
    patterns_amount = {
        "total_before_tax": [
            r"(?:cộng tiền hàng|cong tien hang|tiền hàng|tien hang|subtotal|chưa thuế|chua thue)\s*[:#-]?\s*([0-9\.,]+)",
        ],
        "tax_amount": [
            r"(?:tiền thuế gtgt|tien thue gtgt|thuế gtgt|thue gtgt|vat amount)\s*[:#-]?\s*([0-9\.,]+)",
        ],
        "total_payment": [
            r"(?:tổng cộng tiền thanh toán|tong cong tien thanh toan|tổng thanh toán|tong thanh toan|total payment|grand total)\s*[:#-]?\s*([0-9\.,]+)",
        ],
    }
    for key, patterns in patterns_amount.items():
        val = _first_match(patterns, raw)
        if val:
            parsed = parse_money(val)
            if key == "total_before_tax":
                total_before_tax = parsed
            elif key == "tax_amount":
                tax_amount = parsed
            elif key == "total_payment":
                total_payment = parsed

    vat_rate = parse_percent(raw)
    if vat_rate is None:
        if "khong chiu thue" in normalized or "khong thue" in normalized:
            vat_rate = 0.0
        elif tax_amount and total_before_tax:
            vat_rate = round(tax_amount / total_before_tax, 4) if total_before_tax else None

    # Fallback: choose largest money as total.
    if total_payment is None:
        monies = []
        for m in re.findall(r"\d{1,3}(?:[\.,]\d{3})+(?:[\.,]\d+)?|\d+", raw):
            val = parse_money(m)
            if val and val > 1000:
                monies.append(val)
        if monies:
            total_payment = max(monies)

    if total_before_tax is None and total_payment is not None and vat_rate is not None:
        if vat_rate > 0:
            total_before_tax = round(total_payment / (1 + vat_rate), 2)
            tax_amount = round(total_payment - total_before_tax, 2)
        else:
            total_before_tax = total_payment
            tax_amount = 0.0

    line_items = []
    for line in raw.splitlines():
        n = norm(line)
        if any(k in n for k in ["hang hoa", "dich vu", "san pham", "may tinh", "laptop", "van phong pham", "thue dich vu"]):
            amount = parse_money(line)
            line_items.append({"raw": line.strip(), "amount_guess": amount})

    missing = []
    for key, val in {
        "invoice_no": invoice_no,
        "date": date_text,
        "seller_tax_code": seller_tax_code,
        "total_payment": total_payment,
        "vat_rate": vat_rate,
    }.items():
        if val in {None, ""}:
            missing.append(key)

    return {
        "version": ENTERPRISE_VERSION,
        "invoice_no": invoice_no,
        "serial": serial,
        "date": date_text,
        "seller_name": seller_name,
        "seller_tax_code": seller_tax_code,
        "buyer_name": buyer_name,
        "buyer_tax_code": buyer_tax_code,
        "total_before_tax": _round_money(total_before_tax),
        "vat_rate": vat_rate,
        "tax_amount": _round_money(tax_amount),
        "total_payment": _round_money(total_payment),
        "line_items": line_items[:20],
        "missing_fields": missing,
        "quality": "good" if len(missing) <= 2 else "needs_review",
        "raw_preview": raw[:1000],
    }


# ---------------------------------------------------------------------------
# V88 - Journal entries and export
# ---------------------------------------------------------------------------


def create_journal_entry(
    description: str,
    amount: Optional[float] = None,
    vat_rate: Optional[float] = None,
    workspace_id: str = "default",
    source_document_id: Optional[str] = None,
    amount_includes_vat: bool = True,
    has_invoice: Optional[bool] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    analysis = analyze_transaction(
        description=description,
        amount=amount,
        vat_rate=vat_rate,
        amount_includes_vat=amount_includes_vat,
        has_invoice=has_invoice,
        extra=extra or {},
    )
    store = load_store()
    entry_id = _id("je")
    entry = {
        "entry_id": entry_id,
        "workspace_id": workspace_id,
        "entry_date": (extra or {}).get("entry_date") or _today(),
        "description": description,
        "source_document_id": source_document_id,
        "analysis": analysis,
        "journal_lines": analysis.get("journal_lines", []),
        "journal_check": analysis.get("journal_check", {}),
        "status": "draft",
        "created_at": _now(),
        "updated_at": _now(),
    }
    store["journal_entries"][entry_id] = entry
    save_store(store)
    audit("journal_create", {"workspace_id": workspace_id, "entry_id": entry_id})
    return entry


def list_journal_entries(workspace_id: str = "default", status: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    store = load_store()
    items = [x for x in store.get("journal_entries", {}).values() if x.get("workspace_id") == workspace_id]
    if status:
        items = [x for x in items if x.get("status") == status]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"workspace_id": workspace_id, "count": len(items[:limit]), "items": items[:limit]}


def export_journal_csv(workspace_id: str = "default", status: Optional[str] = None) -> Dict[str, Any]:
    entries = list_journal_entries(workspace_id, status=status, limit=10_000)["items"]
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"journal_{workspace_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.csv"
    path = EXPORT_DIR / filename
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["entry_id", "date", "description", "side", "account_code", "account_name", "amount", "status", "risk_level"])
        for entry in entries:
            risk_level = entry.get("analysis", {}).get("risk_review", {}).get("risk_level")
            for line in entry.get("journal_lines", []):
                writer.writerow([
                    entry.get("entry_id"),
                    entry.get("entry_date"),
                    entry.get("description"),
                    line.get("side"),
                    line.get("account_code"),
                    line.get("account_name"),
                    line.get("amount"),
                    entry.get("status"),
                    risk_level,
                ])
    audit("journal_export_csv", {"workspace_id": workspace_id, "path": str(path)})
    return {"ok": True, "path": str(path), "relative_path": str(path.relative_to(ROOT_DIR)), "rows": sum(len(e.get("journal_lines", [])) for e in entries)}


def export_journal_xlsx(workspace_id: str = "default", status: Optional[str] = None) -> Dict[str, Any]:
    try:
        import openpyxl  # type: ignore
    except Exception as exc:
        return {"ok": False, "error": f"openpyxl chưa khả dụng: {exc}"}
    entries = list_journal_entries(workspace_id, status=status, limit=10_000)["items"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Nhat ky chung"
    headers = ["entry_id", "date", "description", "side", "account_code", "account_name", "amount", "status", "risk_level"]
    ws.append(headers)
    for entry in entries:
        risk_level = entry.get("analysis", {}).get("risk_review", {}).get("risk_level")
        for line in entry.get("journal_lines", []):
            ws.append([
                entry.get("entry_id"),
                entry.get("entry_date"),
                entry.get("description"),
                line.get("side"),
                line.get("account_code"),
                line.get("account_name"),
                line.get("amount"),
                entry.get("status"),
                risk_level,
            ])
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 22
    filename = f"journal_{workspace_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xlsx"
    path = EXPORT_DIR / filename
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    audit("journal_export_xlsx", {"workspace_id": workspace_id, "path": str(path)})
    return {"ok": True, "path": str(path), "relative_path": str(path.relative_to(ROOT_DIR)), "entries": len(entries)}


# ---------------------------------------------------------------------------
# V89 - Review queue and feedback learning
# ---------------------------------------------------------------------------


def create_review_item(
    workspace_id: str,
    item_type: str,
    title: str,
    payload: Dict[str, Any],
    risk_level: str = "medium",
    priority: Optional[str] = None,
) -> Dict[str, Any]:
    store = load_store()
    review_id = _id("rev")
    item = {
        "review_id": review_id,
        "workspace_id": workspace_id,
        "item_type": item_type,
        "title": title,
        "payload": payload,
        "risk_level": risk_level,
        "priority": priority or ("high" if risk_level in {"high", "critical"} else "normal"),
        "status": "pending",
        "reviewer_note": None,
        "correction": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    store["review_items"][review_id] = item
    save_store(store)
    audit("review_create", {"workspace_id": workspace_id, "review_id": review_id})
    return item


def list_review_queue(workspace_id: str = "default", status: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    store = load_store()
    items = [x for x in store.get("review_items", {}).values() if x.get("workspace_id") == workspace_id]
    if status:
        items = [x for x in items if x.get("status") == status]
    weight = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    items.sort(key=lambda x: (weight.get(x.get("risk_level"), 0), x.get("created_at", "")), reverse=True)
    return {"workspace_id": workspace_id, "count": len(items[:limit]), "items": items[:limit]}


def update_review_item(review_id: str, status: str, reviewer_note: Optional[str] = None, correction: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    allowed = {"pending", "approved", "rejected", "need_more_info", "corrected", "posted"}
    if status not in allowed:
        raise ValueError(f"status phải thuộc {sorted(allowed)}")
    store = load_store()
    if review_id not in store.get("review_items", {}):
        raise KeyError("Không tìm thấy review item")
    item = store["review_items"][review_id]
    item["status"] = status
    item["reviewer_note"] = reviewer_note
    item["correction"] = correction
    item["updated_at"] = _now()
    if correction:
        store["feedback"].append({
            "feedback_id": _id("fb"),
            "workspace_id": item.get("workspace_id"),
            "review_id": review_id,
            "item_type": item.get("item_type"),
            "original_payload": item.get("payload"),
            "correction": correction,
            "note": reviewer_note,
            "created_at": _now(),
        })
    save_store(store)
    audit("review_update", {"review_id": review_id, "status": status})
    return item


# ---------------------------------------------------------------------------
# V90/V91 - Risk gate and smart questions
# ---------------------------------------------------------------------------


def tax_risk_check(transaction: Dict[str, Any], workspace_id: str = "default") -> Dict[str, Any]:
    ws = get_workspace(workspace_id)
    policy = ws.get("policy", default_workspace_policy())
    desc = transaction.get("description") or transaction.get("content") or ""
    amount = _safe_float(transaction.get("amount") or transaction.get("total_payment"))
    has_invoice = transaction.get("has_invoice")
    payment_method = norm(transaction.get("payment_method") or transaction.get("extra", {}).get("payment_method") or desc)
    q = norm(desc)
    risks: List[Dict[str, Any]] = []

    non_cash_threshold = _safe_float(policy.get("require_non_cash_payment_above"), 20_000_000)
    if amount >= non_cash_threshold and any(k in payment_method for k in ["tien mat", "cash", "111"]):
        risks.append({"code": "CASH_OVER_THRESHOLD", "level": "high", "message": "Giao dịch giá trị lớn thanh toán tiền mặt: cần kiểm tra điều kiện khấu trừ/chi phí được trừ theo chính sách thuế."})
    if has_invoice is False and any(k in q for k in ["chi phi", "mua", "dich vu", "tiep khach", "marketing", "van phong"]):
        risks.append({"code": "MISSING_INVOICE", "level": "high", "message": "Chi phí chưa có hóa đơn/chứng từ hợp lệ."})
    if any(k in q for k in ["tiep khach", "qua tang", "bieng tang", "phuc loi", "ca nhan", "khong hoa don"]):
        risks.append({"code": "DEDUCTIBILITY_REVIEW", "level": "medium", "message": "Chi phí có khả năng cần xét điều kiện được trừ và hồ sơ kèm theo."})
    if any(k in q for k in ["luong", "thuong", "phu cap"]):
        risks.append({"code": "PAYROLL_SUPPORTING_DOCS", "level": "medium", "message": "Cần hợp đồng lao động, bảng công, bảng lương, quyết định thưởng/phụ cấp và chứng từ thanh toán."})
    if any(k in q for k in ["tai san", "may tinh", "oto", "may moc", "thiet bi"]):
        threshold = _safe_float(policy.get("asset_capitalization_threshold"), 30_000_000)
        if amount >= threshold:
            risks.append({"code": "FIXED_ASSET_CLASSIFICATION", "level": "medium", "message": "Giá trị có thể đạt ngưỡng TSCĐ theo chính sách công ty; cần xác định ghi 211 hay 242/153/642."})
    if transaction.get("vat_rate") is None and any(k in q for k in ["hoa don", "vat", "gtgt", "mua", "ban"]):
        risks.append({"code": "VAT_RATE_MISSING", "level": "medium", "message": "Chưa có thuế suất VAT; cần bổ sung để tách thuế đúng."})
    if amount <= 0:
        risks.append({"code": "INVALID_AMOUNT", "level": "high", "message": "Số tiền không hợp lệ hoặc chưa đọc được."})

    levels = [r["level"] for r in risks]
    rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    risk_level = max(levels, key=lambda x: rank.get(x, 0)) if levels else "low"
    return {
        "workspace_id": workspace_id,
        "risk_level": risk_level,
        "risk_count": len(risks),
        "risks": risks,
        "decision": "review_required" if risk_level in {"medium", "high", "critical"} else "draft_allowed",
        "policy_used": {k: policy.get(k) for k in ["asset_capitalization_threshold", "require_non_cash_payment_above", "review_threshold_amount"]},
    }


def smart_followup_questions(transaction: Dict[str, Any], workspace_id: str = "default") -> Dict[str, Any]:
    q = norm(transaction.get("description") or "")
    questions: List[Dict[str, str]] = []
    amount = transaction.get("amount") or transaction.get("total_payment")
    if not amount:
        questions.append({"field": "amount", "question": "Số tiền giao dịch/tổng thanh toán là bao nhiêu?"})
    if transaction.get("vat_rate") is None and any(k in q for k in ["hoa don", "vat", "gtgt", "mua", "ban", "dich vu"]):
        questions.append({"field": "vat_rate", "question": "Thuế suất VAT là 0%, 5%, 8%, 10% hay không chịu thuế?"})
    if transaction.get("has_invoice") is None and any(k in q for k in ["mua", "chi", "dich vu", "tiep khach", "marketing"]):
        questions.append({"field": "has_invoice", "question": "Có hóa đơn/chứng từ hợp lệ không?"})
    if not transaction.get("payment_method") and any(k in q for k in ["mua", "ban", "thanh toan", "chi", "thu"]):
        questions.append({"field": "payment_method", "question": "Thanh toán bằng tiền mặt, chuyển khoản hay còn công nợ?"})
    if any(k in q for k in ["may tinh", "thiet bi", "tai san", "cong cu", "laptop", "may moc"]):
        questions.append({"field": "asset_policy", "question": "Doanh nghiệp muốn ghi nhận là TSCĐ, công cụ dụng cụ, chi phí trả trước hay chi phí trong kỳ?"})
        questions.append({"field": "department", "question": "Tài sản/chi phí dùng cho bộ phận bán hàng, quản lý hay sản xuất?"})
    if any(k in q for k in ["luong", "thuong", "bhxh", "tncn"]):
        questions.append({"field": "payroll_docs", "question": "Có bảng công, bảng lương, hợp đồng và quyết định lương/thưởng chưa?"})
    return {"workspace_id": workspace_id, "questions": questions, "count": len(questions), "can_finalize_without_more_info": len(questions) == 0}


# ---------------------------------------------------------------------------
# V92 - End-to-end agent pipeline
# ---------------------------------------------------------------------------


def run_accounting_agent_pipeline(
    text: str,
    workspace_id: str = "default",
    filename: Optional[str] = None,
    create_review: bool = True,
) -> Dict[str, Any]:
    doc_result = add_document(
        title=filename or f"manual_input_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        content=text,
        workspace_id=workspace_id,
        source_type=classify_document(filename or "manual", text),
        metadata={"pipeline": "v92_agent"},
    )
    doc = doc_result["document"]
    parsed_invoice = parse_invoice_text(text)
    description = text[:500]
    amount = parsed_invoice.get("total_payment") or parse_money(text)
    vat_rate = parsed_invoice.get("vat_rate")
    analysis = create_journal_entry(
        description=description,
        amount=amount,
        vat_rate=vat_rate,
        workspace_id=workspace_id,
        source_document_id=doc["document_id"],
        has_invoice=parsed_invoice.get("invoice_no") is not None or "hoa don" in norm(text),
        extra={"invoice": parsed_invoice},
    )
    risk = tax_risk_check({"description": description, "amount": amount, "vat_rate": vat_rate, "has_invoice": parsed_invoice.get("invoice_no") is not None}, workspace_id=workspace_id)
    followups = smart_followup_questions({"description": description, "amount": amount, "vat_rate": vat_rate, "has_invoice": parsed_invoice.get("invoice_no") is not None}, workspace_id=workspace_id)
    review_item = None
    if create_review and (risk["decision"] == "review_required" or analysis.get("analysis", {}).get("decision") != "auto_draft_allowed"):
        review_item = create_review_item(
            workspace_id=workspace_id,
            item_type="agent_pipeline_transaction",
            title=f"Duyệt chứng từ: {filename or doc['title']}",
            payload={"document": doc, "invoice": parsed_invoice, "journal_entry": analysis, "risk": risk, "followups": followups},
            risk_level=risk["risk_level"],
        )
    return {
        "version": ENTERPRISE_VERSION,
        "workspace_id": workspace_id,
        "steps": [
            {"step": "document_ingested", "ok": True, "document_id": doc["document_id"]},
            {"step": "invoice_parsed", "ok": True, "quality": parsed_invoice["quality"]},
            {"step": "journal_drafted", "ok": True, "entry_id": analysis["entry_id"]},
            {"step": "risk_checked", "ok": True, "risk_level": risk["risk_level"]},
            {"step": "review_created", "ok": review_item is not None, "review_id": review_item.get("review_id") if review_item else None},
        ],
        "document": doc,
        "invoice": parsed_invoice,
        "journal_entry": analysis,
        "risk": risk,
        "followups": followups,
        "review_item": review_item,
    }


# ---------------------------------------------------------------------------
# V94 - Evaluation dashboard
# ---------------------------------------------------------------------------


def default_evaluation_cases() -> List[Dict[str, Any]]:
    return [
        {"case_id": "eval_purchase_vat", "description": "Mua hàng hóa nhập kho chuyển khoản 11.000.000 VAT 10%", "amount": 11_000_000, "vat_rate": 0.10, "expect_accounts": ["156", "1331", "112"]},
        {"case_id": "eval_sale_vat", "description": "Bán hàng chưa thu tiền 22.000.000 VAT 10%", "amount": 22_000_000, "vat_rate": 0.10, "expect_accounts": ["131", "511", "3331"]},
        {"case_id": "eval_salary", "description": "Tính lương phải trả nhân viên bộ phận quản lý", "amount": 30_000_000, "expect_accounts": ["642", "334"]},
        {"case_id": "eval_supplier_payment", "description": "Chuyển khoản thanh toán công nợ nhà cung cấp", "amount": 15_000_000, "expect_accounts": ["331", "112"]},
        {"case_id": "eval_asset", "description": "Mua máy tính cho phòng kế toán 35 triệu có hóa đơn", "amount": 35_000_000, "vat_rate": 0.10, "expect_any": ["211", "242", "153", "642"]},
    ]


def run_evaluation(cases: Optional[List[Dict[str, Any]]] = None, workspace_id: str = "default") -> Dict[str, Any]:
    cases = cases or default_evaluation_cases()
    results = []
    passed = 0
    for case in cases:
        result = analyze_transaction(
            case.get("description", ""),
            amount=case.get("amount"),
            vat_rate=case.get("vat_rate"),
            amount_includes_vat=case.get("amount_includes_vat", True),
            has_invoice=case.get("has_invoice", True),
            extra=case.get("extra", {}),
        )
        accounts = {line.get("account_code") for line in result.get("journal_lines", [])}
        required = set(case.get("expect_accounts") or [])
        expect_any = set(case.get("expect_any") or [])
        ok_required = required.issubset(accounts) if required else True
        ok_any = bool(accounts & expect_any) if expect_any else True
        ok = ok_required and ok_any and result.get("journal_check", {}).get("is_balanced", True)
        passed += 1 if ok else 0
        results.append({
            "case_id": case.get("case_id"),
            "ok": ok,
            "expected_accounts": sorted(required),
            "expect_any": sorted(expect_any),
            "actual_accounts": sorted(a for a in accounts if a),
            "confidence": result.get("confidence"),
            "decision": result.get("decision"),
        })
    score = round(passed / len(cases), 4) if cases else 0.0
    run = {"run_id": _id("eval"), "workspace_id": workspace_id, "score": score, "passed": passed, "total": len(cases), "results": results, "created_at": _now()}
    store = load_store()
    store["evaluation_runs"].append(run)
    save_store(store)
    audit("evaluation_run", {"workspace_id": workspace_id, "run_id": run["run_id"], "score": score})
    return run


def quality_dashboard(workspace_id: str = "default") -> Dict[str, Any]:
    store = load_store()
    reviews = [x for x in store.get("review_items", {}).values() if x.get("workspace_id") == workspace_id]
    journals = [x for x in store.get("journal_entries", {}).values() if x.get("workspace_id") == workspace_id]
    docs = [x for x in store.get("documents", {}).values() if x.get("workspace_id") == workspace_id]
    evals = [x for x in store.get("evaluation_runs", []) if x.get("workspace_id") == workspace_id]
    risk_counts = Counter(x.get("risk_level", "unknown") for x in reviews)
    status_counts = Counter(x.get("status", "unknown") for x in reviews)
    source_counts = Counter(x.get("source_type", "unknown") for x in docs)
    return {
        "workspace_id": workspace_id,
        "documents": {"total": len(docs), "by_source_type": dict(source_counts)},
        "journal_entries": {"total": len(journals), "balanced": sum(1 for j in journals if j.get("journal_check", {}).get("is_balanced"))},
        "review_queue": {"total": len(reviews), "by_risk": dict(risk_counts), "by_status": dict(status_counts)},
        "feedback_count": len([f for f in store.get("feedback", []) if f.get("workspace_id") == workspace_id]),
        "last_evaluation": evals[-1] if evals else None,
        "recommendations": _dashboard_recommendations(docs, reviews, evals),
    }


def _dashboard_recommendations(docs: List[Dict[str, Any]], reviews: List[Dict[str, Any]], evals: List[Dict[str, Any]]) -> List[str]:
    recs = []
    if not docs:
        recs.append("Nên upload thông tư/quy trình/hồ sơ mẫu để RAG có nguồn trả lời.")
    if reviews and sum(1 for r in reviews if r.get("status") == "pending") > 10:
        recs.append("Review queue đang nhiều pending; nên thêm filter theo rủi ro cao trước.")
    if not evals:
        recs.append("Nên chạy evaluation định kỳ để đo chất lượng rule AI.")
    elif evals[-1].get("score", 0) < 0.8:
        recs.append("Điểm evaluation thấp; cần bổ sung rule/training examples cho nhóm nghiệp vụ sai.")
    if not recs:
        recs.append("Hệ thống ổn; tiếp tục bổ sung dữ liệu thật và feedback kế toán.")
    return recs


# ---------------------------------------------------------------------------
# V95 - Database/Supabase schema blueprint
# ---------------------------------------------------------------------------


def database_schema_blueprint() -> Dict[str, Any]:
    ddl = """
-- Finiip Accounting AI V95 schema blueprint
create table if not exists accounting_workspaces (
  workspace_id text primary key,
  name text not null,
  tax_code text,
  policy jsonb not null default '{}'::jsonb,
  chart_of_accounts jsonb not null default '{}'::jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists accounting_documents (
  document_id text primary key,
  workspace_id text references accounting_workspaces(workspace_id),
  title text not null,
  source_type text not null,
  content_sha256 text not null,
  metadata jsonb not null default '{}'::jsonb,
  status text not null default 'active',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists accounting_chunks (
  chunk_id text primary key,
  document_id text references accounting_documents(document_id),
  workspace_id text references accounting_workspaces(workspace_id),
  heading text,
  content text not null,
  token_vector jsonb,
  created_at timestamptz default now()
);

create table if not exists accounting_journal_entries (
  entry_id text primary key,
  workspace_id text references accounting_workspaces(workspace_id),
  source_document_id text references accounting_documents(document_id),
  entry_date date not null,
  description text not null,
  journal_lines jsonb not null,
  journal_check jsonb not null,
  status text not null default 'draft',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists accounting_review_items (
  review_id text primary key,
  workspace_id text references accounting_workspaces(workspace_id),
  item_type text not null,
  title text not null,
  payload jsonb not null,
  risk_level text not null,
  priority text not null default 'normal',
  status text not null default 'pending',
  reviewer_note text,
  correction jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists accounting_feedback (
  feedback_id text primary key,
  workspace_id text references accounting_workspaces(workspace_id),
  review_id text references accounting_review_items(review_id),
  item_type text not null,
  original_payload jsonb,
  correction jsonb,
  note text,
  created_at timestamptz default now()
);

create index if not exists idx_accounting_docs_workspace on accounting_documents(workspace_id, source_type, status);
create index if not exists idx_accounting_chunks_workspace on accounting_chunks(workspace_id);
create index if not exists idx_accounting_review_workspace on accounting_review_items(workspace_id, status, risk_level);
create index if not exists idx_accounting_journal_workspace on accounting_journal_entries(workspace_id, status, entry_date);
""".strip()
    return {"version": ENTERPRISE_VERSION, "database": "PostgreSQL/Supabase", "ddl": ddl, "migration_order": ["workspaces", "documents", "chunks", "journal_entries", "review_items", "feedback"]}


# ---------------------------------------------------------------------------
# V96 - Frontend API contract
# ---------------------------------------------------------------------------


def frontend_api_contract() -> Dict[str, Any]:
    endpoints = [
        {"method": "POST", "path": "/ai/v86/documents/upload", "screen": "DocumentUpload", "purpose": "Upload PDF/Word/Excel/text vào RAG workspace"},
        {"method": "POST", "path": "/ai/v86/documents", "screen": "DocumentEditor", "purpose": "Nạp tài liệu text trực tiếp"},
        {"method": "POST", "path": "/ai/v86/rag/ask", "screen": "AccountingChat", "purpose": "Hỏi AI kế toán có nguồn từ tài liệu"},
        {"method": "POST", "path": "/ai/v87/invoices/parse", "screen": "InvoiceOCR", "purpose": "Parse text hóa đơn/chứng từ"},
        {"method": "POST", "path": "/ai/v88/journal/create", "screen": "JournalDraft", "purpose": "Tạo bút toán nháp từ giao dịch"},
        {"method": "GET", "path": "/ai/v88/journal", "screen": "JournalList", "purpose": "Danh sách bút toán"},
        {"method": "POST", "path": "/ai/v88/journal/export", "screen": "ExportCenter", "purpose": "Xuất CSV/XLSX nhật ký chung"},
        {"method": "GET", "path": "/ai/v89/review-queue", "screen": "ReviewQueue", "purpose": "Duyệt/correct các đề xuất của AI"},
        {"method": "POST", "path": "/ai/v90/risk-check", "screen": "RiskPanel", "purpose": "Kiểm tra rủi ro thuế/chứng từ"},
        {"method": "POST", "path": "/ai/v92/agent/process-text", "screen": "AgentPipeline", "purpose": "Chạy pipeline OCR→RAG→bút toán→risk→review"},
        {"method": "POST", "path": "/ai/v93/workspaces", "screen": "WorkspaceSettings", "purpose": "Tạo/cập nhật hồ sơ công ty"},
        {"method": "GET", "path": "/ai/v94/dashboard", "screen": "AIDashboard", "purpose": "Đo chất lượng, số review, tài liệu, feedback"},
        {"method": "GET", "path": "/ai/v95/database-schema", "screen": "DevOps", "purpose": "Lấy DDL migrate PostgreSQL/Supabase"},
        {"method": "GET", "path": "/ai/v97/reports/monthly-summary", "screen": "Reports", "purpose": "Báo cáo quản trị/kế toán"},
        {"method": "GET", "path": "/ai/v99/production-readiness", "screen": "ProductionChecklist", "purpose": "Check bảo mật/production"},
    ]
    return {"version": ENTERPRISE_VERSION, "frontend_screens": sorted({e["screen"] for e in endpoints}), "endpoints": endpoints}


# ---------------------------------------------------------------------------
# V97 - Reports and closing checklist
# ---------------------------------------------------------------------------


def monthly_summary_report(workspace_id: str = "default") -> Dict[str, Any]:
    entries = list_journal_entries(workspace_id, limit=10_000)["items"]
    debit_by_account: Dict[str, float] = defaultdict(float)
    credit_by_account: Dict[str, float] = defaultdict(float)
    risk_by_level: Counter[str] = Counter()
    for entry in entries:
        risk_by_level[entry.get("analysis", {}).get("risk_review", {}).get("risk_level", "unknown")] += 1
        for line in entry.get("journal_lines", []):
            if line.get("side") == "debit":
                debit_by_account[line.get("account_code", "unknown")] += _safe_float(line.get("amount"))
            elif line.get("side") == "credit":
                credit_by_account[line.get("account_code", "unknown")] += _safe_float(line.get("amount"))
    revenue = sum(v for acc, v in credit_by_account.items() if str(acc).startswith("511"))
    expense = sum(v for acc, v in debit_by_account.items() if str(acc).startswith(("6", "8")))
    vat_input = debit_by_account.get("1331", 0.0) + debit_by_account.get("1332", 0.0)
    vat_output = credit_by_account.get("3331", 0.0)
    receivable = debit_by_account.get("131", 0.0) - credit_by_account.get("131", 0.0)
    payable = credit_by_account.get("331", 0.0) - debit_by_account.get("331", 0.0)
    return {
        "workspace_id": workspace_id,
        "entry_count": len(entries),
        "kpis": {
            "revenue_credit_511": revenue,
            "expense_debit_6_8": expense,
            "estimated_profit_before_tax": revenue - expense,
            "vat_input_133": vat_input,
            "vat_output_3331": vat_output,
            "vat_payable_estimate": vat_output - vat_input,
            "receivable_131_net": receivable,
            "payable_331_net": payable,
        },
        "debit_by_account": {acc: {"name": ACCOUNT_NAMES.get(acc, ""), "amount": amt} for acc, amt in sorted(debit_by_account.items())},
        "credit_by_account": {acc: {"name": ACCOUNT_NAMES.get(acc, ""), "amount": amt} for acc, amt in sorted(credit_by_account.items())},
        "risk_by_level": dict(risk_by_level),
        "closing_checklist": closing_checklist(workspace_id)["items"],
    }


def closing_checklist(workspace_id: str = "default") -> Dict[str, Any]:
    dashboard = quality_dashboard(workspace_id)
    items = [
        {"code": "BANK_RECON", "title": "Đối chiếu sổ phụ ngân hàng với TK 112", "required": True},
        {"code": "CASH_COUNT", "title": "Kiểm kê quỹ tiền mặt TK 111", "required": True},
        {"code": "AR_AP_RECON", "title": "Đối chiếu công nợ phải thu/phải trả TK 131/331", "required": True},
        {"code": "VAT_RECON", "title": "Đối chiếu hóa đơn đầu vào/đầu ra với TK 133/3331", "required": True},
        {"code": "PAYROLL", "title": "Kiểm tra bảng lương, BHXH, TNCN", "required": True},
        {"code": "DEPRECIATION", "title": "Tính khấu hao TSCĐ và phân bổ CCDC/242", "required": True},
        {"code": "INVENTORY", "title": "Kiểm kê kho và tính giá vốn", "required": True},
        {"code": "REVIEW_QUEUE", "title": "Xử lý hết các item AI đang pending", "required": True, "pending_count": dashboard["review_queue"]["by_status"].get("pending", 0)},
        {"code": "TAX_RISK", "title": "Duyệt các giao dịch có rủi ro thuế medium/high", "required": True},
        {"code": "LOCK_PERIOD", "title": "Khóa kỳ sau khi kế toán trưởng duyệt", "required": True},
    ]
    return {"workspace_id": workspace_id, "items": items}


# ---------------------------------------------------------------------------
# V99 - Production/security readiness
# ---------------------------------------------------------------------------


def production_readiness_check() -> Dict[str, Any]:
    checks = []
    env_path = ROOT_DIR / ".env"
    env_example_path = ROOT_DIR / ".env.example"
    requirements_path = ROOT_DIR / "requirements.txt"
    gitignore_path = ROOT_DIR / ".gitignore"

    checks.append({"code": "ENV_EXISTS", "ok": env_example_path.exists(), "message": ".env.example tồn tại" if env_example_path.exists() else "Thiếu .env.example"})
    if env_path.exists():
        env_text = env_path.read_text(encoding="utf-8", errors="ignore")
        risky = []
        for line in env_text.splitlines():
            if "=" not in line or line.strip().startswith("#"):
                continue
            key, value = line.split("=", 1)
            if value and value.lower() not in {"changeme", "example", "your_key", ""} and any(s in key.lower() for s in ["secret", "key", "token", "password"]):
                risky.append(key)
        checks.append({"code": "ENV_SECRET_REVIEW", "ok": len(risky) == 0, "message": "Không phát hiện secret rõ ràng trong .env" if not risky else f"Cần kiểm tra secret trong .env: {', '.join(risky)}"})
    else:
        checks.append({"code": "ENV_SECRET_REVIEW", "ok": True, "message": "Không có .env trong repo hoặc chưa tạo"})

    if gitignore_path.exists():
        gi = gitignore_path.read_text(encoding="utf-8", errors="ignore")
        checks.append({"code": "GITIGNORE_ENV", "ok": ".env" in gi, "message": ".gitignore có .env" if ".env" in gi else "Nên thêm .env vào .gitignore"})
    else:
        checks.append({"code": "GITIGNORE_ENV", "ok": False, "message": "Thiếu .gitignore"})

    req_text = requirements_path.read_text(encoding="utf-8", errors="ignore") if requirements_path.exists() else ""
    for pkg in ["fastapi", "uvicorn", "sqlalchemy", "pydantic", "python-multipart", "openpyxl", "pypdf", "pytest"]:
        checks.append({"code": f"REQ_{pkg.upper().replace('-', '_')}", "ok": pkg in req_text.lower(), "message": f"requirements có {pkg}" if pkg in req_text.lower() else f"Thiếu {pkg}"})

    store = load_store()
    pending_reviews = sum(1 for r in store.get("review_items", {}).values() if r.get("status") == "pending")
    checks.append({"code": "NO_AUTO_POST", "ok": True, "message": "AI chỉ tạo draft/review; không tự ghi sổ thật nếu chưa duyệt"})
    checks.append({"code": "PENDING_REVIEWS", "ok": pending_reviews < 100, "message": f"Review pending: {pending_reviews}"})
    passed = sum(1 for c in checks if c["ok"])
    return {"version": ENTERPRISE_VERSION, "score": round(passed / len(checks), 4), "passed": passed, "total": len(checks), "checks": checks}


# ---------------------------------------------------------------------------
# Capability matrix and convenience façade
# ---------------------------------------------------------------------------


def enterprise_capabilities() -> Dict[str, Any]:
    return {
        "version": ENTERPRISE_VERSION,
        "modules": {
            "V86_RAG": ["upload", "chunk_by_article", "search", "source_cited_answer"],
            "V87_OCR_INVOICE": ["extract_text", "parse_invoice_fields", "quality_check"],
            "V88_JOURNAL_EXPORT": ["draft_journal", "balance_check", "csv_export", "xlsx_export"],
            "V89_REVIEW_QUEUE": ["pending_approval", "approve_reject_correct", "feedback_learning_log"],
            "V90_TAX_RISK": ["invoice_check", "cash_threshold", "deductibility", "asset_classification", "payroll_docs"],
            "V91_SMART_QUESTIONS": ["missing_amount", "vat_rate", "payment_method", "asset_policy", "payroll_docs"],
            "V92_AGENT_PIPELINE": ["ingest", "parse", "draft", "risk", "review"],
            "V93_WORKSPACE": ["company_profile", "policy", "chart_of_accounts", "multi_company"],
            "V94_DASHBOARD": ["evaluation", "quality_metrics", "feedback_counts"],
            "V95_DATABASE": ["postgres_blueprint", "supabase_ready_schema"],
            "V96_FRONTEND_CONTRACT": ["screen_api_map", "stable_response_shapes"],
            "V97_REPORTS": ["monthly_summary", "vat_estimate", "ar_ap", "closing_checklist"],
            "V98_COMPANY_MEMORY": ["workspace_memory", "policy_notes"],
            "V99_PRODUCTION": ["security_checklist", "env_review", "requirements_check"],
        },
        "storage": {"mode": "local_json_now", "store_path": str(STORE_PATH.relative_to(ROOT_DIR)), "upgrade_path": "swap to V95 PostgreSQL/Supabase schema"},
    }


__all__ = [
    "ENTERPRISE_VERSION",
    "reset_enterprise_store",
    "enterprise_capabilities",
    "create_or_update_workspace",
    "get_workspace",
    "list_workspaces",
    "remember_company_fact",
    "list_company_memory",
    "extract_text_from_bytes",
    "add_document",
    "add_uploaded_document",
    "search_documents",
    "answer_with_enterprise_rag",
    "parse_invoice_text",
    "create_journal_entry",
    "list_journal_entries",
    "export_journal_csv",
    "export_journal_xlsx",
    "create_review_item",
    "list_review_queue",
    "update_review_item",
    "tax_risk_check",
    "smart_followup_questions",
    "run_accounting_agent_pipeline",
    "run_evaluation",
    "quality_dashboard",
    "database_schema_blueprint",
    "frontend_api_contract",
    "monthly_summary_report",
    "closing_checklist",
    "production_readiness_check",
]
