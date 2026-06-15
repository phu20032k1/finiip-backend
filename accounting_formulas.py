"""Finiip V13 - Accounting Formula Engine.

Bộ công thức kế toán thuần Python, không phụ thuộc DB.
Mục tiêu: tính toán rõ ràng, kiểm tra được, dễ gọi từ API hoặc AI.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isclose
from typing import Any, Dict, Iterable, List, Optional


MONEY_TOLERANCE = 1.0


def _round_money(value: float) -> float:
    return round(float(value or 0), 2)


def calculate_vat(*, subtotal: Optional[float] = None, vat_rate: float = 10, vat_amount: Optional[float] = None, total: Optional[float] = None) -> Dict[str, Any]:
    """Tính VAT theo 3 trường hợp: biết subtotal, biết total, hoặc biết vat_amount."""
    rate = float(vat_rate or 0)
    if rate < 0:
        raise ValueError("vat_rate không được âm")

    if subtotal is not None:
        base = float(subtotal)
        tax = float(vat_amount) if vat_amount is not None else base * rate / 100
        gross = float(total) if total is not None else base + tax
    elif total is not None:
        gross = float(total)
        base = gross / (1 + rate / 100) if rate else gross
        tax = float(vat_amount) if vat_amount is not None else gross - base
    elif vat_amount is not None and rate:
        tax = float(vat_amount)
        base = tax / (rate / 100)
        gross = base + tax
    else:
        raise ValueError("Cần subtotal, total hoặc vat_amount để tính VAT")

    expected_total = base + tax
    return {
        "subtotal": _round_money(base),
        "vat_rate": rate,
        "vat_amount": _round_money(tax),
        "total": _round_money(gross),
        "expected_total": _round_money(expected_total),
        "balanced": isclose(gross, expected_total, abs_tol=MONEY_TOLERANCE),
        "difference": _round_money(gross - expected_total),
        "formula": "total = subtotal + vat_amount; vat_amount = subtotal * vat_rate / 100",
    }


def calculate_straight_line_depreciation(*, cost: float, salvage_value: float = 0, useful_life_months: int = 36, months_used: Optional[int] = None) -> Dict[str, Any]:
    if cost <= 0:
        raise ValueError("cost phải > 0")
    if useful_life_months <= 0:
        raise ValueError("useful_life_months phải > 0")
    depreciable = max(float(cost) - float(salvage_value or 0), 0)
    monthly = depreciable / useful_life_months
    months = useful_life_months if months_used is None else max(0, min(int(months_used), useful_life_months))
    accumulated = monthly * months
    return {
        "cost": _round_money(cost),
        "salvage_value": _round_money(salvage_value),
        "useful_life_months": useful_life_months,
        "monthly_depreciation": _round_money(monthly),
        "months_used": months,
        "accumulated_depreciation": _round_money(accumulated),
        "remaining_value": _round_money(float(cost) - accumulated),
        "formula": "monthly_depreciation = (cost - salvage_value) / useful_life_months",
        "suggested_entry": {
            "debit": {"account_code": "642", "name": "Chi phí quản lý doanh nghiệp", "amount": _round_money(monthly)},
            "credit": {"account_code": "214", "name": "Hao mòn tài sản cố định", "amount": _round_money(monthly)},
        },
    }


def calculate_prepaid_allocation(*, total_amount: float, allocation_months: int, months_allocated: int = 1) -> Dict[str, Any]:
    if total_amount <= 0:
        raise ValueError("total_amount phải > 0")
    if allocation_months <= 0:
        raise ValueError("allocation_months phải > 0")
    months = max(0, min(int(months_allocated), int(allocation_months)))
    monthly = float(total_amount) / allocation_months
    allocated = monthly * months
    return {
        "total_amount": _round_money(total_amount),
        "allocation_months": allocation_months,
        "monthly_allocation": _round_money(monthly),
        "months_allocated": months,
        "allocated_amount": _round_money(allocated),
        "remaining_amount": _round_money(float(total_amount) - allocated),
        "formula": "monthly_allocation = total_amount / allocation_months",
        "suggested_entry": {
            "debit": {"account_code": "642", "name": "Chi phí quản lý doanh nghiệp", "amount": _round_money(monthly)},
            "credit": {"account_code": "242", "name": "Chi phí trả trước", "amount": _round_money(monthly)},
        },
    }


def calculate_gross_profit(*, revenue: float, cogs: float) -> Dict[str, Any]:
    gross_profit = float(revenue or 0) - float(cogs or 0)
    margin = gross_profit / revenue * 100 if revenue else 0
    return {
        "revenue": _round_money(revenue),
        "cogs": _round_money(cogs),
        "gross_profit": _round_money(gross_profit),
        "gross_margin_percent": _round_money(margin),
        "formula": "gross_profit = revenue - cogs; gross_margin = gross_profit / revenue",
    }


def calculate_net_profit(*, revenue: float, cogs: float = 0, operating_expenses: float = 0, other_income: float = 0, other_expenses: float = 0, tax_expense: float = 0) -> Dict[str, Any]:
    gross_profit = float(revenue or 0) - float(cogs or 0)
    operating_profit = gross_profit - float(operating_expenses or 0)
    profit_before_tax = operating_profit + float(other_income or 0) - float(other_expenses or 0)
    net_profit = profit_before_tax - float(tax_expense or 0)
    return {
        "revenue": _round_money(revenue),
        "cogs": _round_money(cogs),
        "operating_expenses": _round_money(operating_expenses),
        "other_income": _round_money(other_income),
        "other_expenses": _round_money(other_expenses),
        "tax_expense": _round_money(tax_expense),
        "gross_profit": _round_money(gross_profit),
        "operating_profit": _round_money(operating_profit),
        "profit_before_tax": _round_money(profit_before_tax),
        "net_profit": _round_money(net_profit),
        "net_margin_percent": _round_money(net_profit / revenue * 100 if revenue else 0),
        "formula": "net_profit = revenue - cogs - operating_expenses + other_income - other_expenses - tax_expense",
    }


def calculate_corporate_income_tax(*, profit_before_tax: float, tax_rate: float = 20, non_deductible_expenses: float = 0, tax_exempt_income: float = 0) -> Dict[str, Any]:
    taxable_income = max(float(profit_before_tax or 0) + float(non_deductible_expenses or 0) - float(tax_exempt_income or 0), 0)
    tax = taxable_income * float(tax_rate or 0) / 100
    return {
        "profit_before_tax": _round_money(profit_before_tax),
        "non_deductible_expenses": _round_money(non_deductible_expenses),
        "tax_exempt_income": _round_money(tax_exempt_income),
        "taxable_income": _round_money(taxable_income),
        "tax_rate": float(tax_rate or 0),
        "tax_expense": _round_money(tax),
        "formula": "taxable_income = profit_before_tax + non_deductible_expenses - tax_exempt_income; tax = taxable_income * tax_rate",
    }


def check_journal_balance(lines: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    debit = 0.0
    credit = 0.0
    normalized: List[Dict[str, Any]] = []
    for line in lines:
        side = str(line.get("side", "")).lower()
        amount = float(line.get("amount") or 0)
        if side in {"debit", "no", "nợ"}:
            debit += amount
        elif side in {"credit", "co", "có"}:
            credit += amount
        normalized.append({**line, "amount": _round_money(amount)})
    diff = debit - credit
    return {
        "total_debit": _round_money(debit),
        "total_credit": _round_money(credit),
        "difference": _round_money(diff),
        "balanced": isclose(debit, credit, abs_tol=MONEY_TOLERANCE),
        "lines": normalized,
        "formula": "total_debit must equal total_credit",
    }


def calculate_financial_ratios(*, current_assets: float = 0, current_liabilities: float = 0, total_assets: float = 0, total_liabilities: float = 0, equity: float = 0, revenue: float = 0, net_profit: float = 0, inventory: float = 0, cash: float = 0) -> Dict[str, Any]:
    def safe_div(a: float, b: float) -> Optional[float]:
        return _round_money(a / b) if b else None
    return {
        "current_ratio": safe_div(current_assets, current_liabilities),
        "quick_ratio": safe_div(float(current_assets or 0) - float(inventory or 0), current_liabilities),
        "cash_ratio": safe_div(cash, current_liabilities),
        "debt_to_assets": safe_div(total_liabilities, total_assets),
        "debt_to_equity": safe_div(total_liabilities, equity),
        "net_margin": safe_div(net_profit, revenue),
        "return_on_assets": safe_div(net_profit, total_assets),
        "return_on_equity": safe_div(net_profit, equity),
        "formula": "ratios are returned as decimals, e.g. 0.25 = 25%",
    }


def calculate_break_even(*, fixed_costs: float, selling_price_per_unit: float, variable_cost_per_unit: float) -> Dict[str, Any]:
    contribution = float(selling_price_per_unit) - float(variable_cost_per_unit)
    if contribution <= 0:
        raise ValueError("selling_price_per_unit phải lớn hơn variable_cost_per_unit")
    units = float(fixed_costs) / contribution
    revenue = units * float(selling_price_per_unit)
    return {
        "fixed_costs": _round_money(fixed_costs),
        "selling_price_per_unit": _round_money(selling_price_per_unit),
        "variable_cost_per_unit": _round_money(variable_cost_per_unit),
        "contribution_margin_per_unit": _round_money(contribution),
        "break_even_units": _round_money(units),
        "break_even_revenue": _round_money(revenue),
        "formula": "break_even_units = fixed_costs / (selling_price_per_unit - variable_cost_per_unit)",
    }



# =========================
# V14 Advanced Accounting Engine
# =========================

def calculate_fifo_inventory(*, beginning_layers: Optional[List[Dict[str, Any]]] = None, purchases: Optional[List[Dict[str, Any]]] = None, sales_quantity: float = 0) -> Dict[str, Any]:
    """Tính giá vốn và tồn kho cuối kỳ theo FIFO.

    Mỗi layer có dạng {"quantity": 10, "unit_cost": 100000, "label": "optional"}.
    FIFO xuất trước từ lớp hàng cũ nhất.
    """
    if sales_quantity < 0:
        raise ValueError("sales_quantity không được âm")
    layers = []
    for source, rows in (("beginning", beginning_layers or []), ("purchase", purchases or [])):
        for idx, row in enumerate(rows, start=1):
            qty = float(row.get("quantity") or 0)
            cost = float(row.get("unit_cost") or 0)
            if qty < 0 or cost < 0:
                raise ValueError("quantity và unit_cost không được âm")
            if qty:
                layers.append({
                    "source": source,
                    "label": row.get("label") or f"{source}_{idx}",
                    "quantity": qty,
                    "unit_cost": cost,
                })

    remaining_to_sell = float(sales_quantity or 0)
    consumed: List[Dict[str, Any]] = []
    ending_layers: List[Dict[str, Any]] = []
    cogs = 0.0

    for layer in layers:
        available = float(layer["quantity"])
        take = min(available, remaining_to_sell)
        if take > 0:
            amount = take * float(layer["unit_cost"])
            cogs += amount
            consumed.append({**layer, "quantity_sold": _round_money(take), "amount": _round_money(amount)})
            remaining_to_sell -= take
        leftover = available - take
        if leftover > 0:
            ending_layers.append({**layer, "quantity": _round_money(leftover), "amount": _round_money(leftover * float(layer["unit_cost"]))})

    ending_qty = sum(float(x["quantity"]) for x in ending_layers)
    ending_value = sum(float(x["amount"]) for x in ending_layers)
    return {
        "method": "FIFO",
        "sales_quantity": _round_money(sales_quantity),
        "quantity_sold": _round_money(float(sales_quantity or 0) - remaining_to_sell),
        "shortage_quantity": _round_money(remaining_to_sell),
        "cogs": _round_money(cogs),
        "ending_quantity": _round_money(ending_qty),
        "ending_inventory_value": _round_money(ending_value),
        "consumed_layers": consumed,
        "ending_layers": ending_layers,
        "formula": "FIFO: hàng nhập trước được xuất trước; COGS = tổng(quantity_sold_from_layer * unit_cost_layer)",
        "warning": "Không đủ tồn kho để xuất" if remaining_to_sell > MONEY_TOLERANCE else None,
    }


def calculate_weighted_average_inventory(*, beginning_quantity: float = 0, beginning_value: float = 0, purchases: Optional[List[Dict[str, Any]]] = None, sales_quantity: float = 0) -> Dict[str, Any]:
    """Tính giá vốn theo bình quân gia quyền cuối kỳ."""
    if beginning_quantity < 0 or beginning_value < 0 or sales_quantity < 0:
        raise ValueError("Số lượng/giá trị không được âm")
    purchase_qty = 0.0
    purchase_value = 0.0
    for row in purchases or []:
        qty = float(row.get("quantity") or 0)
        if "amount" in row and row.get("amount") is not None:
            value = float(row.get("amount") or 0)
        else:
            value = qty * float(row.get("unit_cost") or 0)
        if qty < 0 or value < 0:
            raise ValueError("purchase quantity/value không được âm")
        purchase_qty += qty
        purchase_value += value

    available_qty = float(beginning_quantity or 0) + purchase_qty
    available_value = float(beginning_value or 0) + purchase_value
    avg_cost = available_value / available_qty if available_qty else 0
    sold_qty = min(float(sales_quantity or 0), available_qty)
    cogs = sold_qty * avg_cost
    ending_qty = available_qty - sold_qty
    ending_value = ending_qty * avg_cost
    shortage = max(float(sales_quantity or 0) - available_qty, 0)
    return {
        "method": "WEIGHTED_AVERAGE_PERIODIC",
        "available_quantity": _round_money(available_qty),
        "available_value": _round_money(available_value),
        "average_unit_cost": _round_money(avg_cost),
        "sales_quantity": _round_money(sales_quantity),
        "quantity_sold": _round_money(sold_qty),
        "shortage_quantity": _round_money(shortage),
        "cogs": _round_money(cogs),
        "ending_quantity": _round_money(ending_qty),
        "ending_inventory_value": _round_money(ending_value),
        "formula": "average_unit_cost = (beginning_value + purchase_value) / (beginning_quantity + purchase_quantity); COGS = quantity_sold * average_unit_cost",
        "warning": "Không đủ tồn kho để xuất" if shortage > MONEY_TOLERANCE else None,
    }


def calculate_payroll_basic(*, gross_salary: float, employee_social_rate: float = 8, employee_health_rate: float = 1.5, employee_unemployment_rate: float = 1, personal_income_tax: float = 0, employer_social_rate: float = 17.5, employer_health_rate: float = 3, employer_unemployment_rate: float = 1) -> Dict[str, Any]:
    """Tính lương cơ bản theo các tỷ lệ BH người lao động/người sử dụng lao động.

    Đây là công thức tổng quát; không thay thế tư vấn thuế/lương theo luật mới nhất.
    """
    if gross_salary < 0:
        raise ValueError("gross_salary không được âm")
    g = float(gross_salary or 0)
    emp_si = g * float(employee_social_rate or 0) / 100
    emp_hi = g * float(employee_health_rate or 0) / 100
    emp_ui = g * float(employee_unemployment_rate or 0) / 100
    employee_insurance = emp_si + emp_hi + emp_ui
    net_salary = g - employee_insurance - float(personal_income_tax or 0)
    er_si = g * float(employer_social_rate or 0) / 100
    er_hi = g * float(employer_health_rate or 0) / 100
    er_ui = g * float(employer_unemployment_rate or 0) / 100
    employer_contribution = er_si + er_hi + er_ui
    total_company_cost = g + employer_contribution
    return {
        "gross_salary": _round_money(g),
        "employee_deductions": {
            "social_insurance": _round_money(emp_si),
            "health_insurance": _round_money(emp_hi),
            "unemployment_insurance": _round_money(emp_ui),
            "personal_income_tax": _round_money(personal_income_tax),
            "total": _round_money(employee_insurance + float(personal_income_tax or 0)),
        },
        "net_salary": _round_money(net_salary),
        "employer_contributions": {
            "social_insurance": _round_money(er_si),
            "health_insurance": _round_money(er_hi),
            "unemployment_insurance": _round_money(er_ui),
            "total": _round_money(employer_contribution),
        },
        "total_company_cost": _round_money(total_company_cost),
        "suggested_entries": [
            {"debit": "642/622/627/641", "credit": "334", "amount": _round_money(g), "meaning": "Ghi nhận chi phí lương phải trả"},
            {"debit": "334", "credit": "338", "amount": _round_money(employee_insurance), "meaning": "Khấu trừ BH phần người lao động"},
            {"debit": "334", "credit": "3335", "amount": _round_money(personal_income_tax), "meaning": "Khấu trừ thuế TNCN"},
            {"debit": "642/622/627/641", "credit": "338", "amount": _round_money(employer_contribution), "meaning": "Ghi nhận BH phần doanh nghiệp"},
        ],
        "formula": "net_salary = gross_salary - employee_insurance - personal_income_tax; total_company_cost = gross_salary + employer_contributions",
    }


def calculate_accounts_aging(*, items: List[Dict[str, Any]], as_of: Optional[date] = None) -> Dict[str, Any]:
    """Phân tuổi công nợ phải thu/phải trả theo due_date."""
    ref = as_of or date.today()
    buckets = {
        "not_due": 0.0,
        "0_30": 0.0,
        "31_60": 0.0,
        "61_90": 0.0,
        "over_90": 0.0,
    }
    details = []
    for row in items:
        amount = float(row.get("amount") or 0)
        due = row.get("due_date")
        if isinstance(due, str):
            due_date = date.fromisoformat(due)
        elif isinstance(due, date):
            due_date = due
        else:
            due_date = ref
        days_overdue = (ref - due_date).days
        if days_overdue <= 0:
            bucket = "not_due"
        elif days_overdue <= 30:
            bucket = "0_30"
        elif days_overdue <= 60:
            bucket = "31_60"
        elif days_overdue <= 90:
            bucket = "61_90"
        else:
            bucket = "over_90"
        buckets[bucket] += amount
        details.append({
            "name": row.get("name") or row.get("party") or "Unknown",
            "amount": _round_money(amount),
            "due_date": due_date.isoformat(),
            "days_overdue": days_overdue,
            "bucket": bucket,
        })
    return {
        "as_of": ref.isoformat(),
        "total": _round_money(sum(buckets.values())),
        "buckets": {k: _round_money(v) for k, v in buckets.items()},
        "details": details,
        "formula": "days_overdue = as_of - due_date; bucket theo số ngày quá hạn",
    }


def generate_period_closing_entries(*, revenue: float = 0, cogs: float = 0, selling_expenses: float = 0, admin_expenses: float = 0, financial_expenses: float = 0, other_expenses: float = 0, tax_expense: float = 0) -> Dict[str, Any]:
    """Gợi ý bút toán kết chuyển cuối kỳ theo tài khoản VN cơ bản."""
    entries = []
    def add(debit: str, credit: str, amount: float, meaning: str):
        if amount and abs(float(amount)) > MONEY_TOLERANCE:
            entries.append({"debit_account_code": debit, "credit_account_code": credit, "amount": _round_money(amount), "meaning": meaning})
    add("511", "911", revenue, "Kết chuyển doanh thu bán hàng")
    add("911", "632", cogs, "Kết chuyển giá vốn")
    add("911", "641", selling_expenses, "Kết chuyển chi phí bán hàng")
    add("911", "642", admin_expenses, "Kết chuyển chi phí quản lý")
    add("911", "635", financial_expenses, "Kết chuyển chi phí tài chính")
    add("911", "811", other_expenses, "Kết chuyển chi phí khác")
    add("911", "821", tax_expense, "Kết chuyển chi phí thuế TNDN")
    profit_before_tax = float(revenue or 0) - float(cogs or 0) - float(selling_expenses or 0) - float(admin_expenses or 0) - float(financial_expenses or 0) - float(other_expenses or 0)
    net_profit = profit_before_tax - float(tax_expense or 0)
    if net_profit > MONEY_TOLERANCE:
        add("911", "421", net_profit, "Kết chuyển lãi sau thuế")
    elif net_profit < -MONEY_TOLERANCE:
        add("421", "911", abs(net_profit), "Kết chuyển lỗ")
    return {
        "profit_before_tax": _round_money(profit_before_tax),
        "net_profit": _round_money(net_profit),
        "entries": entries,
        "entry_count": len(entries),
        "formula": "net_profit = revenue - cogs - expenses - tax_expense; kết chuyển qua TK 911 và 421",
    }


def build_basic_financial_statements(*, cash: float = 0, receivables: float = 0, inventory: float = 0, fixed_assets: float = 0, accumulated_depreciation: float = 0, payables: float = 0, loans: float = 0, owner_equity: float = 0, revenue: float = 0, cogs: float = 0, operating_expenses: float = 0, tax_expense: float = 0) -> Dict[str, Any]:
    """Lập BCTC cơ bản từ các số tổng hợp đầu vào."""
    net_fixed_assets = float(fixed_assets or 0) - float(accumulated_depreciation or 0)
    total_assets = float(cash or 0) + float(receivables or 0) + float(inventory or 0) + net_fixed_assets
    total_liabilities = float(payables or 0) + float(loans or 0)
    profit = calculate_net_profit(revenue=revenue, cogs=cogs, operating_expenses=operating_expenses, tax_expense=tax_expense)
    ending_equity = float(owner_equity or 0) + float(profit["net_profit"])
    liabilities_and_equity = total_liabilities + ending_equity
    return {
        "balance_sheet": {
            "assets": {
                "cash": _round_money(cash),
                "receivables": _round_money(receivables),
                "inventory": _round_money(inventory),
                "fixed_assets": _round_money(fixed_assets),
                "accumulated_depreciation": _round_money(accumulated_depreciation),
                "net_fixed_assets": _round_money(net_fixed_assets),
                "total_assets": _round_money(total_assets),
            },
            "liabilities": {"payables": _round_money(payables), "loans": _round_money(loans), "total_liabilities": _round_money(total_liabilities)},
            "equity": {"opening_equity": _round_money(owner_equity), "current_period_profit": profit["net_profit"], "ending_equity": _round_money(ending_equity)},
            "liabilities_and_equity": _round_money(liabilities_and_equity),
            "balanced": isclose(total_assets, liabilities_and_equity, abs_tol=MONEY_TOLERANCE),
            "difference": _round_money(total_assets - liabilities_and_equity),
        },
        "income_statement": profit,
        "formula": "assets = liabilities + equity; ending_equity = opening_equity + net_profit",
    }

def formula_catalog() -> List[Dict[str, Any]]:
    return [
        {"id": "vat", "name": "Tính VAT", "endpoint": "/formulas/vat"},
        {"id": "depreciation", "name": "Khấu hao đường thẳng", "endpoint": "/formulas/depreciation"},
        {"id": "prepaid_allocation", "name": "Phân bổ chi phí trả trước", "endpoint": "/formulas/prepaid-allocation"},
        {"id": "gross_profit", "name": "Lợi nhuận gộp", "endpoint": "/formulas/profit/gross"},
        {"id": "net_profit", "name": "Lợi nhuận thuần", "endpoint": "/formulas/profit/net"},
        {"id": "cit", "name": "Thuế TNDN", "endpoint": "/formulas/tax/cit"},
        {"id": "journal_balance", "name": "Kiểm tra Nợ/Có", "endpoint": "/formulas/journal/check-balance"},
        {"id": "financial_ratios", "name": "Tỷ số tài chính", "endpoint": "/formulas/ratios"},
        {"id": "break_even", "name": "Điểm hòa vốn", "endpoint": "/formulas/break-even"},
        {"id": "inventory_fifo", "name": "Tồn kho FIFO và giá vốn", "endpoint": "/formulas/inventory/fifo"},
        {"id": "inventory_weighted_average", "name": "Tồn kho bình quân gia quyền", "endpoint": "/formulas/inventory/weighted-average"},
        {"id": "payroll_basic", "name": "Lương, BH, thuế TNCN cơ bản", "endpoint": "/formulas/payroll/basic"},
        {"id": "accounts_aging", "name": "Tuổi công nợ phải thu/phải trả", "endpoint": "/formulas/accounts/aging"},
        {"id": "period_closing", "name": "Kết chuyển cuối kỳ", "endpoint": "/formulas/closing/period"},
        {"id": "financial_statements_basic", "name": "BCTC cơ bản", "endpoint": "/formulas/statements/basic"},
    ]
