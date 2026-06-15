"""Production-facing chat API for the Finiip frontend.

This module wraps the existing V106 conversational RAG engine behind a stable
/api/v1/chat contract and adds product concerns: conversations, message IDs,
attachments, normalized citations and feedback.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import ChatAttachment, ChatConversation, ChatFeedback, ChatMessage
from services.rag_storage_v101 import answer_with_supabase_rag
from services.smart_orchestrator_v110 import (
    analyze_request,
    build_attachment_context,
    combine_subanswers,
    merge_citations,
    synthesize_subanswers_with_llm,
)
from services.rag_v66_v67 import read_upload_bytes, safe_filename, validate_rag_file
from services.file_report_v68_v72 import (
    FileReportInput,
    create_and_run_sync,
    get_job_status as get_file_report_job_status,
    resolve_job_output as resolve_file_report_output,
)
from services.advanced_calculation_v110 import capabilities as calculation_capabilities, solve_advanced_text_question

router = APIRouter(prefix="/api/v1/chat", tags=["Product Chat API"])
CHAT_UPLOAD_DIR = Path(__file__).resolve().parent / "data" / "chat_uploads"
CHAT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> datetime:
    return datetime.utcnow()


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.replace(microsecond=0).isoformat() + "Z" if value else None


def _clean_identity(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.@-]", "-", (value or fallback).strip())[:120]
    return cleaned or fallback


def _context(
    x_user_id: Optional[str] = Header(default="anonymous", alias="X-User-ID"),
    x_workspace_id: Optional[str] = Header(default="default", alias="X-Workspace-ID"),
) -> Dict[str, str]:
    return {
        "user_id": _clean_identity(x_user_id or "anonymous", "anonymous"),
        "workspace_id": _clean_identity(x_workspace_id or "default", "default"),
    }


def _json_load(raw: Optional[str], default: Any) -> Any:
    try:
        return json.loads(raw) if raw else default
    except Exception:
        return default


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _conversation_or_404(db: Session, conversation_id: str, ctx: Dict[str, str]) -> ChatConversation:
    row = (
        db.query(ChatConversation)
        .filter(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == ctx["user_id"],
            ChatConversation.workspace_id == ctx["workspace_id"],
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện")
    return row


def _message_or_404(db: Session, message_id: str, ctx: Dict[str, str]) -> ChatMessage:
    row = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.id == message_id,
            ChatMessage.user_id == ctx["user_id"],
            ChatMessage.workspace_id == ctx["workspace_id"],
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy tin nhắn")
    return row


def _serialize_conversation(row: ChatConversation) -> Dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "preview": row.preview or "",
        "is_archived": bool(row.is_archived),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "last_message_at": _iso(row.last_message_at),
    }


def _serialize_message(row: ChatMessage) -> Dict[str, Any]:
    return {
        "id": row.id,
        "conversation_id": row.conversation_id,
        "role": row.role,
        "content": row.content,
        "status": row.status,
        "metadata": _json_load(row.metadata_json, {}),
        "citations": _json_load(row.citations_json, []),
        "confidence": row.confidence,
        "created_at": _iso(row.created_at),
    }


def _normalize_citations(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    seen = set()
    for index, item in enumerate(items or [], 1):
        title = (
            item.get("document_title")
            or item.get("title")
            or item.get("filename")
            or item.get("file_name")
            or "Tài liệu tham chiếu"
        )
        page = item.get("page") or item.get("page_start")
        section = item.get("section") or item.get("heading") or item.get("legal_location") or item.get("location") or ""
        excerpt = item.get("excerpt") or item.get("content") or ""
        key = (str(title), str(page), str(section), str(excerpt)[:120])
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "id": str(item.get("chunk_id") or item.get("document_id") or f"source_{index}"),
                "index": index,
                "title": str(title),
                "file_name": item.get("filename") or item.get("file_name"),
                "page": page,
                "section": str(section),
                "excerpt": str(excerpt)[:1200],
                "relevance": item.get("score") or item.get("relevance") or item.get("final_score"),
                "document_id": item.get("document_id"),
                "chunk_id": item.get("chunk_id"),
            }
        )
    return normalized[:12]


def _source_cards_from_citations(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    for item in (items or [])[:8]:
        title = str(item.get("title") or "Tài liệu tham chiếu")
        lowered = title.lower()
        badge = "Nguồn nội bộ"
        if any(token in lowered for token in ["thông tư", "nghị định", "luật"]):
            badge = "Văn bản pháp lý"
        elif item.get("chunk_id"):
            badge = "Tài liệu RAG"
        cards.append({
            "index": item.get("index") or len(cards) + 1,
            "title": title,
            "badge": badge,
            "page": item.get("page"),
            "location": item.get("section") or (f"Trang {item.get('page')}" if item.get("page") else "Kho kiến thức Finiip"),
            "excerpt": str(item.get("excerpt") or "")[:320],
            "document_id": item.get("document_id"),
            "chunk_id": item.get("chunk_id"),
        })
    return cards


def _history_text(db: Session, conversation_id: str, ctx: Dict[str, str], limit: int = 40) -> str:
    rows = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.conversation_id == conversation_id,
            ChatMessage.user_id == ctx["user_id"],
            ChatMessage.workspace_id == ctx["workspace_id"],
            ChatMessage.status == "completed",
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    per_message = int(os.getenv("FINIIP_CHAT_MESSAGE_CONTEXT_CHARS", "5000"))
    max_chars = int(os.getenv("FINIIP_CHAT_CONTEXT_CHARS", "20000"))
    text = "\n".join(f"{row.role}: {row.content[:per_message]}" for row in rows)
    return text[-max_chars:]


def _attachment_context(rows: List[ChatAttachment], question: str = "") -> str:
    files = [{"filename": row.file_name, "extracted_text": row.extracted_text or ""} for row in rows]
    selected = build_attachment_context(question, files)
    return str(selected.get("context") or "")


def _deterministic_attachment_answer(question: str, rows: List[ChatAttachment], selected_context: str = "") -> str:
    """Safe fallback when no external LLM key is configured.

    It never invents facts: it presents the extracted content and a small set of
    detected invoice fields when applicable.
    """
    analysis = analyze_request(question)
    parts = [
        "Mình đã đọc tệp đính kèm và chọn các đoạn liên quan nhất với yêu cầu của bạn.",
        f"Yêu cầu được nhận diện gồm {analysis.get('task_count', 1)} phần; độ dài {analysis.get('char_count', 0)} ký tự.",
    ]
    if selected_context:
        preview = selected_context[:14000]
        parts.append(f"\n## Nội dung liên quan đã trích chọn\n{preview}{'…' if len(selected_context) > len(preview) else ''}")
    else:
        for row in rows[:4]:
            text = re.sub(r"\s+", " ", (row.extracted_text or "").strip())
            preview = text[:3000]
            parts.append(f"\n## {row.file_name}\n{preview}{'…' if len(text) > len(preview) else ''}")

    q = question.lower()
    if any(term in q for term in ["hóa đơn", "hoá đơn", "invoice", "vat", "gtgt"]):
        try:
            from invoice_ocr import parse_invoice_text
            merged = "\n".join((row.extracted_text or "") for row in rows)
            parsed = parse_invoice_text(merged)
            parts.append("\n## Dữ liệu nhận diện sơ bộ")
            fields = [
                ("Số hóa đơn", parsed.get("invoice_number")),
                ("Ngày hóa đơn", parsed.get("invoice_date")),
                ("Người bán", parsed.get("supplier_name")),
                ("Tiền trước thuế", parsed.get("subtotal")),
                ("Thuế suất VAT", parsed.get("vat_rate")),
                ("Tiền VAT", parsed.get("vat_amount")),
                ("Tổng thanh toán", parsed.get("total_amount")),
            ]
            found = [f"- **{label}:** {value}" for label, value in fields if value not in (None, "", [])]
            parts.extend(found or ["- Chưa nhận diện chắc chắn được các trường hóa đơn."])
        except Exception:
            pass

    parts.append("\nTôi còn có thể giúp bạn tóm tắt tệp thành checklist, kiểm tra rủi ro hoặc lập báo cáo từ nội dung này.")
    return "\n".join(parts)


def _direct_attachment_answer(question: str, attachment_context: str, history: str) -> Optional[str]:
    """Use the configured LLM for one-off attachment analysis when available."""
    if not os.getenv("OPENAI_API_KEY") or not attachment_context:
        return None
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        max_output_tokens = int(os.getenv("FINIIP_LLM_MAX_OUTPUT_TOKENS", "4000"))
        request_plan = analyze_request(question)
        system = (
            "Bạn là Finiip, trợ lý AI thuộc CTCP IIP Việt Nam, chuyên hỗ trợ kế toán, thuế, báo cáo và phân tích tài liệu. "
            "Phân tích chủ yếu dựa trên nội dung tệp người dùng đính kèm. "
            "Không bịa dữ kiện không có trong tệp. Khi thiếu căn cứ hãy nói rõ. "
            "Trả lời bằng tiếng Việt, rõ ràng, có kết luận, căn cứ trong tệp, các bước xử lý và lưu ý rủi ro. "
            "Với yêu cầu dài, phải xử lý đủ từng phần, nêu số liệu/công thức và giả định; không được bỏ sót."
        )
        user = (
            f"LỊCH SỬ GẦN ĐÂY:\n{history[-3000:]}\n\n"
            f"CÂU HỎI:\n{question}\n\n"
            f"NỘI DUNG TỆP ĐÍNH KÈM:\n{attachment_context}"
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.15,
            max_tokens=max_output_tokens,
        )
        return (response.choices[0].message.content or "").strip() or None
    except Exception:
        return None


def _suggested_questions(route: str, has_attachments: bool) -> List[str]:
    if has_attachments:
        return [
            "Những điểm nào trong tệp cần kiểm tra lại?",
            "Hãy lập checklist xử lý từ nội dung này.",
            "Có rủi ro thuế hoặc chứng từ nào không?",
        ]
    if route == "accounting_rag":
        return [
            "Hồ sơ và chứng từ cần lưu gồm những gì?",
            "Hãy cho ví dụ bút toán cụ thể.",
            "Những sai sót thường gặp là gì?",
        ]
    return [
        "Hãy tóm tắt thành checklist thực hiện.",
        "Căn cứ nào quan trọng nhất?",
        "Doanh nghiệp cần làm gì tiếp theo?",
    ]


def _infer_export_request(question: str) -> Optional[Dict[str, str]]:
    q = str(question or "").lower()
    if not any(term in q for term in [
        "xuất file", "xuat file", "trả file", "tra file",
        "tạo báo cáo", "tao bao cao", "làm báo cáo", "lam bao cao",
        "xuất báo cáo", "xuat bao cao", "xuất cho", "xuat cho",
        "tạo file", "tao file", "trả cho tôi file", "tra cho toi file",
        "xuất word", "xuat word", "xuất excel", "xuat excel", "xuất pdf", "xuat pdf",
    ]):
        return None
    capability_question = any(term in q for term in [
        "bạn có thể", "ban co the", "có hỗ trợ", "co ho tro",
        "làm được không", "lam duoc khong", "có làm được", "co lam duoc",
    ])
    explicit_action = any(term in q for term in [
        "hãy ", "hay ", "giúp tôi", "giup toi", "giúp tớ", "giup to",
        "tạo cho", "tao cho", "xuất cho", "xuat cho", "trả cho", "tra cho",
    ])
    if capability_question and not explicit_action:
        return None
    output_format = "docx"
    if any(term in q for term in ["excel", "xlsx"]): output_format = "xlsx"
    elif "pdf" in q: output_format = "pdf"
    elif "csv" in q: output_format = "csv"
    elif "json" in q: output_format = "json"
    elif any(term in q for term in ["markdown", " md"]): output_format = "md"
    elif any(term in q for term in ["text", "txt"]): output_format = "txt"
    task_type = "auto_report"
    if any(term in q for term in ["báo cáo tài chính", "bao cao tai chinh", "phân tích tài chính", "phan tich tai chinh"]):
        task_type = "financial_report"
    elif any(term in q for term in ["kiểm tra kế toán", "kiem tra ke toan", "soát xét", "soat xet"]):
        task_type = "accounting_review"
    elif any(term in q for term in ["pháp lý", "phap ly", "hợp đồng", "hop dong"]):
        task_type = "legal_review"
    elif any(term in q for term in ["câu hỏi", "cau hoi", "trả lời theo file", "tra loi theo file"]):
        task_type = "qa"
    return {"output_format": output_format, "task_type": task_type}


def _maybe_create_attachment_report(
    question: str,
    rows: List[ChatAttachment],
    ctx: Dict[str, str],
    answer: str = "",
) -> Optional[Dict[str, Any]]:
    export = _infer_export_request(question)
    if not export:
        return None
    files: List[FileReportInput] = []
    for row in rows:
        raw: bytes
        path = Path(row.storage_path) if row.storage_path else None
        if path and path.exists():
            raw = path.read_bytes()
            filename = row.file_name
        else:
            raw = (row.extracted_text or "").encode("utf-8")
            filename = f"{Path(row.file_name).stem or 'attachment'}.txt"
        files.append(FileReportInput(filename=filename, content=raw))
    if not files:
        generated_source = (
            "# Yêu cầu của người dùng\n\n" + str(question or "").strip() +
            "\n\n# Nội dung Finiip đã phân tích\n\n" + str(answer or "").strip()
        ).encode("utf-8")
        files.append(FileReportInput(filename="noi_dung_phan_tich_finiip.md", content=generated_source))
    result = create_and_run_sync(
        files=files,
        instruction=question,
        question=question,
        task_type=export["task_type"],
        output_format=export["output_format"],
        report_style="detailed",
        workspace_id=ctx["workspace_id"],
        user_id=ctx["user_id"],
        title="Báo cáo Finiip từ tệp đính kèm",
    )
    return {
        "job_id": result.get("job_id"),
        "status": result.get("status"),
        "filename": result.get("output_filename"),
        "download_url": (f"/api/v1/chat/generated-files/{result.get('job_id')}" if result.get("status") == "done" and result.get("job_id") else result.get("download_url")),
        "output_format": export["output_format"],
        "analysis_mode": result.get("analysis_mode"),
        "error": result.get("error"),
    }


def _answer_complex_request(
    *,
    question: str,
    history: str,
    workspace_id: str,
    conversation_id: str,
    deep: bool = False,
) -> Optional[Dict[str, Any]]:
    """Plan and answer a multi-part prompt without dropping later requests."""
    analysis = analyze_request(question)
    tasks = analysis.get("tasks") or []
    if not analysis.get("is_complex") or len(tasks) < 2:
        return None

    task_results: List[Dict[str, Any]] = []
    citation_groups: List[List[Dict[str, Any]]] = []
    quality_issues: List[str] = []
    shared_context = question[:12000]
    for index, task in enumerate(tasks[:10], 1):
        subquestion = str(task).strip()
        if subquestion != question.strip():
            subquestion += (
                "\n\nBối cảnh chung của yêu cầu gốc (chỉ sử dụng phần liên quan):\n"
                + shared_context
            )
        try:
            result = answer_with_supabase_rag(
                question=subquestion,
                workspace_id=workspace_id,
                limit=12 if deep else 8,
                history=history,
                answer_mode="chief_accountant",
                conversation_id=conversation_id,
                save_memory=False,
                allow_llm=False,
            )
        except Exception as exc:
            task_results.append({"task": task, "answer": f"Chưa xử lý được phần này: {exc}"})
            quality_issues.append(f"subtask_{index}_failed")
            continue
        task_results.append({
            "task": task,
            "answer": result.get("answer") or "Chưa có kết quả.",
            "confidence": result.get("confidence"),
        })
        citation_groups.append(result.get("citations") or [])
        quality_issues.extend((result.get("quality_gate") or {}).get("issues") or [])

    if not task_results:
        return None
    citations = merge_citations(citation_groups, limit=24)
    source_context = "\n\n".join(
        f"[{item.get('index')}] {item.get('title') or item.get('document_title')}: {item.get('excerpt') or ''}"
        for item in citations[:12]
    )
    llm_answer = synthesize_subanswers_with_llm(
        question=question,
        history=history,
        task_results=task_results,
        source_context=source_context,
    )
    answer = llm_answer or combine_subanswers(question, task_results)
    return {
        "answer": answer,
        "citations": citations,
        "confidence": "high_complex_synthesis" if llm_answer else "medium_complex_offline_synthesis",
        "quality_gate": {"passed": not quality_issues, "issues": sorted(set(quality_issues))},
        "conversation_route": "complex_request",
        "answer_mode": "multi_task_orchestrator",
        "request_analysis": analysis,
        "subtask_count": len(task_results),
        "llm_used": bool(llm_answer),
        "llm_model": os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini") if llm_answer else None,
    }


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=240)


class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=240)
    is_archived: Optional[bool] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=100000)
    mode: str = Field(default="normal", pattern="^(normal|deep)$")
    include_sources: bool = True
    attachment_ids: List[str] = Field(default_factory=list, max_length=12)


class FeedbackRequest(BaseModel):
    rating: str = Field(..., pattern="^(up|down)$")
    reason: Optional[str] = Field(default=None, max_length=240)
    comment: Optional[str] = Field(default=None, max_length=3000)


class CalculationRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=100000)


class RequestAnalysisRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=100000)


@router.get("/status")
def chat_status():
    return {
        "ok": True,
        "service": "finiip-product-chat",
        "version": "1.10.0",
        "database": "configured" if os.getenv("DATABASE_URL") else "sqlite_default",
        "llm_configured": bool(os.getenv("OPENAI_API_KEY")),
        "endpoints": {
            "conversations": "/api/v1/chat/conversations",
            "attachments": "/api/v1/chat/attachments",
            "calculate": "/api/v1/chat/calculate",
            "analyze_request": "/api/v1/chat/analyze-request",
            "capabilities": "/api/v1/chat/capabilities",
            "generated_file": "/api/v1/chat/generated-files/{job_id}",
        },
        "limits": {
            "message_chars": 100000,
            "attachments_per_message": 12,
            "remembered_context_chars": int(os.getenv("FINIIP_CHAT_CONTEXT_CHARS", "20000")),
        },
    }


@router.get("/capabilities")
def chat_capabilities():
    return {
        "ok": True,
        "version": "1.10.0",
        "long_question": {
            "max_message_chars": 100000,
            "multi_task_planning": True,
            "attachment_chunk_selection": True,
            "final_answer_synthesis": True,
        },
        "calculation": calculation_capabilities(),
        "files": {
            "read": ["pdf", "docx", "xlsx", "xlsm", "csv", "json", "txt", "md", "html", "png", "jpg", "jpeg", "webp", "tif", "tiff"],
            "export": ["docx", "xlsx", "pdf", "csv", "json", "txt", "md"],
            "ocr_fallback": True,
            "natural_language_export": True,
        },
        "knowledge": {
            "rag": True,
            "workspace_scoped": True,
            "general_llm_fallback": bool(os.getenv("OPENAI_API_KEY")),
            "source_cards": True,
        },
    }


@router.post("/calculate")
def calculate(payload: CalculationRequest):
    result = solve_advanced_text_question(payload.question)
    if result:
        return {"ok": True, **result}
    return {
        "ok": True,
        "recognized": False,
        "answer": "Chưa nhận diện được công thức an toàn từ câu hỏi. Hãy nêu rõ dữ liệu, đơn vị và đại lượng cần tính.",
        "capabilities": calculation_capabilities(),
    }


@router.post("/analyze-request")
def analyze_chat_request(payload: RequestAnalysisRequest):
    return {"ok": True, "analysis": analyze_request(payload.message)}


@router.get("/generated-files/{job_id}")
def download_generated_file(
    job_id: str,
    ctx: Dict[str, str] = Depends(_context),
):
    try:
        job = get_file_report_job_status(job_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Không tìm thấy file đã tạo") from exc
    if job.get("workspace_id") != ctx["workspace_id"] or job.get("user_id") != ctx["user_id"]:
        raise HTTPException(status_code=403, detail="Bạn không có quyền tải file này")
    try:
        resolved = resolve_file_report_output(job_id)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=f"File chưa sẵn sàng: {exc}") from exc
    return FileResponse(
        path=str(resolved["path"]),
        filename=str(resolved["filename"]),
        media_type="application/octet-stream",
    )


@router.post("/conversations", status_code=201)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    ctx: Dict[str, str] = Depends(_context),
):
    row = ChatConversation(
        id=str(uuid.uuid4()),
        user_id=ctx["user_id"],
        workspace_id=ctx["workspace_id"],
        title=(payload.title or "Cuộc trò chuyện mới").strip() or "Cuộc trò chuyện mới",
        last_message_at=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"conversation": _serialize_conversation(row)}


@router.get("/conversations")
def list_conversations(
    limit: int = Query(default=40, ge=1, le=100),
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    ctx: Dict[str, str] = Depends(_context),
):
    query = db.query(ChatConversation).filter(
        ChatConversation.user_id == ctx["user_id"],
        ChatConversation.workspace_id == ctx["workspace_id"],
    )
    if not include_archived:
        query = query.filter(ChatConversation.is_archived.is_(False))
    rows = query.order_by(ChatConversation.last_message_at.desc()).limit(limit).all()
    return {"items": [_serialize_conversation(row) for row in rows], "count": len(rows)}


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    ctx: Dict[str, str] = Depends(_context),
):
    row = _conversation_or_404(db, conversation_id, ctx)
    return {"conversation": _serialize_conversation(row)}


@router.patch("/conversations/{conversation_id}")
def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    db: Session = Depends(get_db),
    ctx: Dict[str, str] = Depends(_context),
):
    row = _conversation_or_404(db, conversation_id, ctx)
    if payload.title is not None:
        row.title = payload.title.strip() or "Cuộc trò chuyện mới"
    if payload.is_archived is not None:
        row.is_archived = payload.is_archived
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return {"conversation": _serialize_conversation(row)}


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    ctx: Dict[str, str] = Depends(_context),
):
    row = _conversation_or_404(db, conversation_id, ctx)
    db.query(ChatFeedback).filter(ChatFeedback.conversation_id == conversation_id, ChatFeedback.user_id == ctx["user_id"]).delete(synchronize_session=False)
    db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation_id, ChatMessage.user_id == ctx["user_id"]).delete(synchronize_session=False)
    attachment_rows = db.query(ChatAttachment).filter(ChatAttachment.conversation_id == conversation_id, ChatAttachment.user_id == ctx["user_id"]).all()
    for attachment in attachment_rows:
        if attachment.storage_path:
            try:
                Path(attachment.storage_path).unlink(missing_ok=True)
            except Exception:
                pass
        db.delete(attachment)
    db.delete(row)
    db.commit()
    return {"ok": True, "conversation_id": conversation_id}


@router.get("/conversations/{conversation_id}/messages")
def list_messages(
    conversation_id: str,
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
    ctx: Dict[str, str] = Depends(_context),
):
    _conversation_or_404(db, conversation_id, ctx)
    rows = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.conversation_id == conversation_id,
            ChatMessage.user_id == ctx["user_id"],
            ChatMessage.workspace_id == ctx["workspace_id"],
        )
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
        .all()
    )
    return {"items": [_serialize_message(row) for row in rows], "count": len(rows)}


@router.post("/conversations/{conversation_id}/messages", status_code=201)
def send_message(
    conversation_id: str,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    ctx: Dict[str, str] = Depends(_context),
):
    conversation = _conversation_or_404(db, conversation_id, ctx)
    history = _history_text(db, conversation_id, ctx)
    request_analysis = analyze_request(payload.message)

    attachments: List[ChatAttachment] = []
    if payload.attachment_ids:
        attachments = (
            db.query(ChatAttachment)
            .filter(
                ChatAttachment.id.in_(payload.attachment_ids),
                ChatAttachment.user_id == ctx["user_id"],
                ChatAttachment.workspace_id == ctx["workspace_id"],
                ChatAttachment.conversation_id == conversation_id,
            )
            .all()
        )
        if len(attachments) != len(set(payload.attachment_ids)):
            raise HTTPException(status_code=400, detail="Có tệp đính kèm không hợp lệ hoặc không thuộc cuộc trò chuyện này")

    user_message = ChatMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        user_id=ctx["user_id"],
        workspace_id=ctx["workspace_id"],
        role="user",
        content=payload.message.strip(),
        status="completed",
        metadata_json=_json_dump({"attachment_ids": payload.attachment_ids, "mode": payload.mode, "request_analysis": request_analysis}),
    )
    db.add(user_message)
    db.flush()

    attachment_text = _attachment_context(attachments, payload.message)
    direct_answer = _direct_attachment_answer(payload.message, attachment_text, history)
    core_result: Dict[str, Any]
    if direct_answer or attachments:
        attachment_citations = [
            {
                "id": row.id,
                "index": index,
                "title": row.file_name,
                "file_name": row.file_name,
                "page": None,
                "section": "Tệp đính kèm trong cuộc trò chuyện",
                "excerpt": (row.extracted_text or "")[:700],
                "relevance": 1.0,
                "document_id": row.id,
                "chunk_id": None,
            }
            for index, row in enumerate(attachments, 1)
        ]
        core_result = {
            "answer": direct_answer or _deterministic_attachment_answer(payload.message, attachments, attachment_text),
            "citations": attachment_citations,
            "confidence": "high_attachment_grounded",
            "quality_gate": {"passed": True, "issues": []},
            "conversation_route": "attachment_analysis",
            "answer_mode": "attachment_analysis",
            "request_analysis": request_analysis,
            "llm_used": bool(direct_answer),
            "llm_model": os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini") if direct_answer else None,
        }
    else:
        complex_result = _answer_complex_request(
            question=payload.message,
            history=history,
            workspace_id=ctx["workspace_id"],
            conversation_id=conversation_id,
            deep=payload.mode == "deep",
        )
        if complex_result:
            core_result = complex_result
        else:
            effective_message = payload.message
            try:
                core_result = answer_with_supabase_rag(
                    question=effective_message,
                    workspace_id=ctx["workspace_id"],
                    limit=12 if payload.mode == "deep" else 6,
                    history=history,
                    answer_mode="chief_accountant" if payload.mode == "deep" else "auto",
                    conversation_id=conversation_id,
                    save_memory=False,
                )
            except Exception as exc:
                db.rollback()
                raise HTTPException(status_code=502, detail=f"AI backend chưa trả lời được: {exc}") from exc


    generated_file: Optional[Dict[str, Any]] = None
    try:
        generated_file = _maybe_create_attachment_report(
            payload.message,
            attachments,
            ctx,
            answer=str(core_result.get("answer") or ""),
        )
        if generated_file and generated_file.get("download_url"):
            core_result["answer"] = str(core_result.get("answer") or "").rstrip() + (
                f"\n\nMình đã tạo file **{generated_file.get('filename')}**. "
                "Giao diện có thể dùng nút tải xuống từ trường `generated_file.download_url`."
            )
    except Exception as exc:
        generated_file = {"status": "failed", "error": str(exc)}
        quality = core_result.setdefault("quality_gate", {"passed": True, "issues": []})
        quality.setdefault("issues", []).append("file_export_failed")

    citations = _normalize_citations(core_result.get("citations") or []) if payload.include_sources else []
    source_cards = _source_cards_from_citations(citations)
    quality_gate = core_result.get("quality_gate") or {}
    assistant_message = ChatMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        user_id=ctx["user_id"],
        workspace_id=ctx["workspace_id"],
        role="assistant",
        content=str(core_result.get("answer") or "Mình chưa tạo được câu trả lời.").strip(),
        status="completed",
        metadata_json=_json_dump(
            {
                "answer_mode": core_result.get("answer_mode"),
                "route": core_result.get("conversation_route"),
                "quality": quality_gate,
                "followup_context_used": core_result.get("followup_context_used", False),
                "resolved_question": core_result.get("resolved_question"),
                "source_presentation": "separate_cards",
                "llm_used": bool(core_result.get("llm_used")),
                "llm_model": core_result.get("llm_model"),
                "request_analysis": core_result.get("request_analysis") or request_analysis,
                "subtask_count": core_result.get("subtask_count"),
                "generated_file": generated_file,
            }
        ),
        citations_json=_json_dump(citations),
        confidence=str(core_result.get("confidence") or "unknown"),
    )
    db.add(assistant_message)

    if conversation.title == "Cuộc trò chuyện mới":
        conversation.title = payload.message.strip().replace("\n", " ")[:64]
    conversation.preview = assistant_message.content.replace("\n", " ")[:180]
    conversation.last_message_at = _now()
    conversation.updated_at = _now()
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)
    db.refresh(conversation)

    route = str(core_result.get("conversation_route") or "knowledge_rag")
    return {
        "conversation": _serialize_conversation(conversation),
        "user_message": _serialize_message(user_message),
        "message": _serialize_message(assistant_message),
        "citations": citations,
        "source_cards": source_cards,
        "source_presentation": "separate_cards",
        "confidence": assistant_message.confidence,
        "llm_used": bool(core_result.get("llm_used")),
        "followup_context_used": bool(core_result.get("followup_context_used")),
        "request_analysis": core_result.get("request_analysis") or request_analysis,
        "subtask_count": core_result.get("subtask_count"),
        "generated_file": generated_file,
        "quality": {
            "status": "passed" if quality_gate.get("passed", True) else "review_recommended",
            "warnings": quality_gate.get("issues") or core_result.get("conflict_warnings") or [],
        },
        "suggested_questions": _suggested_questions(route, bool(attachments)),
    }


@router.post("/attachments", status_code=201)
async def upload_attachment(
    file: UploadFile = File(...),
    conversation_id: str = Form(...),
    db: Session = Depends(get_db),
    ctx: Dict[str, str] = Depends(_context),
):
    _conversation_or_404(db, conversation_id, ctx)
    raw = await file.read()
    filename = file.filename or "upload"
    validation = validate_rag_file(filename, len(raw))
    if not validation.get("ok"):
        raise HTTPException(status_code=400, detail=validation.get("error") or validation)
    try:
        text = read_upload_bytes(filename, raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Không đọc được tệp: {exc}") from exc
    if not (text or "").strip():
        raise HTTPException(status_code=400, detail="Không trích xuất được nội dung. Với ảnh scan, hãy cấu hình OCR/Tesseract hoặc dùng PDF có lớp text.")

    attachment_id = str(uuid.uuid4())
    stored_name = f"{attachment_id}_{safe_filename(filename)}"
    storage_path = CHAT_UPLOAD_DIR / stored_name
    try:
        storage_path.write_bytes(raw)
        path_value: Optional[str] = str(storage_path)
    except Exception:
        path_value = None

    row = ChatAttachment(
        id=attachment_id,
        conversation_id=conversation_id,
        user_id=ctx["user_id"],
        workspace_id=ctx["workspace_id"],
        file_name=filename[:255],
        mime_type=file.content_type,
        size_bytes=len(raw),
        storage_path=path_value,
        extraction_status="ready",
        extracted_text=text[: int(os.getenv("FINIIP_ATTACHMENT_STORE_CHARS", "1000000"))],
        extraction_method="rag_v66_reader",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "attachment": {
            "id": row.id,
            "conversation_id": row.conversation_id,
            "file_name": row.file_name,
            "mime_type": row.mime_type,
            "size_bytes": row.size_bytes,
            "status": row.extraction_status,
            "text_length": len(row.extracted_text or ""),
            "created_at": _iso(row.created_at),
        }
    }


@router.delete("/attachments/{attachment_id}")
def delete_attachment(
    attachment_id: str,
    db: Session = Depends(get_db),
    ctx: Dict[str, str] = Depends(_context),
):
    row = (
        db.query(ChatAttachment)
        .filter(
            ChatAttachment.id == attachment_id,
            ChatAttachment.user_id == ctx["user_id"],
            ChatAttachment.workspace_id == ctx["workspace_id"],
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp")
    if row.storage_path:
        try:
            Path(row.storage_path).unlink(missing_ok=True)
        except Exception:
            pass
    db.delete(row)
    db.commit()
    return {"ok": True, "attachment_id": attachment_id}


@router.post("/messages/{message_id}/feedback", status_code=201)
def create_feedback(
    message_id: str,
    payload: FeedbackRequest,
    db: Session = Depends(get_db),
    ctx: Dict[str, str] = Depends(_context),
):
    message = _message_or_404(db, message_id, ctx)
    if message.role != "assistant":
        raise HTTPException(status_code=400, detail="Chỉ có thể đánh giá câu trả lời của AI")
    existing = (
        db.query(ChatFeedback)
        .filter(ChatFeedback.message_id == message_id, ChatFeedback.user_id == ctx["user_id"])
        .first()
    )
    if existing:
        existing.rating = payload.rating
        existing.reason = payload.reason
        existing.comment = payload.comment
        existing.updated_at = _now()
        row = existing
    else:
        row = ChatFeedback(
            id=str(uuid.uuid4()),
            message_id=message_id,
            conversation_id=message.conversation_id,
            user_id=ctx["user_id"],
            rating=payload.rating,
            reason=payload.reason,
            comment=payload.comment,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "feedback": {"id": row.id, "message_id": message_id, "rating": row.rating}}
