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
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import ChatAttachment, ChatConversation, ChatFeedback, ChatMessage
from services.rag_storage_v101 import answer_with_supabase_rag
from services.rag_v66_v67 import read_upload_bytes, safe_filename, validate_rag_file

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


def _history_text(db: Session, conversation_id: str, ctx: Dict[str, str], limit: int = 20) -> str:
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
    text = "\n".join(f"{row.role}: {row.content[:2000]}" for row in rows)
    return text[-12000:]


def _attachment_context(rows: List[ChatAttachment]) -> str:
    blocks = []
    for row in rows:
        text = (row.extracted_text or "").strip()
        if text:
            blocks.append(f"TỆP: {row.file_name}\n{text[:9000]}")
    return "\n\n".join(blocks)[:18000]


def _deterministic_attachment_answer(question: str, rows: List[ChatAttachment]) -> str:
    """Safe fallback when no external LLM key is configured.

    It never invents facts: it presents the extracted content and a small set of
    detected invoice fields when applicable.
    """
    parts = ["Mình đã đọc tệp đính kèm. Dưới đây là nội dung trích xuất để bạn kiểm tra:"]
    for row in rows[:4]:
        text = re.sub(r"\s+", " ", (row.extracted_text or "").strip())
        preview = text[:2200]
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
        system = (
            "Bạn là Finiip, trợ lý AI thuộc CTCP IIP Việt Nam, chuyên hỗ trợ kế toán, thuế, báo cáo và phân tích tài liệu. "
            "Phân tích chủ yếu dựa trên nội dung tệp người dùng đính kèm. "
            "Không bịa dữ kiện không có trong tệp. Khi thiếu căn cứ hãy nói rõ. "
            "Trả lời bằng tiếng Việt, rõ ràng, có kết luận, căn cứ trong tệp, các bước xử lý và lưu ý rủi ro."
        )
        user = (
            f"LỊCH SỬ GẦN ĐÂY:\n{history[-3000:]}\n\n"
            f"CÂU HỎI:\n{question}\n\n"
            f"NỘI DUNG TỆP ĐÍNH KÈM:\n{attachment_context}"
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.2,
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


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=240)


class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=240)
    is_archived: Optional[bool] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=30000)
    mode: str = Field(default="normal", pattern="^(normal|deep)$")
    include_sources: bool = True
    attachment_ids: List[str] = Field(default_factory=list, max_length=8)


class FeedbackRequest(BaseModel):
    rating: str = Field(..., pattern="^(up|down)$")
    reason: Optional[str] = Field(default=None, max_length=240)
    comment: Optional[str] = Field(default=None, max_length=3000)


@router.get("/status")
def chat_status():
    return {
        "ok": True,
        "service": "finiip-product-chat",
        "version": "1.9.0",
        "database": "configured" if os.getenv("DATABASE_URL") else "sqlite_default",
        "llm_configured": bool(os.getenv("OPENAI_API_KEY")),
        "endpoints": {
            "conversations": "/api/v1/chat/conversations",
            "attachments": "/api/v1/chat/attachments",
        },
    }


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
        metadata_json=_json_dump({"attachment_ids": payload.attachment_ids, "mode": payload.mode}),
    )
    db.add(user_message)
    db.flush()

    attachment_text = _attachment_context(attachments)
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
            "answer": direct_answer or _deterministic_attachment_answer(payload.message, attachments),
            "citations": attachment_citations,
            "confidence": "high_attachment_grounded",
            "quality_gate": {"passed": True, "issues": []},
            "conversation_route": "attachment_analysis",
            "answer_mode": "attachment_analysis",
        }
    else:
        effective_message = payload.message
        if attachment_text:
            effective_message += (
                "\n\nHãy ưu tiên phân tích nội dung tệp đính kèm dưới đây. "
                "Không được coi tệp này là tài liệu chính thức trong kho RAG:\n\n" + attachment_text
            )
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
        extracted_text=text[:200000],
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
