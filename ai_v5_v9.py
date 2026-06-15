"""Finiip AI V5-V9 backend-only extensions.

Small, dependency-light utilities for:
- V5 feedback learning rules
- V6 invoice OCR to transaction draft
- V7 lightweight knowledge/RAG storage
- V8 anomaly scoring
- V9 API-key helper
"""
from __future__ import annotations

import json
import os
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Dict, Iterable, List, Optional

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)
FEEDBACK_FILE = DATA_DIR / "ai_v5_feedback_rules.json"
KNOWLEDGE_FILE = DATA_DIR / "ai_v7_knowledge_docs.json"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^\w\sÀ-ỹđĐ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_keywords(text: str) -> List[str]:
    stop = {"và", "của", "cho", "thanh", "toan", "thanh toán", "tien", "tiền", "bang", "bằng", "qua", "the", "vào", "ra", "chi", "thu"}
    words = [w for w in normalize_text(text).split() if len(w) >= 3 and w not in stop]
    # keep order, unique
    seen, out = set(), []
    for w in words:
        if w not in seen:
            seen.add(w); out.append(w)
    return out[:12]


def load_feedback_rules() -> Dict[str, Any]:
    return _load_json(FEEDBACK_FILE, {"version": "v5", "rules": [], "events": []})


def save_feedback_event(description: str, amount: float, ai_result: Dict[str, Any], correction: Dict[str, Any], user_note: str = "", user_id: str = "anonymous") -> Dict[str, Any]:
    store = load_feedback_rules()
    now = datetime.utcnow().isoformat() + "Z"
    event = {
        "id": str(uuid.uuid4()),
        "created_at": now,
        "description": description,
        "amount": amount,
        "ai_result": ai_result or {},
        "correction": correction or {},
        "user_note": user_note,
        "user_id": user_id,
        "keywords": extract_keywords(description),
    }
    store.setdefault("events", []).append(event)

    # create/update rule per keyword + corrected account/category
    corrected_category = correction.get("category") or correction.get("correct_category") or correction.get("transaction_type")
    debit = correction.get("debit_account") or correction.get("debit_account_code")
    credit = correction.get("credit_account") or correction.get("credit_account_code")
    for kw in event["keywords"][:8]:
        match = None
        for r in store.setdefault("rules", []):
            if r.get("keyword") == kw and r.get("category") == corrected_category and r.get("debit_account") == debit and r.get("credit_account") == credit:
                match = r; break
        if match:
            match["hits"] = int(match.get("hits", 0)) + 1
            match["updated_at"] = now
        else:
            store["rules"].append({
                "id": str(uuid.uuid4()),
                "keyword": kw,
                "category": corrected_category,
                "debit_account": debit,
                "credit_account": credit,
                "confidence_boost": 0.08,
                "hits": 1,
                "created_at": now,
                "updated_at": now,
            })
    _save_json(FEEDBACK_FILE, store)
    return event


