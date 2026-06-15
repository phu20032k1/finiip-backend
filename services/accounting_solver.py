from __future__ import annotations

import re


def parse_money(text: str) -> float | None:
    t = text.lower().replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)\s*(trieu|triệu|tr|k|nghin|nghìn|ty|tỷ)?", t)

    if not match:
        return None

    number = float(match.group(1))
    unit = match.group(2) or ""

    if unit in ["trieu", "triệu", "tr"]:
        return number * 1_000_000

    if unit in ["k", "nghin", "nghìn"]:
        return number * 1_000

    if unit in ["ty", "tỷ"]:
        return number * 1_000_000_000

    return number


def format_vnd(amount: float) -> str:
    return f"{amount:,.0f}".replace(",", ".") + " đồng"


def calc_vat(amount: float, rate: float = 0.1) -> dict:
    vat = amount * rate
    total = amount + vat

    return {
        "amount_before_vat": amount,
        "vat": vat,
        "total": total
    }


def solve_vat_question(question: str) -> str:
    amount = parse_money(question)

    if amount is None:
        return "Chưa đủ dữ liệu để tính VAT. Cần có số tiền trước thuế."

    rate = 0.1
    if "8%" in question:
        rate = 0.08
    elif "5%" in question:
        rate = 0.05

    result = calc_vat(amount, rate)

    return (
        f"Tiền trước thuế: {format_vnd(result['amount_before_vat'])}\n"
        f"VAT {int(rate * 100)}%: {format_vnd(result['vat'])}\n"
        f"Tổng thanh toán: {format_vnd(result['total'])}"
    )


def calc_average_cost(begin_value: float, begin_qty: float, import_value: float, import_qty: float) -> dict:
    total_qty = begin_qty + import_qty

    if total_qty <= 0:
        raise ValueError("Không có số lượng để tính đơn giá bình quân.")

    unit_cost = (begin_value + import_value) / total_qty

    return {
        "total_value": begin_value + import_value,
        "total_qty": total_qty,
        "unit_cost": unit_cost
    }


def calc_depreciation(cost: float, months: int) -> dict:
    if months <= 0:
        raise ValueError("Số tháng khấu hao phải lớn hơn 0.")

    monthly = cost / months

    return {
        "monthly_depreciation": monthly,
        "yearly_depreciation": monthly * 12
    }


def solve_calculation(question: str) -> str:
    q = question.lower()

    if "vat" in q or "thuế" in q or "thue" in q:
        return solve_vat_question(question)

    return "Mình nhận diện đây là câu hỏi tính toán, nhưng chưa có công thức phù hợp. Cần bổ sung solver cho nghiệp vụ này."
# ============================================================
# V85 bridge: use the full accounting AI solver when available.
# Keeps old function names for backward compatibility.
# ============================================================
try:  # pragma: no cover - compatibility wrapper
    from services.accounting_ai_full import (
        analyze_transaction as analyze_transaction_full,
        ask_accounting_ai,
        solve_text_question as solve_text_question_full,
        solve_formula as solve_formula_full,
        rule_catalog as full_rule_catalog,
        capability_matrix as full_capability_matrix,
    )
except Exception:  # pragma: no cover
    analyze_transaction_full = None
    ask_accounting_ai = None
    solve_text_question_full = None
    solve_formula_full = None
    full_rule_catalog = None
    full_capability_matrix = None


def solve_accounting_question_full(question: str) -> dict:
    """Full offline accounting answer: calculation + entry suggestion + local knowledge search."""
    if solve_text_question_full is None:
        return {"answer": solve_calculation(question), "version": "legacy_solver"}
    return solve_text_question_full(question)


def solve_calculation_v85(question: str) -> str:
    """Human-readable V85 calculation wrapper for older callers."""
    if solve_text_question_full is None:
        return solve_calculation(question)
    result = solve_text_question_full(question)
    if isinstance(result, dict) and result.get("answer"):
        return str(result["answer"])
    return str(result)
