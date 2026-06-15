"""Finiip V110 deterministic calculation engine.

The goal is not to replace a spreadsheet or accountant approval.  It gives the
chatbot a safe, auditable first pass for arithmetic and common accounting /
finance questions before any generative model is used.
"""
from __future__ import annotations

import ast
import math
import operator
import re
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional, Tuple

VERSION = "v110_advanced_calculation"

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _norm(text: Any) -> str:
    raw = str(text or "").lower()
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = raw.replace("đ", "d")
    return re.sub(r"\s+", " ", raw).strip()


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Giá trị không hợp lệ: {value}") from exc


def _round(value: Decimal, digits: int = 2) -> float:
    quantum = Decimal("1") if digits <= 0 else Decimal("1." + ("0" * digits))
    return float(value.quantize(quantum, rounding=ROUND_HALF_UP))


def format_number(value: Any, digits: int = 2) -> str:
    dec = _decimal(value)
    if dec == dec.to_integral_value():
        return f"{int(dec):,}".replace(",", ".")
    s = f"{dec:,.{digits}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".").rstrip("0").rstrip(",")


def format_vnd(value: Any) -> str:
    return f"{format_number(value, 0)} đồng"


def _parse_localized_number(raw: str) -> Decimal:
    s = (raw or "").strip().replace(" ", "")
    if not s:
        raise ValueError("Thiếu số")
    # Vietnamese commonly uses dot for thousands and comma for decimals.
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        tail = s.split(",")[-1]
        s = s.replace(",", ".") if len(tail) <= 3 else s.replace(",", "")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    elif "." in s:
        left, right = s.split(".", 1)
        if len(right) == 3 and len(left) >= 1:
            s = left + right
    return _decimal(s)


_UNIT_FACTORS = {
    "k": Decimal("1000"),
    "nghin": Decimal("1000"),
    "ngan": Decimal("1000"),
    "tr": Decimal("1000000"),
    "trieu": Decimal("1000000"),
    "ty": Decimal("1000000000"),
    "bil": Decimal("1000000000"),
}

_NUMBER_PATTERN = re.compile(
    r"(?<![\w.])(?P<num>[+-]?\d[\d., ]*)(?:\s*(?P<unit>ty|tỷ|trieu|triệu|tr|nghin|nghìn|ngan|ngàn|k|bil))?(?!\w)",
    flags=re.I,
)


def extract_numbers(text: str) -> List[Dict[str, Any]]:
    values: List[Dict[str, Any]] = []
    for match in _NUMBER_PATTERN.finditer(text or ""):
        raw_num = match.group("num")
        unit_raw = match.group("unit") or ""
        try:
            value = _parse_localized_number(raw_num)
        except ValueError:
            continue
        unit = _norm(unit_raw)
        factor = _UNIT_FACTORS.get(unit, Decimal("1"))
        values.append(
            {
                "raw": match.group(0),
                "number": float(value),
                "unit": unit_raw,
                "value": float(value * factor),
                "start": match.start(),
                "end": match.end(),
            }
        )
    return values


def extract_percentages(text: str) -> List[float]:
    out: List[float] = []
    for raw in re.findall(r"([+-]?\d+(?:[.,]\d+)?)\s*%", text or ""):
        try:
            out.append(float(_parse_localized_number(raw) / Decimal("100")))
        except ValueError:
            continue
    return out


