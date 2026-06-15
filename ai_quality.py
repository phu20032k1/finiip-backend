"""Finiip AI Quality Layer V3.

Layer này không thay thế ai_engine.py. Nó bọc kết quả AI hiện có để biến kết quả
thành dạng dùng được khi đi làm: có giải thích, confidence gate, risk flags,
review checklist và next action.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable, Dict, List, Optional


MONEY_ACCOUNTS = {"111", "112"}
RECEIVABLE_PAYABLE_ACCOUNTS = {"131", "331", "334", "338", "3331", "3334", "3335"}
VAT_ACCOUNTS = {"1331", "3331"}
ASSET_ACCOUNTS = {"153", "156", "211", "214", "242"}
EXPENSE_ACCOUNTS = {"632", "635", "641", "642", "811"}
REVENUE_ACCOUNTS = {"511", "515", "711"}

AI_V3_DEMO_CASES: List[Dict[str, Any]] = [
    {
        "description": "Thanh toán quảng cáo Facebook 5.000.000 bằng tiền mặt",
        "amount": 5_000_000,
        "expected_category_contains": "quảng cáo",
        "expected_debit": "641",
        "expected_credit": "111",
    },
    {
        "description": "Thu tiền bán hàng 12.000.000 chuyển khoản qua Vietcombank",
        "amount": 12_000_000,
        "expected_category_contains": "doanh thu",
        "expected_debit": "112",
        "expected_credit": "511",
    },
    {
        "description": "Thanh toán tiền điện EVN 2.300.000 bằng tiền mặt có hóa đơn VAT 10%",
        "amount": 2_530_000,
        "expected_category_contains": "điện",
        "expected_debit": "642",
        "expected_credit": "111",
    },
    {
        "description": "Mua máy tính văn phòng 20.000.000 chưa VAT chuyển khoản",
        "amount": 20_000_000,
        "expected_category_contains": "tài sản",
        "expected_debit": "211",
        "expected_credit": "112",
    },
    {
        "description": "Trả lương nhân viên qua ngân hàng tháng 5",
        "amount": 30_000_000,
        "expected_category_contains": "lương",
        "expected_debit": "334",
        "expected_credit": "112",
    },
    {
        "description": "Thu công nợ khách hàng bằng chuyển khoản",
        "amount": 18_000_000,
        "expected_category_contains": "công nợ",
        "expected_debit": "112",
        "expected_credit": "131",
    },
]


VI_STOPWORDS = {
    "va", "voi", "bang", "cho", "cua", "la", "co", "khong", "thang", "ngay",
    "phi", "tien", "thanh", "toan", "chuyen", "khoan", "mat", "nhan",
}


def normalize_vi_text(value: Optional[str]) -> str:
    value = (value or "").lower().strip()
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = value.replace("đ", "d")
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def meaningful_tokens(value: Optional[str]) -> List[str]:
    tokens = normalize_vi_text(value).split()
    return [t for t in tokens if len(t) >= 3 and t not in VI_STOPWORDS]


def get_code(result: Dict[str, Any], key: str) -> Optional[str]:
    return result.get(f"{key}_account_code") or result.get(f"{key}_account")


def infer_payment_method(description: str, result: Dict[str, Any]) -> str:
    norm = normalize_vi_text(description)
    explicit = result.get("payment_method")
    if explicit and explicit != "unknown":
        return explicit
    if any(k in norm for k in ["chuyen khoan", "ngan hang", "bank", "vietcombank", "vcb", "techcombank", "bidv", "momo", "zalopay"]):
        return "bank"
    if any(k in norm for k in ["tien mat", "cash"]):
        return "cash"
    debit = get_code(result, "debit")
    credit = get_code(result, "credit")
    if "112" in {debit, credit}:
        return "bank_inferred"
    if "111" in {debit, credit}:
        return "cash_inferred"
    return "unknown"


def detect_signal_tags(description: str) -> List[str]:
    norm = normalize_vi_text(description)
    tags: List[str] = []
    groups = {
        "vat_or_invoice": ["vat", "gtgt", "hoa don", "hoa don gtgt"],
        "cash": ["tien mat", "cash"],
        "bank": ["chuyen khoan", "ngan hang", "bank", "vietcombank", "techcombank", "momo"],
        "revenue": ["doanh thu", "ban hang", "thu tien", "khach thanh toan"],
        "expense": ["chi phi", "thanh toan", "mua", "tra", "nop"],
        "payroll": ["luong", "nhan vien", "bhxh", "tncn"],
        "ecommerce": ["shopee", "tiktok shop", "lazada", "cod", "phi san"],
        "fixed_asset": ["tai san co dinh", "may tinh", "laptop", "may in", "thiet bi"],
        "debt": ["cong no", "phai thu", "phai tra", "khach no", "nha cung cap"],
    }
    for tag, keys in groups.items():
        if any(k in norm for k in keys):
            tags.append(tag)
    return tags


def build_explanation(description: str, amount: float, result: Dict[str, Any]) -> Dict[str, Any]:
    matched_keywords = result.get("matched_keywords") or []
    tokens = meaningful_tokens(description)[:12]
    debit = get_code(result, "debit")
    credit = get_code(result, "credit")
    source = result.get("source") or result.get("ai_stage") or "rule_based"
    payment_method = infer_payment_method(description, result)
    signal_tags = detect_signal_tags(description)

    reasons: List[str] = []
    if matched_keywords:
        reasons.append("Mô tả khớp keyword: " + ", ".join(str(x) for x in matched_keywords[:6]))
    elif tokens:
        reasons.append("AI dựa trên các token chính: " + ", ".join(tokens[:8]))
    if result.get("category"):
        reasons.append(f"Nghiệp vụ được xếp vào nhóm: {result.get('category')}.")
    if debit and credit:
        reasons.append(f"Bút toán đề xuất dùng Nợ {debit} và Có {credit}.")
    if payment_method != "unknown":
        reasons.append(f"Phương thức thanh toán nhận diện: {payment_method}.")
    if result.get("vat_rate"):
        reasons.append(f"Có dấu hiệu VAT thuế suất {result.get('vat_rate')}%.")
    if result.get("learning_correction_id"):
        reasons.append("Kết quả ưu tiên từ dữ liệu người dùng đã từng sửa trước đó.")
    if result.get("ml_candidate"):
        reasons.append("Có ML candidate nhưng chưa dùng vì confidence chưa đạt ngưỡng.")

    return {
        "summary": "AI đã phân tích mô tả, keyword, tài khoản kế toán và rủi ro trước khi đề xuất bút toán.",
        "source": source,
        "matched_keywords": matched_keywords,
        "signal_tags": signal_tags,
        "payment_method": payment_method,
        "reasons": reasons,
        "human_readable": " ".join(reasons) if reasons else "AI chưa có đủ tín hiệu để giải thích chắc chắn.",
    }


def detect_risk_flags(description: str, amount: float, result: Dict[str, Any]) -> List[Dict[str, Any]]:
    norm = normalize_vi_text(description)
    flags: List[Dict[str, Any]] = []
    confidence = float(result.get("confidence") or 0)
    tx_type = result.get("transaction_type") or result.get("type")
    debit = get_code(result, "debit")
    credit = get_code(result, "credit")
    payment_method = infer_payment_method(description, result)
    tags = set(detect_signal_tags(description))

    def add(code: str, level: str, message: str, suggestion: str):
        flags.append({"code": code, "level": level, "message": message, "suggestion": suggestion})

    if tx_type in {None, "unknown"} or not debit or not credit:
        add("UNKNOWN_ACCOUNTING_CASE", "high", "AI chưa xác định đủ nghiệp vụ hoặc tài khoản Nợ/Có.", "Không tự ghi sổ. Đưa vào hàng chờ kế toán duyệt và bổ sung rule/correction.")
    if confidence < 0.55:
        add("VERY_LOW_CONFIDENCE", "high", "Độ tin cậy AI rất thấp.", "Bắt buộc người dùng sửa/duyệt trước khi tạo bút toán.")
    elif confidence < 0.75:
        add("LOW_CONFIDENCE", "medium", "Độ tin cậy AI chưa đủ cao.", "Nên hiển thị câu hỏi xác nhận trước khi ghi sổ.")
    if amount >= 5_000_000 and payment_method in {"cash", "cash_inferred"}:
        add("LARGE_CASH_PAYMENT", "high", "Giao dịch từ 5 triệu đồng trở lên có dấu hiệu thanh toán tiền mặt.", "Kiểm tra hóa đơn/chứng từ và cân nhắc thanh toán không dùng tiền mặt khi cần khấu trừ/chi phí hợp lệ.")
    if "vat_or_invoice" in tags and not (result.get("vat_rate") or debit in VAT_ACCOUNTS or credit in VAT_ACCOUNTS or result.get("has_vat")):
        add("VAT_MENTIONED_BUT_NOT_MODELED", "medium", "Mô tả có nhắc hóa đơn/VAT nhưng bút toán chưa tách VAT rõ ràng.", "Kiểm tra thuế suất và cân nhắc tách dòng Nợ 1331 hoặc Có 3331.")
    if "bank" in tags and "cash" in tags:
        add("PAYMENT_METHOD_CONFLICT", "medium", "Mô tả có cả dấu hiệu tiền mặt và chuyển khoản.", "Hỏi lại người nhập để xác định Có 111 hay Có/Nợ 112.")
    if {"revenue", "expense"}.issubset(tags) and tx_type not in {"transfer", "other"}:
        add("MIXED_REVENUE_EXPENSE_SIGNAL", "low", "Mô tả có cả dấu hiệu thu và chi.", "Kiểm tra xem đây là doanh thu, chi phí hay đối trừ công nợ.")
    if any(k in norm for k in ["khong hoa don", "khong co hoa don", "mat hoa don", "phat", "vi pham"]):
        add("DOCUMENT_OR_PENALTY_RISK", "high", "Mô tả có dấu hiệu thiếu hóa đơn, phạt hoặc vi phạm.", "Không tự động hạch toán chi phí được trừ nếu chưa có chứng từ hợp lệ.")
    if debit == credit and debit is not None:
        add("SAME_DEBIT_CREDIT", "high", "Tài khoản Nợ và Có đang trùng nhau.", "Chặn ghi sổ và yêu cầu sửa bút toán.")
    if tx_type == "income" and debit not in MONEY_ACCOUNTS | {"131"}:
        add("UNUSUAL_INCOME_DEBIT", "medium", "Doanh thu/thu tiền nhưng tài khoản Nợ không phải tiền hoặc phải thu.", "Kiểm tra lại Nợ 111/112/131.")
    if tx_type == "expense" and credit not in MONEY_ACCOUNTS | RECEIVABLE_PAYABLE_ACCOUNTS | ASSET_ACCOUNTS:
        add("UNUSUAL_EXPENSE_CREDIT", "medium", "Chi phí/mua hàng nhưng tài khoản Có không phổ biến.", "Kiểm tra lại Có 111/112/331/334/338/214/156.")
    return flags


def confidence_calibration(result: Dict[str, Any], flags: List[Dict[str, Any]]) -> Dict[str, Any]:
    original = float(result.get("confidence") or 0)
    penalty = 0.0
    for flag in flags:
        if flag["level"] == "high":
            penalty += 0.18
        elif flag["level"] == "medium":
            penalty += 0.08
        else:
            penalty += 0.03
    if result.get("source") == "learning_memory":
        bonus = 0.04
    elif result.get("source") == "rule_based":
        bonus = 0.0
    else:
        bonus = 0.02
    adjusted = max(0.0, min(0.99, original + bonus - penalty))
    if adjusted >= 0.90:
        band = "very_high"
    elif adjusted >= 0.75:
        band = "high"
    elif adjusted >= 0.55:
        band = "medium"
    else:
        band = "low"
    return {
        "original_confidence": round(original, 3),
        "adjusted_confidence": round(adjusted, 3),
        "band": band,
        "penalty_from_risks": round(penalty, 3),
        "note": "adjusted_confidence dùng để quyết định workflow duyệt, không thay thế kiểm tra kế toán.",
    }


def quality_gate(result: Dict[str, Any], flags: List[Dict[str, Any]], calibration: Dict[str, Any]) -> Dict[str, Any]:
    high = [f for f in flags if f["level"] == "high"]
    medium = [f for f in flags if f["level"] == "medium"]
    adjusted = float(calibration.get("adjusted_confidence") or 0)
    if high or adjusted < 0.55:
        decision = "BLOCK_AUTO_POSTING"
        label = "Chặn tự ghi sổ"
    elif medium or adjusted < 0.82:
        decision = "REVIEW_REQUIRED"
        label = "Cần kế toán duyệt"
    else:
        decision = "AUTO_DRAFT_ALLOWED"
        label = "Có thể tạo draft, vẫn nên duyệt trước khi posted"
    checklist = [
        "Kiểm tra mô tả và số tiền với chứng từ gốc.",
        "Kiểm tra tài khoản Nợ/Có.",
        "Kiểm tra VAT nếu hóa đơn có thuế.",
        "Chỉ confirmed/posted sau khi người dùng duyệt.",
    ]
    if high:
        checklist.insert(0, "Không tự động ghi sổ vì có rủi ro cao.")
    return {
        "decision": decision,
        "label": label,
        "needs_review": decision != "AUTO_DRAFT_ALLOWED",
        "can_create_draft": decision != "BLOCK_AUTO_POSTING",
        "can_auto_post": False,
        "high_risk_count": len(high),
        "medium_risk_count": len(medium),
        "checklist": checklist,
    }


def review_questions(description: str, amount: float, result: Dict[str, Any], flags: List[Dict[str, Any]]) -> List[str]:
    questions = []
    codes = {f["code"] for f in flags}
    if "UNKNOWN_ACCOUNTING_CASE" in codes:
        questions.append("Nghiệp vụ này thuộc nhóm nào và dùng tài khoản Nợ/Có nào?")
    if "VAT_MENTIONED_BUT_NOT_MODELED" in codes:
        questions.append("Hóa đơn có VAT không, thuế suất bao nhiêu, có cần tách Nợ 1331/Có 3331 không?")
    if "LARGE_CASH_PAYMENT" in codes:
        questions.append("Khoản từ 5 triệu đồng trở lên này có chứng từ và phương thức thanh toán không dùng tiền mặt phù hợp không?")
    if "PAYMENT_METHOD_CONFLICT" in codes:
        questions.append("Thanh toán thực tế là tiền mặt hay chuyển khoản?")
    if not questions:
        questions.append("Kế toán xác nhận bút toán Nợ/Có này đã đúng chưa?")
    return questions


def enhance_ai_result(description: str, amount: float, result: Dict[str, Any]) -> Dict[str, Any]:
    enhanced = dict(result or {})
    # Chuẩn hóa key để frontend/API dùng nhất quán.
    if enhanced.get("debit_account") and not enhanced.get("debit_account_code"):
        enhanced["debit_account_code"] = enhanced.get("debit_account")
    if enhanced.get("credit_account") and not enhanced.get("credit_account_code"):
        enhanced["credit_account_code"] = enhanced.get("credit_account")
    enhanced["amount"] = amount
    flags = detect_risk_flags(description, amount, enhanced)
    calibration = confidence_calibration(enhanced, flags)
    gate = quality_gate(enhanced, flags, calibration)
    explanation = build_explanation(description, amount, enhanced)
    enhanced["explainable_ai"] = explanation
    enhanced["risk_flags"] = flags
    enhanced["confidence_calibration"] = calibration
    enhanced["quality_gate"] = gate
    enhanced["review_questions"] = review_questions(description, amount, enhanced, flags)
    enhanced["next_best_action"] = gate["label"]
    enhanced["ai_version"] = "V3 AI Quality Layer - explainable + confidence calibration + risk gate"
    enhanced["needs_review"] = gate["needs_review"]
    # Giữ field confidence cũ, thêm field calibrated rõ hơn.
    enhanced["calibrated_confidence"] = calibration["adjusted_confidence"]
    return enhanced


def evaluate_case(case: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    category = normalize_vi_text(result.get("category"))
    expected_category = normalize_vi_text(case.get("expected_category_contains"))
    debit = get_code(result, "debit")
    credit = get_code(result, "credit")
    checks = {
        "category_contains": bool(expected_category and expected_category in category),
        "debit_account": debit == case.get("expected_debit"),
        "credit_account": credit == case.get("expected_credit"),
        "has_explanation": bool(result.get("explainable_ai", {}).get("reasons")),
        "has_quality_gate": bool(result.get("quality_gate", {}).get("decision")),
    }
    return {"checks": checks, "passed": all(checks.values())}


def run_ai_v3_test_suite(analyzer: Callable[[str, float], Dict[str, Any]], cases: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    cases = cases or AI_V3_DEMO_CASES
    results = []
    passed = 0
    for case in cases:
        ai_result = analyzer(case["description"], float(case["amount"]))
        evaluation = evaluate_case(case, ai_result)
        if evaluation["passed"]:
            passed += 1
        results.append({"input": case, "ai_result": ai_result, **evaluation})
    total = len(cases)
    return {
        "ai_version": "V3 AI Quality Layer",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy_percent": round(passed / total * 100, 2) if total else 0,
        "note": "Đây là smoke test demo. Khi dùng đi làm cần bổ sung test case từ dữ liệu thật đã ẩn thông tin.",
        "results": results,
    }
