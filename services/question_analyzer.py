from __future__ import annotations

import re
import unicodedata

try:
    from services.simple_intents_v101 import detect_simple_intent
except Exception:  # pragma: no cover - keeps legacy imports safe
    detect_simple_intent = None


def strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", strip_accents(text).lower()).strip()


def detect_intent(question: str) -> str:
    q = norm(question)

    # V101: handle many short/simple accounting/admin questions before the older broad router.
    if detect_simple_intent is not None:
        try:
            simple = detect_simple_intent(question)
            if simple.get("confidence", 0) >= 0.55 and simple.get("intent") not in {"unknown", "greeting", "thanks", "goodbye", "help"}:
                mapped = {
                    "admin_rag_upload": "admin_rag_upload",
                    "admin_rag_list": "admin_rag_list",
                    "admin_rag_delete": "admin_rag_delete",
                    "admin_rag_reindex": "admin_rag_reindex",
                    "admin_rag_search": "admin_rag_search",
                    "admin_rag_ask": "legal_rag",
                    "supabase_status": "supabase_status",
                    "user_file_upload": "user_file_upload",
                    "ocr_invoice": "ocr_invoice",
                    "report_analyze": "report_analyze",
                    "accounting_entry": "accounting_entry",
                    "transaction_classification": "transaction_classification",
                    "journal_check": "journal_check",
                    "tax_risk_check": "legal_rag",
                    "followup_questions": "followup_questions",
                    "vat_question": "calculation",
                    "invoice_question": "legal_rag",
                    "expense_deductibility": "legal_rag",
                    "account_lookup": "account_lookup",
                    "payroll_question": "payroll_question",
                    "asset_question": "asset_question",
                    "ccdc_prepaid_question": "calculation",
                    "inventory_question": "calculation",
                    "bank_cash_question": "bank_cash_question",
                    "receivable_payable_question": "receivable_payable_question",
                    "closing_books": "closing",
                    "financial_report": "report_question",
                    "profit_question": "report_question",
                    "revenue_question": "report_question",
                    "cost_question": "report_question",
                    "cashflow_question": "report_question",
                    "review_queue": "review_queue",
                    "export_excel": "export_excel",
                    "import_data": "import_data",
                    "workspace_settings": "workspace_settings",
                    "company_memory": "company_memory",
                    "database_setup": "database_setup",
                    "security_production": "security_production",
                }
                return mapped.get(simple.get("intent"), simple.get("intent"))
        except Exception:
            pass

    calculation_keywords = [
        "tinh", "bao nhieu", "vat", "gtgt", "thue", "khau hao", "phan bo",
        "ccdc", "gia xuat kho", "fifo", "binh quan", "lai vay", "tong tien",
        "doanh thu", "chi phi", "loi nhuan", "tndn phai nop", "gia von",
    ]

    accounting_entry_keywords = [
        "hach toan", "dinh khoan", "but toan", "no tai khoan", "co tai khoan", "no tk", "co tk",
    ]

    legal_keywords = [
        "co bat buoc", "co duoc", "quy dinh", "thong tu", "nghi dinh", "luat",
        "can cu", "dieu kien", "phai khong", "co phai", "thoi han", "muc phat",
        "ap dung", "bao cao tai chinh", "ke toan truong", "duoc tru", "khong duoc tru",
        "hoa don", "chung tu", "quyet toan",
    ]

    has_calc = any(k in q for k in calculation_keywords) or bool(re.search(r"\d+(?:[\.,]\d+)?\s*(trieu|triệu|tr|ty|tỷ|%|dong|đ)", question.lower()))
    has_entry = any(k in q for k in accounting_entry_keywords)
    has_legal = any(k in q for k in legal_keywords)
    is_long = len(question or "") > 260 or len(re.findall(r"[\.\?\!;\n]", question or "")) >= 2

    if has_legal and (has_calc or has_entry or is_long):
        return "hybrid_legal_exam"

    if is_long and (has_calc or has_entry):
        return "long_exam_calculation"

    if is_long:
        return "long_question"

    if has_legal and (has_calc or has_entry):
        return "hybrid"

    if has_entry:
        return "accounting_entry"

    if has_calc:
        return "calculation"

    if has_legal:
        return "legal_rag"

    return "general_accounting"


def split_long_question(question: str) -> list[str]:
    raw = re.sub(r"\s+", " ", question or "").strip()
    raw_parts = re.split(r"(?:\n+)|(?:;)+|(?:\s+(?=\d+[\)\.]\s))|(?<=[\?\.\!])\s+|(?:\s+va\s+)|(?:\s+và\s+)", raw)
    parts: list[str] = []

    for part in raw_parts:
        part = re.sub(r"^\s*\d+[\)\.]\s*", "", part).strip(" .,-")
        if len(part) >= 12:
            parts.append(part)

    if not parts:
        return [question]

    merged: list[str] = []
    for part in parts:
        if merged and len(part) < 15:
            merged[-1] = merged[-1] + "; " + part
        else:
            merged.append(part)
    return merged[:12]


def analyze_question(question: str) -> dict:
    intent = detect_intent(question)

    if intent in {"long_question", "long_exam_calculation", "hybrid_legal_exam"}:
        sub_questions = split_long_question(question)
    else:
        sub_questions = [question]

    return {
        "intent": intent,
        "sub_questions": [
            {
                "question": q,
                "intent": detect_intent(q),
            }
            for q in sub_questions
        ],
    }


# ============================================================
# V85 richer accounting question router
# ============================================================

def detect_accounting_domain(question: str) -> dict:
    q = norm(question)
    domains = {
        "vat_tax": ["vat", "gtgt", "thue", "tndn", "tncn", "hoa don", "duoc tru", "khong duoc tru"],
        "journal_entry": ["hach toan", "dinh khoan", "but toan", "no tk", "co tk", "ghi so"],
        "payroll": ["luong", "bhxh", "bhyt", "bhtn", "tncn", "bang cong"],
        "assets": ["tai san co dinh", "tscd", "khau hao", "ccdc", "cong cu", "242", "phan bo"],
        "inventory": ["kho", "gia von", "fifo", "binh quan", "nhap kho", "xuat kho", "ton kho"],
        "receivable_payable": ["cong no", "phai thu", "phai tra", "khach thanh toan", "nha cung cap"],
        "cash_bank": ["tien mat", "ngan hang", "chuyen khoan", "sao ke", "phi ngan hang"],
        "closing": ["ket chuyen", "khoa so", "cuoi ky", "bao cao tai chinh", "911", "421"],
        "rag_legal": ["quy dinh", "thong tu", "nghi dinh", "luat", "can cu", "muc phat", "dieu kien"],
    }
    hits = {name: [kw for kw in kws if kw in q] for name, kws in domains.items()}
    hits = {k: v for k, v in hits.items() if v}
    primary = max(hits, key=lambda k: len(hits[k])) if hits else "general_accounting"
    detailed_intent = None
    if detect_simple_intent is not None:
        try:
            detailed_intent = detect_simple_intent(question)
        except Exception:
            detailed_intent = None
    return {"primary_domain": primary, "domains": hits, "intent": detect_intent(question), "v101_simple_intent": detailed_intent}