def _safe_ast_eval(node: ast.AST) -> Decimal:
    if isinstance(node, ast.Expression):
        return _safe_ast_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return _decimal(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        left = _safe_ast_eval(node.left)
        right = _safe_ast_eval(node.right)
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
            raise ValueError("Không thể chia cho 0")
        if isinstance(node.op, ast.Pow) and (abs(float(right)) > 12 or abs(float(left)) > 1e12):
            raise ValueError("Lũy thừa vượt giới hạn an toàn")
        return _decimal(_ALLOWED_BINOPS[type(node.op)](left, right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _decimal(_ALLOWED_UNARYOPS[type(node.op)](_safe_ast_eval(node.operand)))
    raise ValueError("Biểu thức có toán tử không được hỗ trợ")


def safe_eval_expression(expression: str) -> Decimal:
    expr = (expression or "").strip().replace("^", "**").replace("×", "*").replace("÷", "/")
    if len(expr) > 500:
        raise ValueError("Biểu thức quá dài")
    if not re.fullmatch(r"[0-9+\-*/().%\s*]+", expr):
        raise ValueError("Biểu thức chứa ký tự không an toàn")
    tree = ast.parse(expr, mode="eval")
    return _safe_ast_eval(tree)


def _replace_number_units_for_expression(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        raw_num = match.group("num")
        unit = _norm(match.group("unit") or "")
        try:
            value = _parse_localized_number(raw_num) * _UNIT_FACTORS.get(unit, Decimal("1"))
        except ValueError:
            return match.group(0)
        return str(value)

    return _NUMBER_PATTERN.sub(repl, text or "")


def _extract_expression(question: str) -> Optional[str]:
    raw = _replace_number_units_for_expression(question)
    raw = raw.replace("%", "/100")
    raw = re.sub(r"(?i)\b(tinh|tính|bang bao nhieu|bằng bao nhiêu|ket qua|kết quả)\b", " ", raw)
    candidates = re.findall(r"[\d.()+\-*/^\s]{3,}", raw)
    candidates = [re.sub(r"\s+", "", c) for c in candidates]
    candidates = [c for c in candidates if re.search(r"[+\-*/^]", c) and re.search(r"\d", c)]
    return max(candidates, key=len) if candidates else None


def _amount_after_label(question: str, labels: Iterable[str]) -> Optional[Decimal]:
    q = question or ""
    label_expr = "|".join(re.escape(label) for label in labels)
    pattern = re.compile(
        rf"(?:{label_expr})\s*(?:là|la|:|=|khoảng|khoang)?\s*([+-]?\d[\d., ]*)\s*(tỷ|ty|triệu|trieu|tr|nghìn|nghin|ngàn|ngan|k)?",
        flags=re.I,
    )
    m = pattern.search(q)
    if not m:
        return None
    value = _parse_localized_number(m.group(1))
    return value * _UNIT_FACTORS.get(_norm(m.group(2) or ""), Decimal("1"))


def _count_after_label(question: str, labels: Iterable[str]) -> Optional[int]:
    label_expr = "|".join(re.escape(label) for label in labels)
    m = re.search(rf"(?:{label_expr})\s*(?:là|la|:|=)?\s*(\d+)", question or "", flags=re.I)
    return int(m.group(1)) if m else None


def _pct_after_label(question: str, labels: Iterable[str]) -> Optional[Decimal]:
    label_expr = "|".join(re.escape(label) for label in labels)
    m = re.search(rf"(?:{label_expr})\s*(?:là|la|:|=)?\s*([+-]?\d+(?:[.,]\d+)?)\s*%", question or "", flags=re.I)
    if not m:
        return None
    return _parse_localized_number(m.group(1)) / Decimal("100")


def _result(answer: str, formula: str, inputs: Dict[str, Any], result: Dict[str, Any], steps: List[str], checks: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "version": VERSION,
        "recognized": True,
        "answer": answer,
        "formula": formula,
        "inputs": inputs,
        "result": result,
        "steps": steps,
        "checks": checks or [],
        "needs_human_review": True,
    }


def _solve_percent_of(question: str) -> Optional[Dict[str, Any]]:
    m = re.search(r"([+-]?\d+(?:[.,]\d+)?)\s*%\s*(?:của|cua|x|\*)\s*([+-]?\d[\d., ]*)\s*(tỷ|ty|triệu|trieu|tr|nghìn|nghin|ngàn|ngan|k)?", question, flags=re.I)
    if not m:
        return None
    pct = _parse_localized_number(m.group(1)) / Decimal("100")
    amount = _parse_localized_number(m.group(2)) * _UNIT_FACTORS.get(_norm(m.group(3) or ""), Decimal("1"))
    value = amount * pct
    return _result(
        f"{format_number(pct * 100)}% của {format_vnd(amount)} = **{format_vnd(value)}**.",
        "Giá trị = Số tiền × Tỷ lệ",
        {"amount": float(amount), "rate": float(pct)},
        {"value": _round(value)},
        [f"Đổi {format_number(pct * 100)}% = {pct}", f"{format_vnd(amount)} × {pct} = {format_vnd(value)}"],
    )


def _solve_vat(question: str) -> Optional[Dict[str, Any]]:
    q = _norm(question)
    if not any(t in q for t in ["vat", "gtgt", "thue gia tri gia tang"]):
        return None
    percentages = extract_percentages(question)
    rate = Decimal(str(percentages[0] if percentages else 0.10))
    numbers = [n for n in extract_numbers(question) if not (n["end"] < len(question) and question[n["end"]:n["end"] + 1] == "%")]
    # Prefer an amount carrying a money unit, not the tax rate itself.
    money = [n for n in numbers if n.get("unit")]
    chosen = max(money or numbers, key=lambda n: abs(float(n["value"])), default=None)
    if not chosen:
        return None
    amount = _decimal(chosen["value"])
    includes = any(t in q for t in ["da gom", "bao gom", "sau thue", "tong thanh toan", "gia co vat"])
    if includes:
        net = amount / (Decimal("1") + rate)
        vat = amount - net
        gross = amount
        formula = "Giá chưa thuế = Tổng thanh toán / (1 + thuế suất)"
    else:
        net = amount
        vat = net * rate
        gross = net + vat
        formula = "VAT = Giá chưa thuế × Thuế suất"
    return _result(
        f"Giá chưa thuế: **{format_vnd(net)}**\n\nVAT {format_number(rate * 100)}%: **{format_vnd(vat)}**\n\nTổng thanh toán: **{format_vnd(gross)}**",
        formula,
        {"amount": float(amount), "rate": float(rate), "amount_includes_vat": includes},
        {"net_amount": _round(net), "vat_amount": _round(vat), "gross_amount": _round(gross)},
        [formula, f"Kết quả kiểm tra: {format_vnd(net)} + {format_vnd(vat)} = {format_vnd(gross)}"],
        ["Thuế suất cần đối chiếu theo hàng hóa, dịch vụ và thời điểm áp dụng thực tế."],
    )


def _solve_percentage_change(question: str) -> Optional[Dict[str, Any]]:
    q = _norm(question)
    if not any(t in q for t in ["tang bao nhieu %", "giam bao nhieu %", "chenh lech %", "ty le tang", "toc do tang"]):
        return None
    nums = extract_numbers(question)
    money = [n for n in nums if n.get("unit")]
    chosen = money if len(money) >= 2 else nums
    if len(chosen) < 2:
        return None
    old, new = _decimal(chosen[0]["value"]), _decimal(chosen[1]["value"])
    if old == 0:
        return _result("Không thể tính tỷ lệ thay đổi vì giá trị gốc bằng 0.", "(Mới - Cũ) / Cũ", {"old": 0, "new": float(new)}, {}, [], ["Cần một giá trị gốc khác 0."])
    delta = new - old
    rate = delta / old
    direction = "tăng" if delta >= 0 else "giảm"
    return _result(
        f"Giá trị {direction} **{format_number(abs(delta))}**, tương đương **{format_number(abs(rate) * 100)}%** so với kỳ gốc.",
        "Tỷ lệ thay đổi = (Giá trị mới - Giá trị cũ) / Giá trị cũ",
        {"old": float(old), "new": float(new)},
        {"difference": _round(delta), "change_rate": _round(rate, 6), "change_percent": _round(rate * 100, 4)},
        [f"({format_number(new)} - {format_number(old)}) / {format_number(old)} = {format_number(rate * 100)}%"],
    )


def _solve_profit(question: str) -> Optional[Dict[str, Any]]:
    q = _norm(question)
    if not any(t in q for t in ["loi nhuan", "bien loi nhuan", "lai gop", "ket qua kinh doanh"]):
        return None
    revenue = _amount_after_label(question, ["doanh thu", "revenue"])
    cogs = _amount_after_label(question, ["giá vốn", "gia von", "cogs"])
    selling = _amount_after_label(question, ["chi phí bán hàng", "chi phi ban hang"])
    admin = _amount_after_label(question, ["chi phí quản lý", "chi phi quan ly", "chi phí qldn", "chi phi qldn"])
    finance = _amount_after_label(question, ["chi phí tài chính", "chi phi tai chinh", "lãi vay", "lai vay"])
    other_income = _amount_after_label(question, ["thu nhập khác", "thu nhap khac"])
    other_expense = _amount_after_label(question, ["chi phí khác", "chi phi khac"])
    if revenue is None or cogs is None:
        return None
    selling = selling or Decimal("0")
    admin = admin or Decimal("0")
    finance = finance or Decimal("0")
    other_income = other_income or Decimal("0")
    other_expense = other_expense or Decimal("0")
    gross = revenue - cogs
    operating = gross - selling - admin - finance
    before_tax = operating + other_income - other_expense
    gross_margin = gross / revenue if revenue else Decimal("0")
    net_margin = before_tax / revenue if revenue else Decimal("0")
    return _result(
        f"Lợi nhuận gộp: **{format_vnd(gross)}** ({format_number(gross_margin * 100)}%).\n\n"
        f"Lợi nhuận trước thuế ước tính: **{format_vnd(before_tax)}** ({format_number(net_margin * 100)}% doanh thu).",
        "LNTT = Doanh thu - Giá vốn - CP bán hàng - CP quản lý - CP tài chính + Thu nhập khác - CP khác",
        {"revenue": float(revenue), "cogs": float(cogs), "selling_expenses": float(selling), "admin_expenses": float(admin), "financial_expenses": float(finance), "other_income": float(other_income), "other_expenses": float(other_expense)},
        {"gross_profit": _round(gross), "operating_profit": _round(operating), "profit_before_tax": _round(before_tax), "gross_margin": _round(gross_margin, 6), "profit_before_tax_margin": _round(net_margin, 6)},
        [f"Lợi nhuận gộp = {format_vnd(revenue)} - {format_vnd(cogs)} = {format_vnd(gross)}", f"Lợi nhuận trước thuế = {format_vnd(before_tax)}"],
        ["Chưa tính thuế TNDN và các điều chỉnh thuế nếu câu hỏi không cung cấp."],
    )


def _solve_break_even(question: str) -> Optional[Dict[str, Any]]:
    q = _norm(question)
    if not any(t in q for t in ["hoa von", "diem hoa von", "break even"]):
        return None
    fixed = _amount_after_label(question, ["chi phí cố định", "chi phi co dinh", "định phí", "dinh phi"])
    price = _amount_after_label(question, ["giá bán", "gia ban", "đơn giá bán", "don gia ban"])
    variable = _amount_after_label(question, ["biến phí", "bien phi", "chi phí biến đổi", "chi phi bien doi", "biến phí đơn vị", "bien phi don vi"])
    if fixed is None or price is None or variable is None:
        return None
    contribution = price - variable
    if contribution <= 0:
        return _result("Không có điểm hòa vốn hữu hạn vì lãi góp đơn vị không dương.", "Sản lượng hòa vốn = Định phí / (Giá bán - Biến phí đơn vị)", {"fixed_cost": float(fixed), "price": float(price), "variable_cost": float(variable)}, {}, [], ["Giá bán phải lớn hơn biến phí đơn vị."])
    units = fixed / contribution
    revenue = units * price
    return _result(
        f"Lãi góp đơn vị: **{format_vnd(contribution)}**.\n\nSản lượng hòa vốn: **{format_number(units)} đơn vị**.\n\nDoanh thu hòa vốn: **{format_vnd(revenue)}**.",
        "Q hòa vốn = Định phí / (Giá bán - Biến phí đơn vị)",
        {"fixed_cost": float(fixed), "selling_price": float(price), "variable_cost": float(variable)},
        {"contribution_per_unit": _round(contribution), "break_even_units": _round(units), "break_even_revenue": _round(revenue)},
        [f"Lãi góp = {format_vnd(price)} - {format_vnd(variable)} = {format_vnd(contribution)}", f"Q = {format_vnd(fixed)} / {format_vnd(contribution)} = {format_number(units)}"],
    )


def _solve_loan_payment(question: str) -> Optional[Dict[str, Any]]:
    q = _norm(question)
    if not any(t in q for t in ["tra gop", "khoan vay", "tien vay", "emi", "goc lai deu"]):
        return None
    principal = _amount_after_label(question, ["vay", "tiền vay", "tien vay", "gốc vay", "goc vay", "khoản vay", "khoan vay"])
    annual = _pct_after_label(question, ["lãi suất", "lai suat", "lãi", "lai"])
    months = _count_after_label(question, ["thời hạn", "thoi han", "kỳ hạn", "ky han", "trong"])
    if months is None:
        m = re.search(r"(\d+)\s*(?:tháng|thang)", question, flags=re.I)
        months = int(m.group(1)) if m else None
    if principal is None or annual is None or not months:
        return None
    monthly_rate = annual / Decimal("12")
    if monthly_rate == 0:
        payment = principal / Decimal(months)
    else:
        one = Decimal("1")
        factor = (one + monthly_rate) ** months
        payment = principal * monthly_rate * factor / (factor - one)
    total = payment * months
    interest = total - principal
    return _result(
        f"Khoản trả đều ước tính mỗi tháng: **{format_vnd(payment)}**.\n\nTổng tiền trả: **{format_vnd(total)}**; tổng lãi: **{format_vnd(interest)}**.",
        "PMT = P × r × (1+r)^n / ((1+r)^n - 1)",
        {"principal": float(principal), "annual_rate": float(annual), "months": months},
        {"monthly_payment": _round(payment), "total_payment": _round(total), "total_interest": _round(interest)},
        [f"Lãi suất tháng = {format_number(annual * 100)}% / 12 = {format_number(monthly_rate * 100, 4)}%", f"Thay vào công thức PMT với n = {months}"],
        ["Kết quả chưa gồm phí, bảo hiểm khoản vay hoặc lịch trả nợ đặc thù của ngân hàng."],
    )


def _solve_ratios(question: str) -> Optional[Dict[str, Any]]:
    q = _norm(question)
    ratio = None
    labels: Tuple[List[str], List[str]]
    if any(t in q for t in ["he so thanh toan hien hanh", "current ratio"]):
        ratio = "current_ratio"; labels = (["tài sản ngắn hạn", "tai san ngan han"], ["nợ ngắn hạn", "no ngan han"])
    elif any(t in q for t in ["he so thanh toan nhanh", "quick ratio"]):
        current_assets = _amount_after_label(question, ["tài sản ngắn hạn", "tai san ngan han"])
        inventory = _amount_after_label(question, ["hàng tồn kho", "hang ton kho", "tồn kho", "ton kho"])
        current_liabilities = _amount_after_label(question, ["nợ ngắn hạn", "no ngan han"])
        if None in (current_assets, inventory, current_liabilities) or current_liabilities == 0:
            return None
        value = (current_assets - inventory) / current_liabilities
        return _result(f"Hệ số thanh toán nhanh = **{format_number(value, 4)} lần**.", "(Tài sản ngắn hạn - Hàng tồn kho) / Nợ ngắn hạn", {"current_assets": float(current_assets), "inventory": float(inventory), "current_liabilities": float(current_liabilities)}, {"quick_ratio": _round(value, 6)}, [f"({format_number(current_assets)} - {format_number(inventory)}) / {format_number(current_liabilities)} = {format_number(value, 4)}"])
    elif any(t in q for t in ["roe", "ty suat loi nhuan tren von"]):
        ratio = "roe"; labels = (["lợi nhuận sau thuế", "loi nhuan sau thue", "lợi nhuận", "loi nhuan"], ["vốn chủ sở hữu", "von chu so huu", "vốn bình quân", "von binh quan"])
    elif any(t in q for t in ["roa", "ty suat loi nhuan tren tai san"]):
        ratio = "roa"; labels = (["lợi nhuận sau thuế", "loi nhuan sau thue", "lợi nhuận", "loi nhuan"], ["tổng tài sản", "tong tai san", "tài sản bình quân", "tai san binh quan"])
    else:
        return None
    numerator = _amount_after_label(question, labels[0])
    denominator = _amount_after_label(question, labels[1])
    if numerator is None or denominator in (None, Decimal("0")):
        return None
    value = numerator / denominator
    is_percent = ratio in {"roe", "roa"}
    display = f"{format_number(value * 100, 4)}%" if is_percent else f"{format_number(value, 4)} lần"
    return _result(f"{ratio.upper()} = **{display}**.", f"{labels[0][0]} / {labels[1][0]}", {"numerator": float(numerator), "denominator": float(denominator)}, {ratio: _round(value, 6)}, [f"{format_number(numerator)} / {format_number(denominator)} = {display}"])



def _duration_in_months(question: str) -> Optional[int]:
    """Extract an accounting/finance duration and normalize it to months."""
    q = question or ""
    m = re.search(r"(?:thời gian|thoi gian|thời hạn|thoi han|kỳ hạn|ky han|trong|sử dụng|su dung)?\s*(\d+)\s*(?:tháng|thang)", q, flags=re.I)
    if m:
        return max(1, int(m.group(1)))
    y = re.search(r"(?:thời gian|thoi gian|thời hạn|thoi han|kỳ hạn|ky han|trong|sử dụng|su dung)?\s*(\d+(?:[.,]\d+)?)\s*(?:năm|nam)", q, flags=re.I)
    if y:
        years = _parse_localized_number(y.group(1))
        return max(1, int((years * Decimal("12")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
    return None


def _solve_cogs(question: str) -> Optional[Dict[str, Any]]:
    q = _norm(question)
    if not any(t in q for t in ["gia von", "cogs", "hang ban"]):
        return None
    opening = _amount_after_label(question, ["tồn đầu kỳ", "ton dau ky", "hàng tồn kho đầu kỳ", "hang ton kho dau ky"])
    purchases = _amount_after_label(question, ["mua trong kỳ", "mua trong ky", "hàng mua", "hang mua", "nhập trong kỳ", "nhap trong ky"])
    closing = _amount_after_label(question, ["tồn cuối kỳ", "ton cuoi ky", "hàng tồn kho cuối kỳ", "hang ton kho cuoi ky"])
    if None in (opening, purchases, closing):
        return None
    cogs = opening + purchases - closing
    return _result(
        f"Giá vốn hàng bán ước tính: **{format_vnd(cogs)}**.",
        "Giá vốn = Tồn đầu kỳ + Mua trong kỳ - Tồn cuối kỳ",
        {"opening_inventory": float(opening), "purchases": float(purchases), "ending_inventory": float(closing)},
        {"cogs": _round(cogs)},
        [f"{format_vnd(opening)} + {format_vnd(purchases)} - {format_vnd(closing)} = {format_vnd(cogs)}"],
        ["Công thức giả định số liệu đã bao gồm các điều chỉnh mua hàng, hàng trả lại và chi phí thu mua phù hợp."],
    )


def _solve_depreciation_or_allocation(question: str) -> Optional[Dict[str, Any]]:
    q = _norm(question)
    is_depreciation = any(t in q for t in ["khau hao", "duong thang", "tai san co dinh"])
    is_allocation = any(t in q for t in ["phan bo", "chi phi tra truoc", "cong cu dung cu"])
    if not (is_depreciation or is_allocation):
        return None
    months = _duration_in_months(question)
    if not months:
        return None
    if is_depreciation:
        cost = _amount_after_label(question, ["nguyên giá", "nguyen gia", "giá trị tài sản", "gia tri tai san"])
        residual = _amount_after_label(question, ["giá trị thu hồi", "gia tri thu hoi", "giá trị còn lại", "gia tri con lai", "giá trị thanh lý", "gia tri thanh ly"]) or Decimal("0")
        if cost is None:
            return None
        depreciable = cost - residual
        if depreciable < 0:
            return _result(
                "Không thể tính khấu hao vì giá trị thu hồi lớn hơn nguyên giá.",
                "Khấu hao kỳ = (Nguyên giá - Giá trị thu hồi) / Số kỳ",
                {"cost": float(cost), "residual_value": float(residual), "months": months},
                {},
                [],
                ["Hãy kiểm tra lại nguyên giá và giá trị thu hồi."],
            )
        monthly = depreciable / Decimal(months)
        annual = monthly * Decimal("12")
        return _result(
            f"Giá trị phải khấu hao: **{format_vnd(depreciable)}**.\n\nKhấu hao bình quân tháng: **{format_vnd(monthly)}**.\n\nKhấu hao bình quân năm: **{format_vnd(annual)}**.",
            "Khấu hao đường thẳng mỗi tháng = (Nguyên giá - Giá trị thu hồi) / Thời gian sử dụng (tháng)",
            {"cost": float(cost), "residual_value": float(residual), "months": months},
            {"depreciable_amount": _round(depreciable), "monthly_depreciation": _round(monthly), "annual_depreciation": _round(annual)},
            [f"({format_vnd(cost)} - {format_vnd(residual)}) / {months} = {format_vnd(monthly)}/tháng"],
            ["Thời điểm bắt đầu khấu hao và thời gian sử dụng cần đối chiếu hồ sơ tài sản và quy định áp dụng."],
        )
    total = _amount_after_label(question, ["giá trị", "gia tri", "chi phí", "chi phi", "tổng tiền", "tong tien", "nguyên giá", "nguyen gia"])
    if total is None:
        money = [n for n in extract_numbers(question) if n.get("unit")]
        total = _decimal(max(money, key=lambda n: abs(float(n["value"])), default={"value": 0})["value"]) if money else None
    if total is None:
        return None
    monthly = total / Decimal(months)
    return _result(
        f"Mức phân bổ bình quân mỗi tháng: **{format_vnd(monthly)}**, trong **{months} tháng**.",
        "Mức phân bổ kỳ = Tổng giá trị cần phân bổ / Số kỳ",
        {"total_amount": float(total), "months": months},
        {"monthly_allocation": _round(monthly), "total_allocation": _round(total)},
        [f"{format_vnd(total)} / {months} = {format_vnd(monthly)}/tháng"],
        ["Cần kiểm tra ngày bắt đầu phân bổ và số kỳ còn lại khi lập bảng thực tế."],
    )


def _solve_interest(question: str) -> Optional[Dict[str, Any]]:
    q = _norm(question)
    if not any(t in q for t in ["lai don", "lai kep", "gia tri tuong lai", "tien gui", "compound interest", "simple interest"]):
        return None
    principal = _amount_after_label(question, ["tiền gốc", "tien goc", "vốn ban đầu", "von ban dau", "gửi", "gui", "tiền gửi", "tien gui", "principal"])
    rate = _pct_after_label(question, ["lãi suất", "lai suat", "tỷ suất", "ty suat", "rate"])
    months = _duration_in_months(question)
    if principal is None or rate is None or months is None:
        return None
    years = Decimal(months) / Decimal("12")
    compound = any(t in q for t in ["lai kep", "compound", "gia tri tuong lai"])
    if compound:
        monthly_compounding = any(t in q for t in ["hang thang", "hàng tháng", "theo thang", "theo tháng", "moi thang", "mỗi tháng"])
        periods_per_year = Decimal("12") if monthly_compounding else Decimal("1")
        periods = int((years * periods_per_year).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        periodic_rate = rate / periods_per_year
        future = principal * ((Decimal("1") + periodic_rate) ** periods)
        formula = "FV = P × (1 + r/m)^(m×t)"
    else:
        future = principal * (Decimal("1") + rate * years)
        periods_per_year = Decimal("1")
        periods = int(years.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        formula = "FV = P × (1 + r×t)"
    interest = future - principal
    return _result(
        f"Tiền lãi ước tính: **{format_vnd(interest)}**.\n\nGiá trị cuối kỳ: **{format_vnd(future)}**.",
        formula,
        {"principal": float(principal), "annual_rate": float(rate), "months": months, "compound": compound, "periods_per_year": int(periods_per_year)},
        {"interest": _round(interest), "future_value": _round(future)},
        [f"Thời hạn = {months} tháng = {format_number(years, 4)} năm", f"Áp dụng {formula} → {format_vnd(future)}"],
        ["Kết quả chưa gồm thuế, phí, ngày gửi thực tế và quy ước tính lãi của tổ chức tài chính."],
    )


def _extract_cash_flows(question: str) -> List[Decimal]:
    m = re.search(
        r"(?:dòng tiền|dong tien|cash flows?)\s*(?:dự kiến|du kien|hàng năm|hang nam)?\s*[:=]?\s*(.+?)(?=(?:tỷ lệ chiết khấu|ty le chiet khau|lãi suất chiết khấu|lai suat chiet khau|chiết khấu|chiet khau|wacc)\s*(?:là|la|:|=)?\s*\d|$)",
        question or "",
        flags=re.I | re.S,
    )
    if not m:
        return []
    section = m.group(1)
    values = extract_numbers(section)
    money = [v for v in values if v.get("unit")]
    chosen = money or values
    return [_decimal(v["value"]) for v in chosen]


def _npv_at_rate(cash_flows: List[Decimal], rate: Decimal) -> Decimal:
    total = Decimal("0")
    one = Decimal("1")
    for index, cash_flow in enumerate(cash_flows):
        total += cash_flow / ((one + rate) ** index)
    return total


def _estimate_irr(cash_flows: List[Decimal]) -> Optional[Decimal]:
    if not cash_flows or not (any(v < 0 for v in cash_flows) and any(v > 0 for v in cash_flows)):
        return None
    # Scan for a bracket first because unusual cash-flow sequences can have no
    # IRR or more than one IRR. We return the first economically plausible root.
    grid = [Decimal("-0.99") + Decimal(i) * Decimal("0.01") for i in range(0, 200)]
    grid += [Decimal("1") + Decimal(i) * Decimal("0.10") for i in range(0, 91)]
    previous_rate = grid[0]
    previous_value = _npv_at_rate(cash_flows, previous_rate)
    bracket: Optional[Tuple[Decimal, Decimal]] = None
    for current_rate in grid[1:]:
        current_value = _npv_at_rate(cash_flows, current_rate)
        if current_value == 0 or previous_value == 0 or (current_value > 0) != (previous_value > 0):
            bracket = (previous_rate, current_rate)
            break
        previous_rate, previous_value = current_rate, current_value
    if not bracket:
        return None
    low, high = bracket
    low_value = _npv_at_rate(cash_flows, low)
    for _ in range(120):
        mid = (low + high) / Decimal("2")
        mid_value = _npv_at_rate(cash_flows, mid)
        if abs(mid_value) < Decimal("0.0001"):
            return mid
        if (mid_value > 0) == (low_value > 0):
            low, low_value = mid, mid_value
        else:
            high = mid
    return (low + high) / Decimal("2")


def _solve_npv_irr(question: str) -> Optional[Dict[str, Any]]:
    q = _norm(question)
    wants_npv = "npv" in q or "gia tri hien tai rong" in q
    wants_irr = "irr" in q or "ty suat hoan von noi bo" in q
    if not (wants_npv or wants_irr):
        return None
    initial = _amount_after_label(question, ["vốn đầu tư ban đầu", "von dau tu ban dau", "đầu tư ban đầu", "dau tu ban dau", "chi phí đầu tư", "chi phi dau tu", "initial investment"])
    flows = _extract_cash_flows(question)
    if initial is None or not flows:
        return None
    cash_flows = [-abs(initial)] + flows
    result_values: Dict[str, Any] = {"cash_flows": [float(v) for v in cash_flows]}
    answer_parts: List[str] = []
    steps: List[str] = ["Dòng tiền kỳ 0 được ghi nhận là vốn đầu tư ra nên mang dấu âm."]
    formula_parts: List[str] = []
    checks: List[str] = []
    if wants_npv:
        rate = _pct_after_label(question, ["tỷ lệ chiết khấu", "ty le chiet khau", "lãi suất chiết khấu", "lai suat chiet khau", "chiết khấu", "chiet khau", "wacc"])
        if rate is None:
            return None
        npv = _npv_at_rate(cash_flows, rate)
        result_values.update({"discount_rate": float(rate), "npv": _round(npv)})
        answer_parts.append(f"NPV tại tỷ lệ chiết khấu {format_number(rate * 100)}%: **{format_vnd(npv)}**.")
        formula_parts.append("NPV = Σ CF_t/(1+r)^t")
        steps.append(f"Chiết khấu {len(flows)} dòng tiền về hiện tại với r = {format_number(rate * 100)}%.")
        checks.append("NPV dương thường cho thấy dự án tạo giá trị tại tỷ lệ chiết khấu đã chọn; vẫn cần xem rủi ro và giả định dòng tiền.")
    if wants_irr:
        irr = _estimate_irr(cash_flows)
        if irr is None:
            answer_parts.append("Không tìm được IRR duy nhất trong vùng kiểm tra; dòng tiền có thể không đổi dấu phù hợp hoặc có nhiều nghiệm.")
            checks.append("IRR có thể gây hiểu nhầm với dòng tiền đổi dấu nhiều lần; nên đối chiếu thêm NPV/MIRR.")
        else:
            result_values["irr"] = _round(irr, 8)
            answer_parts.append(f"IRR ước tính: **{format_number(irr * 100, 4)}%**.")
            formula_parts.append("IRR là r sao cho NPV(r) = 0")
            steps.append("Tìm nghiệm bằng quét khoảng và chia đôi, không dùng thực thi mã tùy ý.")
    return _result(
        "\n\n".join(answer_parts),
        "; ".join(formula_parts),
        {"initial_investment": float(initial), "future_cash_flows": [float(v) for v in flows]},
        result_values,
        steps,
        checks,
    )

def _solve_arithmetic(question: str) -> Optional[Dict[str, Any]]:
    expression = _extract_expression(question)
    if not expression:
        return None
    try:
        value = safe_eval_expression(expression)
    except (ValueError, SyntaxError, ZeroDivisionError):
        return None
    return _result(
        f"Kết quả: **{format_number(value, 6)}**.",
        expression,
        {"expression": expression},
        {"value": _round(value, 8)},
        [f"Tính an toàn biểu thức: `{expression}`", f"Kết quả = {format_number(value, 6)}"],
    )


def solve_advanced_text_question(question: str) -> Optional[Dict[str, Any]]:
    """Return a deterministic answer or ``None`` when no formula is recognized."""
    if not str(question or "").strip() or not re.search(r"\d", question):
        return None
    solvers = (
        _solve_vat,
        _solve_percent_of,
        _solve_percentage_change,
        _solve_cogs,
        _solve_depreciation_or_allocation,
        _solve_break_even,
        _solve_loan_payment,
        _solve_interest,
        _solve_npv_irr,
        _solve_ratios,
        _solve_profit,
        _solve_arithmetic,
    )
    for solver in solvers:
        try:
            answer = solver(question)
        except Exception:
            answer = None
        if answer:
            return answer
    return None


def capabilities() -> Dict[str, Any]:
    return {
        "version": VERSION,
        "supported": [
            "arithmetic_expression",
            "percentage_of_amount",
            "percentage_change",
            "vat_inclusive_exclusive",
            "profit_and_margins",
            "break_even",
            "loan_equal_payment",
            "straight_line_depreciation",
            "prepaid_expense_allocation",
            "cost_of_goods_sold",
            "simple_interest",
            "compound_interest",
            "npv",
            "irr",
            "current_ratio",
            "quick_ratio",
            "roa",
            "roe",
        ],
        "safety": ["AST whitelist", "division-by-zero guard", "auditable steps", "no arbitrary code execution"],
    }
