from services.accounting_ai_full import (
    analyze_transaction,
    ask_accounting_ai,
    calc_vat,
    journal_totals,
    rule_catalog,
    solve_formula,
)


def test_v85_purchase_with_vat_balanced():
    result = analyze_transaction("mua hàng hóa nhập kho chuyển khoản VAT 10%", amount=11000000, vat_rate=0.10)
    assert result["matched_rule"]["matched"] is True
    assert result["journal_check"]["is_balanced"] is True
    accounts = {line["account_code"] for line in result["journal_lines"]}
    assert "156" in accounts
    assert "1331" in accounts
    assert "112" in accounts


def test_v85_sales_with_vat_balanced():
    result = analyze_transaction("bán hàng thu tiền qua ngân hàng VAT 10%", amount=22000000, vat_rate=0.10)
    assert result["journal_check"]["is_balanced"] is True
    accounts = {line["account_code"] for line in result["journal_lines"]}
    assert "112" in accounts
    assert "511" in accounts
    assert "3331" in accounts


def test_v85_cash_large_payment_requires_review():
    result = analyze_transaction("chi tiền mặt tiếp khách", amount=25000000, has_invoice=False)
    assert result["risk_review"]["severity"] in {"review", "block"}
    assert result["decision"] != "auto_draft_allowed"


def test_v85_vat_formula_reverse():
    result = calc_vat(11000000, 0.10, amount_includes_vat=True)
    assert round(result["net_amount"]) == 10000000
    assert round(result["vat_amount"]) == 1000000


def test_v85_formula_solver_depreciation():
    result = solve_formula({"formula": "depreciation", "cost": 120000000, "months": 60})
    assert result["result"]["monthly_amount"] == 2000000


def test_v85_journal_check():
    check = journal_totals([
        {"side": "debit", "account_code": "642", "amount": 100},
        {"side": "credit", "account_code": "112", "amount": 100},
    ])
    assert check["is_balanced"] is True


def test_v85_catalog_has_many_rules():
    catalog = rule_catalog()
    assert catalog["total_rules"] >= 50


def test_v85_ask_returns_disclaimer_and_sources():
    answer = ask_accounting_ai("mua tài sản cố định có VAT hạch toán thế nào?", limit=3)
    assert "disclaimer" in answer
    assert "solver" in answer