def apply_learning(description: str, ai_result: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(ai_result or {})
    store = load_feedback_rules()
    text = normalize_text(description)
    matched = []
    for rule in store.get("rules", []):
        kw = rule.get("keyword", "")
        if kw and kw in text:
            matched.append(rule)
    if not matched:
        result.setdefault("learning", {"matched_rules": [], "applied": False})
        return result
    # strongest by hits
    matched.sort(key=lambda r: int(r.get("hits", 0)), reverse=True)
    top = matched[0]
    if top.get("category"):
        result["category"] = top.get("category")
        result["transaction_type"] = top.get("category")
    if top.get("debit_account"):
        result["debit_account"] = top.get("debit_account")
        result["debit_account_code"] = top.get("debit_account")
    if top.get("credit_account"):
        result["credit_account"] = top.get("credit_account")
        result["credit_account_code"] = top.get("credit_account")
    base_conf = float(result.get("calibrated_confidence") or result.get("confidence") or 0.65)
    boost = min(0.2, sum(float(r.get("confidence_boost", 0.05)) for r in matched[:3]))
    result["calibrated_confidence"] = round(min(0.98, base_conf + boost), 3)
    result["learning"] = {
        "applied": True,
        "matched_rules": [{"id": r.get("id"), "keyword": r.get("keyword"), "hits": r.get("hits")} for r in matched[:5]],
        "message": "AI đã áp dụng rule học từ correction trước đó.",
    }
    return result


def delete_learning_rule(rule_id: str) -> bool:
    store = load_feedback_rules()
    before = len(store.get("rules", []))
    store["rules"] = [r for r in store.get("rules", []) if r.get("id") != rule_id]
    _save_json(FEEDBACK_FILE, store)
    return len(store.get("rules", [])) < before


def learning_stats() -> Dict[str, Any]:
    store = load_feedback_rules()
    return {
        "rules": len(store.get("rules", [])),
        "feedback_events": len(store.get("events", [])),
        "top_keywords": Counter(r.get("keyword") for r in store.get("rules", [])).most_common(10),
    }


def invoice_to_transaction_draft(parsed_invoice: Dict[str, Any]) -> Dict[str, Any]:
    seller = parsed_invoice.get("seller_name") or parsed_invoice.get("vendor") or parsed_invoice.get("seller") or "nhà cung cấp"
    total = parsed_invoice.get("total_amount") or parsed_invoice.get("total") or parsed_invoice.get("amount") or 0
    vat = parsed_invoice.get("vat_amount") or parsed_invoice.get("vat") or 0
    desc = f"Hóa đơn từ {seller} tổng tiền {total}"
    if vat:
        desc += f", VAT {vat}"
    return {
        "description": desc,
        "amount": total,
        "vat_amount": vat,
        "supplier": seller,
        "invoice_number": parsed_invoice.get("invoice_number") or parsed_invoice.get("number"),
        "invoice_date": parsed_invoice.get("invoice_date") or parsed_invoice.get("date"),
        "status": "waiting_review",
        "safety_note": "OCR chỉ tạo draft. Kế toán cần kiểm tra hóa đơn trước khi ghi sổ.",
    }


def add_knowledge_doc(title: str, content: str, source: str = "manual", tags: Optional[List[str]] = None) -> Dict[str, Any]:
    store = _load_json(KNOWLEDGE_FILE, {"version": "v7", "documents": []})
    doc = {
        "id": str(uuid.uuid4()),
        "title": title,
        "content": content,
        "source": source,
        "tags": tags or [],
        "created_at": datetime.utcnow().isoformat() + "Z",
        "keywords": extract_keywords(title + " " + content),
    }
    store.setdefault("documents", []).append(doc)
    _save_json(KNOWLEDGE_FILE, store)
    return doc


def search_knowledge(question: str, limit: int = 5) -> Dict[str, Any]:
    store = _load_json(KNOWLEDGE_FILE, {"version": "v7", "documents": []})
    q_words = set(extract_keywords(question))
    scored = []
    for doc in store.get("documents", []):
        d_words = set(doc.get("keywords") or extract_keywords(doc.get("title", "") + " " + doc.get("content", "")))
        score = len(q_words & d_words)
        if score:
            scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    docs = [d for _, d in scored[:limit]]
    answer = "Chưa tìm thấy tài liệu phù hợp. Hãy upload quy trình/quy định kế toán liên quan." if not docs else "\n\n".join([f"- {d['title']}: {d['content'][:500]}" for d in docs])
    return {"answer": answer, "sources": [{"id": d["id"], "title": d["title"], "source": d.get("source")} for d in docs], "matched": len(docs)}


def anomaly_score(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    amounts = [float(i.get("amount") or 0) for i in items if float(i.get("amount") or 0) > 0]
    avg = mean(amounts) if amounts else 0
    sd = pstdev(amounts) if len(amounts) > 1 else 0
    result = []
    seen = defaultdict(list)
    for idx, item in enumerate(items, start=1):
        amount = float(item.get("amount") or 0)
        desc = item.get("description", "")
        flags, score = [], 0.0
        if sd and amount > avg + 2 * sd:
            flags.append("Số tiền cao bất thường so với file import") ; score += 0.35
        if amount >= 5_000_000 and any(k in normalize_text(desc) for k in ["tien mat", "tiền mặt", "cash", "rut tien", "rút tiền"]):
            flags.append("Tiền mặt từ 5 triệu đồng trở lên cần kiểm tra điều kiện thuế") ; score += 0.35
        if any(k in normalize_text(desc) for k in ["dịch vụ", "dich vu", "tư vấn", "tu van"]) and amount >= 10000000:
            flags.append("Dịch vụ giá trị lớn cần kiểm tra hợp đồng/hóa đơn") ; score += 0.2
        key = (normalize_text(desc), round(amount, 0))
        seen[key].append(idx)
        result.append({**item, "row_index": item.get("row_index", idx), "anomaly_score": round(min(1.0, score), 3), "anomaly_flags": flags})
    for key, rows in seen.items():
        if len(rows) > 1:
            for r in result:
                if r.get("row_index") in rows:
                    r["anomaly_flags"].append(f"Nghi trùng với dòng {rows}")
                    r["anomaly_score"] = round(min(1.0, r["anomaly_score"] + 0.25), 3)
    high = [r for r in result if r["anomaly_score"] >= 0.5]
    return {"summary": {"total": len(result), "high_risk": len(high), "average_amount": avg}, "items": result}


def api_key_required() -> bool:
    return bool(os.getenv("FINIIP_API_KEY"))


def validate_api_key(value: Optional[str]) -> bool:
    expected = os.getenv("FINIIP_API_KEY")
    return True if not expected else bool(value and value == expected)
