"""Finiip AI V17 - accounting autopilot layer.

This module does not call OpenAI, Ollama, or any external LLM. It turns the
existing self-built rule engine + Naive Bayes classifier into a safer product
workflow: auto-approve only high-confidence results, route uncertain cases to
human review, and produce teachable feedback hints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value or 0)))
    except (TypeError, ValueError):
        return 0.0


def _label(result: Optional[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    result = result or {}
    return {
        "category": result.get("category"),
        "transaction_type": result.get("transaction_type"),
        "debit_account_code": result.get("debit_account_code") or result.get("debit_account"),
        "credit_account_code": result.get("credit_account_code") or result.get("credit_account"),
    }


def labels_match(left: Optional[Dict[str, Any]], right: Optional[Dict[str, Any]]) -> bool:
    """Return True when two AI results suggest the same accounting label."""
    lval = _label(left)
    rval = _label(right)
    return bool(lval["category"] and rval["category"] and lval == rval)


def detect_disagreement(result: Dict[str, Any]) -> Dict[str, Any]:
    """Compare the chosen result with rule-based and ML candidates if present."""
    chosen = _label(result)
    rule = result.get("rule_based_result") or {}
    ml_candidate = result.get("ml_candidate") or {}

    signals: List[str] = []
    if rule and not labels_match(result, rule):
        signals.append("rule_disagrees")
    if ml_candidate and not labels_match(result, ml_candidate):
        signals.append("ml_disagrees")
    if result.get("source") == "rule_based" and ml_candidate:
        signals.append("ml_rejected_low_confidence")

    return {
        "chosen_label": chosen,
        "rule_label": _label(rule) if rule else None,
        "ml_candidate_label": _label(ml_candidate) if ml_candidate else None,
        "signals": signals,
        "has_disagreement": bool(signals),
    }


def decide_ai_action(
    result: Dict[str, Any],
    *,
    auto_approve_confidence: float = 0.86,
    review_confidence: float = 0.55,
) -> Dict[str, Any]:
    """Decide whether the result can be auto-applied or should be reviewed."""
    confidence = _confidence(result.get("confidence"))
    source = result.get("source") or "unknown"
    disagreement = detect_disagreement(result)
    warnings = list(result.get("warnings") or [])

    risk_reasons: List[str] = []
    if confidence < review_confidence:
        risk_reasons.append("confidence_low")
    if disagreement["has_disagreement"]:
        risk_reasons.extend(disagreement["signals"])
    if warnings:
        risk_reasons.append("has_warnings")
    if source == "rule_based" and confidence < auto_approve_confidence:
        risk_reasons.append("rule_based_not_enough_for_autopilot")

    if not risk_reasons and confidence >= auto_approve_confidence and source in {"ml_model", "learning_memory"}:
        action = "auto_approve"
        message = "Có thể tự áp dụng vì AI tự học có confidence cao và không có xung đột lớn."
    elif confidence >= review_confidence:
        action = "needs_review"
        message = "Nên cho kế toán kiểm tra trước khi ghi sổ."
    else:
        action = "reject_or_teach"
        message = "Không nên dùng trực tiếp; cần dạy thêm ví dụ đúng hoặc chỉnh rule."

    return {
        "action": action,
        "message": message,
        "confidence": confidence,
        "source": source,
        "risk_reasons": sorted(set(risk_reasons)),
        "disagreement": disagreement,
    }


def build_human_explanation(description: str, amount: float, result: Dict[str, Any], decision: Dict[str, Any]) -> List[str]:
    """Generate short, product-friendly explanation lines."""
    lines = [
        f"Giao dịch: {description}",
        f"Số tiền: {amount:,.0f}",
        f"Nguồn AI: {decision.get('source')}",
        f"Confidence: {decision.get('confidence')}",
        f"Đề xuất: {result.get('category')} / Nợ {result.get('debit_account_code')} / Có {result.get('credit_account_code')}",
        f"Quyết định hệ thống: {decision.get('action')}",
    ]
    if decision.get("risk_reasons"):
        lines.append("Lý do cần cẩn thận: " + ", ".join(decision["risk_reasons"]))
    if result.get("ml_candidate"):
        cand = result["ml_candidate"]
        lines.append(
            "ML candidate chưa dùng: "
            f"{cand.get('category')} / Nợ {cand.get('debit_account_code')} / Có {cand.get('credit_account_code')} "
            f"vì {cand.get('reason_not_used')}"
        )
    return lines


def build_teaching_suggestion(description: str, amount: float, result: Dict[str, Any], decision: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return an example payload the user can correct and submit to /ai/teach."""
    if decision.get("action") == "auto_approve":
        return None
    return {
        "endpoint": "POST /ai/teach",
        "instruction": "Nếu kết quả sai, sửa 4 trường category/type/debit/credit rồi gửi để AI tự học.",
        "draft_payload": {
            "description": description,
            "amount": amount,
            "category": result.get("category"),
            "transaction_type": result.get("transaction_type"),
            "debit_account_code": result.get("debit_account_code"),
            "credit_account_code": result.get("credit_account_code"),
        },
    }


def autopilot_response(description: str, amount: float, ai_result: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap an existing AI result with safety decision, explanation, and teaching hint."""
    decision = decide_ai_action(ai_result)
    return {
        "stage": "V17 - Self-made AI Accounting Autopilot",
        "no_external_llm": True,
        "ai_result": ai_result,
        "autopilot": decision,
        "explanation": build_human_explanation(description, amount, ai_result, decision),
        "teaching_suggestion": build_teaching_suggestion(description, amount, ai_result, decision),
        "next_level": "Khi auto_approve_rate cao và wrong_rate thấp, có thể chuyển sang Cấp 4 OCR thật hoặc Cấp 5 sinh bút toán nâng cao.",
    }
