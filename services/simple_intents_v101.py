"""Finiip V101 - richer simple-intent router for short accounting/admin questions.

Goal: make short messages like "up rag ở đâu", "vat là gì", "mua laptop", "xóa tài liệu"
route to the right backend capability instead of falling into unknown/general.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Tuple

V101_INTENT_VERSION = "v106_conversation_intent_router"


def strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", strip_accents(text).lower()).strip()


# intent, action, admin_only, route_hint, keywords/phrases
INTENT_CATALOG: List[Dict[str, Any]] = [
    {"intent": "emotional_support", "action": "reply_with_empathy", "admin_only": False, "route_hint": "/ai/v106/chat", "keywords": ["mệt quá", "met qua", "stress", "áp lực", "ap luc", "rối quá", "roi qua", "chán quá", "chan qua", "không biết làm sao", "khong biet lam sao"]},
    {"intent": "conversation_followup", "action": "resolve_previous_context", "admin_only": False, "route_hint": "/ai/v106/chat", "keywords": ["còn cái này", "con cai nay", "thế thì sao", "the thi sao", "vậy nếu", "vay neu", "trường hợp trên", "truong hop tren", "còn 642", "con 642", "tiếp đi", "tiep di"]},
    {"intent": "conversation_chat", "action": "reply_naturally", "admin_only": False, "route_hint": "/ai/v106/chat", "keywords": ["nói chuyện", "noi chuyen", "tâm sự", "tam su", "giải thích dễ hiểu", "giai thich de hieu"]},
    {"intent": "greeting", "action": "reply_greeting", "admin_only": False, "route_hint": None, "keywords": ["xin chao", "chao", "hello", "hi", "alo", "hey"]},
    {"intent": "thanks", "action": "reply_polite", "admin_only": False, "route_hint": None, "keywords": ["cam on", "thank", "thanks", "ok cam on", "cảm ơn"]},
    {"intent": "goodbye", "action": "reply_goodbye", "admin_only": False, "route_hint": None, "keywords": ["tam biet", "bye", "hen gap", "xong roi"]},
    {"intent": "help", "action": "reply_capabilities", "admin_only": False, "route_hint": "/ai/accounting/full-capabilities", "keywords": ["giup", "huong dan", "lam duoc gi", "co chuc nang gi", "cach dung", "test sao"]},

    {"intent": "admin_rag_upload", "action": "open_admin_rag_upload", "admin_only": True, "route_hint": "/admin/rag-ui", "keywords": ["up rag", "upload rag", "nap rag", "tai lieu rag", "them tai lieu", "upload thong tu", "nap thong tu", "knowledge", "tri thuc", "quan ly rag", "index tai lieu"]},
    {"intent": "admin_rag_list", "action": "list_admin_rag_documents", "admin_only": True, "route_hint": "/admin/rag-ui/api/documents", "keywords": ["danh sach tai lieu", "tai lieu da up", "xem tai lieu rag", "co nhung tai lieu nao", "list docs", "documents"]},
    {"intent": "admin_rag_delete", "action": "delete_admin_rag_document", "admin_only": True, "route_hint": "/admin/rag-ui/delete", "keywords": ["xoa tai lieu rag", "xoa tai lieu", "xoa rag", "delete document", "bo khoi rag", "remove rag"]},
    {"intent": "admin_rag_reindex", "action": "reindex_admin_rag_document", "admin_only": True, "route_hint": "/admin/rag-ui/reindex", "keywords": ["reindex", "index lai", "lap chi muc lai", "cap nhat index", "quét lại"]},
    {"intent": "admin_rag_search", "action": "search_admin_rag_chunks", "admin_only": True, "route_hint": "/admin/rag-ui/search", "keywords": ["search chunk", "tim chunk", "tim trong rag", "tim tai lieu", "truy xuat nguon"]},
    {"intent": "admin_rag_ask", "action": "ask_admin_rag", "admin_only": True, "route_hint": "/admin/rag-ui/ask", "keywords": ["hoi rag", "hoi thu rag", "tra loi theo tai lieu", "dua vao tai lieu", "theo thong tu", "theo quy dinh"]},
    {"intent": "supabase_status", "action": "check_supabase_status", "admin_only": True, "route_hint": "/ai/v101/supabase/status", "keywords": ["supabase", "da noi supabase", "storage mode", "bucket", "schema", "postgres", "pgvector"]},

    {"intent": "user_file_upload", "action": "upload_user_file_for_processing", "admin_only": False, "route_hint": "/user/files/upload", "keywords": ["up file", "upload file", "tai file", "bao cao", "sao ke", "excel", "chung tu", "file ben ngoai", "orc", "ocr", "anh hoa don"]},
    {"intent": "ocr_invoice", "action": "parse_invoice_ocr", "admin_only": False, "route_hint": "/ai/v87/invoices/parse", "keywords": ["ocr", "doc hoa don", "quét hóa đơn", "scan hoa don", "trich xuat hoa don", "parse invoice"]},
    {"intent": "report_analyze", "action": "analyze_uploaded_report", "admin_only": False, "route_hint": "/user/reports/analyze", "keywords": ["phan tich bao cao", "doc bao cao", "bao cao tai chinh", "bang can doi", "ket qua kinh doanh", "luu chuyen tien te"]},

    {"intent": "accounting_entry", "action": "suggest_accounting_entry", "admin_only": False, "route_hint": "/ai/accounting/suggest-entry", "keywords": ["hach toan", "dinh khoan", "but toan", "no co", "no tk", "co tk", "ghi so", "mua laptop", "mua may tinh", "ban hang", "mua hang", "thanh toan nha cung cap", "khach thanh toan"]},
    {"intent": "transaction_classification", "action": "classify_transaction", "admin_only": False, "route_hint": "/ai/accounting/analyze-transaction", "keywords": ["phan loai", "giao dich nay", "khoan nay", "chi phi gi", "thu tien", "chi tien", "tam ung", "hoan ung", "chuyen khoan", "tien mat"]},
    {"intent": "journal_check", "action": "check_journal_balance", "admin_only": False, "route_hint": "/ai/accounting/check-journal", "keywords": ["kiem tra but toan", "but toan can khong", "no co can", "sai but toan", "check journal"]},
    {"intent": "tax_risk_check", "action": "check_tax_risk", "admin_only": False, "route_hint": "/ai/v90/risk-check", "keywords": ["rui ro thue", "co rui ro khong", "hop le khong", "thieu hoa don", "khong co hoa don", "tien mat 5 trieu", "tien mat 20 trieu", "duoc tru", "khong duoc tru", "chung tu can gi"]},
    {"intent": "followup_questions", "action": "ask_missing_info", "admin_only": False, "route_hint": "/ai/v91/followup-questions", "keywords": ["can hoi gi", "thieu thong tin", "can bo sung", "hoi lai", "chua du du lieu"]},

    {"intent": "vat_question", "action": "vat_answer_or_calculate", "admin_only": False, "route_hint": "/ai/accounting/solve", "keywords": ["vat", "gtgt", "thue dau vao", "thue dau ra", "khau tru vat", "vat nguoc", "gia chua thue", "tong thanh toan"]},
    {"intent": "invoice_question", "action": "invoice_policy_answer", "admin_only": False, "route_hint": "/ai/v86/rag/ask", "keywords": ["hoa don", "hoa don dien tu", "so hoa don", "ky hieu", "mau so", "xuat hoa don", "dieu chinh hoa don", "huy hoa don"]},
    {"intent": "expense_deductibility", "action": "deductible_expense_answer", "admin_only": False, "route_hint": "/ai/v86/rag/ask", "keywords": ["chi phi duoc tru", "khong duoc tru", "tie p khach", "tiep khach", "cong tac phi", "marketing", "quang cao", "phuc loi", "hoa don hop le"]},
    {"intent": "account_lookup", "action": "lookup_account", "admin_only": False, "route_hint": "/ai/accounting/ask", "keywords": ["tai khoan", "tk 111", "tk 112", "tk 131", "tk 331", "tk 133", "tk 333", "tk 156", "tk 211", "tk 242", "tk 641", "tk 642", "642 la gi", "641 la gi"]},
    {"intent": "payroll_question", "action": "payroll_accounting_answer", "admin_only": False, "route_hint": "/ai/accounting/ask", "keywords": ["luong", "bang luong", "bhxh", "bhyt", "bhtn", "tncn", "bao hiem", "cham cong", "trich luong"]},
    {"intent": "asset_question", "action": "asset_accounting_answer", "admin_only": False, "route_hint": "/ai/accounting/ask", "keywords": ["tai san co dinh", "tscd", "khau hao", "nguyen gia", "thanh ly tai san", "mua oto", "mua may moc"]},
    {"intent": "ccdc_prepaid_question", "action": "prepaid_ccdc_answer", "admin_only": False, "route_hint": "/ai/accounting/solve", "keywords": ["ccdc", "cong cu dung cu", "phan bo", "chi phi tra truoc", "242", "153", "phan bo may tinh", "phan bo chi phi"]},
    {"intent": "inventory_question", "action": "inventory_answer", "admin_only": False, "route_hint": "/ai/accounting/solve", "keywords": ["hang ton kho", "nhap kho", "xuat kho", "gia von", "fifo", "binh quan gia quyen", "ton kho", "156", "632"]},
    {"intent": "bank_cash_question", "action": "cash_bank_answer", "admin_only": False, "route_hint": "/ai/accounting/ask", "keywords": ["tien mat", "ngan hang", "sao ke", "chuyen khoan", "phi ngan hang", "uy nhiem chi", "thu chi", "111", "112"]},
    {"intent": "receivable_payable_question", "action": "ar_ap_answer", "admin_only": False, "route_hint": "/ai/accounting/ask", "keywords": ["cong no", "phai thu", "phai tra", "khach no", "nha cung cap", "131", "331", "doi chieu cong no", "qua han"]},
    {"intent": "closing_books", "action": "period_closing_checklist", "admin_only": False, "route_hint": "/ai/v97/reports/closing-checklist", "keywords": ["khoa so", "cuoi ky", "cuoi thang", "ket chuyen", "911", "421", "chot so", "lap bctc"]},

    {"intent": "financial_report", "action": "financial_report_summary", "admin_only": False, "route_hint": "/ai/v97/reports/monthly-summary", "keywords": ["bao cao", "bao cao thang", "bctc", "bang can doi", "ket qua kinh doanh", "tai san no phai tra"]},
    {"intent": "profit_question", "action": "profit_report", "admin_only": False, "route_hint": "/reports/income-statement", "keywords": ["loi nhuan", "lai lo", "ket qua kinh doanh", "lai gop", "lai rong", "bien loi nhuan"]},
    {"intent": "revenue_question", "action": "revenue_report", "admin_only": False, "route_hint": "/reports/income-statement", "keywords": ["doanh thu", "ban duoc bao nhieu", "doanh so", "511", "doanh thu thang"]},
    {"intent": "cost_question", "action": "cost_report", "admin_only": False, "route_hint": "/reports/income-statement", "keywords": ["chi phi", "tong chi", "chi phi thang", "641", "642", "635", "632"]},
    {"intent": "cashflow_question", "action": "cashflow_report", "admin_only": False, "route_hint": "/reports/cashflow", "keywords": ["dong tien", "cashflow", "luu chuyen tien", "tien ve", "tien ra", "thieu tien"]},

    {"intent": "review_queue", "action": "open_review_queue", "admin_only": False, "route_hint": "/ai/v89/review-queue", "keywords": ["review", "duyet", "hang doi", "cho duyet", "ke toan duyet", "pending", "approved", "rejected"]},
    {"intent": "export_excel", "action": "export_excel", "admin_only": False, "route_hint": "/ai/v88/journal/export", "keywords": ["xuat excel", "export", "tai excel", "xuat csv", "file excel", "nhat ky chung excel"]},
    {"intent": "import_data", "action": "import_data", "admin_only": False, "route_hint": "/import/excel", "keywords": ["import", "nhap du lieu", "upload excel", "seed data", "du lieu mau"]},

    {"intent": "workspace_settings", "action": "workspace_settings", "admin_only": True, "route_hint": "/ai/v93/workspaces", "keywords": ["workspace", "cong ty", "company", "thiet lap cong ty", "danh muc tai khoan", "chinh sach cong ty"]},
    {"intent": "company_memory", "action": "company_memory", "admin_only": True, "route_hint": "/ai/v98/company-memory", "keywords": ["memory", "nho cong ty", "ghi nho chinh sach", "chinh sach phan bo", "nguong tai san"]},
    {"intent": "database_setup", "action": "database_schema", "admin_only": True, "route_hint": "/ai/v95/database-schema", "keywords": ["database", "db", "schema", "bang du lieu", "postgres", "migration", "supabase sql"]},
    {"intent": "security_production", "action": "production_readiness", "admin_only": True, "route_hint": "/ai/v99/production-readiness", "keywords": ["production", "bao mat", "deploy", "admin key", "secret", "rate limit", "docker", "health check"]},
]


def _score_catalog_item(q: str, item: Dict[str, Any]) -> Tuple[int, List[str]]:
    matched: List[str] = []
    score = 0
    for kw in item.get("keywords", []):
        nkw = norm(kw)
        if not nkw:
            continue
        if nkw == q:
            score += 12
            matched.append(kw)
        elif nkw in q:
            score += 4 + min(5, len(nkw.split()))
            matched.append(kw)
        else:
            # Token overlap for short fragmented questions.
            kw_tokens = set(re.findall(r"[a-z0-9]+", nkw))
            q_tokens = set(re.findall(r"[a-z0-9]+", q))
            overlap = kw_tokens & q_tokens
            if kw_tokens and len(overlap) >= max(1, min(2, len(kw_tokens))):
                score += len(overlap)
                matched.append(kw)
    # Amount/account-code hints.
    if item["intent"] in {"accounting_entry", "transaction_classification", "vat_question"}:
        if re.search(r"\d+(?:[\.,]\d+)?\s*(trieu|tr|ty|dong|vnd|%)", q):
            score += 2
    if item["intent"] == "account_lookup" and re.search(r"\b\d{3}\b", q):
        score += 3
    return score, matched[:10]


def detect_simple_intent(message: str) -> Dict[str, Any]:
    q = norm(message)
    if not q:
        return _unknown(message)
    scored = []
    for item in INTENT_CATALOG:
        score, matched = _score_catalog_item(q, item)
        if score > 0:
            scored.append((score, item, matched))
    if not scored:
        return _unknown(message)
    scored.sort(key=lambda x: (x[0], len(x[2])), reverse=True)
    best_score, best, matched = scored[0]
    confidence = min(0.99, round(best_score / 14, 2))
    if best_score < 3:
        return _unknown(message)
    return {
        "version": V101_INTENT_VERSION,
        "message": message,
        "normalized": q,
        "intent": best["intent"],
        "action": best["action"],
        "confidence": confidence,
        "matched_keywords": matched,
        "requires_admin": bool(best.get("admin_only")),
        "route_hint": best.get("route_hint"),
        "reply_hint": _reply_hint(best["intent"]),
        "alternatives": [
            {"intent": item["intent"], "score": score, "matched_keywords": m[:5], "route_hint": item.get("route_hint")}
            for score, item, m in scored[1:6]
        ],
    }


def _reply_hint(intent: str) -> str:
    hints = {
        "admin_rag_upload": "Mở /admin/rag-ui để admin upload/index tài liệu RAG chính thức.",
        "supabase_status": "Kiểm tra /ai/v101/supabase/status và chạy SQL schema nếu chưa có bảng.",
        "user_file_upload": "User upload file để OCR/phân tích tạm, không đưa vào RAG chính thức.",
        "accounting_entry": "Gọi analyze/suggest-entry để gợi ý bút toán, sau đó đưa vào review queue.",
        "tax_risk_check": "Dùng risk-check/RAG để đối chiếu hóa đơn, chứng từ và điều kiện được trừ.",
        "vat_question": "Có thể trả lời kiến thức VAT hoặc tính VAT xuôi/ngược nếu có số tiền.",
        "emotional_support": "Phản hồi ngắn gọn, đồng cảm và giúp người dùng chia nhỏ việc đang vướng.",
        "conversation_followup": "Dùng conversation_id để nối câu hiện tại với câu hỏi trước, không bắt người dùng nhắc lại.",
        "conversation_chat": "Trả lời tự nhiên; không ép RAG hoặc citation khi người dùng chỉ trò chuyện.",
    }
    return hints.get(intent, "Điều hướng theo route_hint/action tương ứng.")


def _unknown(message: str) -> Dict[str, Any]:
    return {
        "version": V101_INTENT_VERSION,
        "message": message,
        "normalized": norm(message),
        "intent": "unknown",
        "action": "ask_clarifying_question",
        "confidence": 0.0,
        "matched_keywords": [],
        "requires_admin": False,
        "route_hint": None,
        "reply_hint": "Hỏi lại người dùng: họ muốn hạch toán, hỏi luật/RAG, upload file, xem báo cáo hay quản trị hệ thống?",
        "alternatives": [],
    }


def list_simple_intents() -> Dict[str, Any]:
    return {
        "version": V101_INTENT_VERSION,
        "count": len(INTENT_CATALOG),
        "items": [
            {
                "intent": item["intent"],
                "action": item["action"],
                "requires_admin": bool(item.get("admin_only")),
                "route_hint": item.get("route_hint"),
                "examples": item.get("keywords", [])[:8],
            }
            for item in INTENT_CATALOG
        ],
    }
