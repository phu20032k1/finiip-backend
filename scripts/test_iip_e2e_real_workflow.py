"""End-to-end test for IIP Stage 1 real-input backend.

Run from project root:
    python scripts/test_iip_e2e_real_workflow.py

The test uses FastAPI TestClient, so you do not need to start uvicorn first.
It creates unique sample records, then checks the main chairman/risk APIs that
frontend will call later.
"""
from __future__ import annotations

from datetime import date, timedelta, datetime
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def assert_ok(resp, label: str):
    if resp.status_code >= 400:
        raise AssertionError(f"{label} failed: {resp.status_code} {resp.text}")
    return resp.json()


def post(path: str, payload: dict, label: str):
    return assert_ok(client.post(path, json=payload), label)


def get(path: str, label: str):
    return assert_ok(client.get(path), label)


def main():
    suffix = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    dealer_code = f"DL_E2E_{suffix}"
    staff_code = f"NV_E2E_{suffix}"
    product_code = f"VAS_E2E_{suffix}"
    order_code = f"ORD_E2E_{suffix}"
    invoice_no = f"INV_E2E_{suffix}"

    print("1) Check backend status")
    status = get("/iip/status", "status")
    print("   OK:", status.get("platform"), status.get("version"))

    print("2) Create real-input master data")
    post("/iip/sales-staff", {
        "code": staff_code,
        "name": "Nguyễn Văn E2E",
        "phone": "0900000000",
        "region": "Tây Bắc",
        "status": "active",
    }, "create sales staff")
    post("/iip/dealers", {
        "code": dealer_code,
        "name": "Đại lý E2E Sơn La",
        "province": "Sơn La",
        "phone": "0911111111",
        "sales_staff_code": staff_code,
        "rank": "B",
        "status": "active",
    }, "create dealer")
    post("/iip/products", {
        "code": product_code,
        "name": "Thép VAS E2E D10",
        "brand": "VAS",
        "category": "Thép cây",
        "unit": "ton",
        "status": "active",
    }, "create product")
    post("/iip/price-floors", {
        "product_code": product_code,
        "province": "ALL",
        "effective_from": str(date.today() - timedelta(days=10)),
        "floor_price": 14200000,
        "allowed_discount_pct": 0,
    }, "create price floor")
    post("/iip/credit-limits", {
        "dealer_code": dealer_code,
        "limit_amount": 500000000,
        "debt_term_days": 30,
        "rank": "B",
        "require_deposit_pct": 0,
    }, "create credit limit")

    print("3) Create transactions that should trigger alerts")
    post("/iip/orders", {
        "order_code": order_code,
        "order_date": str(date.today()),
        "dealer_code": dealer_code,
        "sales_staff_code": staff_code,
        "status": "approved",
        "items": [{
            "product_code": product_code,
            "quantity_ton": 20,
            "unit_price": 14000000,
            "discount_pct": 0,
        }],
        "note": "E2E: cố tình bán dưới giá sàn để test cảnh báo",
    }, "create low-price order")
    post("/iip/debts", {
        "dealer_code": dealer_code,
        "order_code": order_code,
        "debt_date": str(date.today() - timedelta(days=60)),
        "due_date": str(date.today() - timedelta(days=30)),
        "original_amount": 900000000,
        "paid_amount": 100000000,
        "status": "open",
        "note": "E2E: nợ quá hạn và vượt hạn mức",
    }, "create overdue debt")
    post("/iip/payments", {
        "payment_date": str(date.today()),
        "dealer_code": dealer_code,
        "amount": 100000000,
        "bank_ref": f"VCB_E2E_{suffix}",
        "matched_order_code": order_code,
        "matched_invoice_number": invoice_no,
    }, "create payment")
    post("/iip/invoices", {
        "invoice_number": invoice_no,
        "invoice_date": str(date.today()),
        "dealer_code": dealer_code,
        "order_code": order_code,
        "subtotal": 280000000,
        "vat_rate": 0.1,
        "status": "issued",
    }, "create invoice")

    print("4) Read chairman/risk APIs")
    report = get("/iip/chairman/morning-report", "morning report")
    overdue = get("/iip/risk/overdue-debts", "overdue debts")
    limits = get("/iip/risk/credit-limit-violations", "credit limit violations")
    low_price = get("/iip/risk/low-price-sales", "low price sales")
    reconcile = get("/iip/reconcile/4-way", "4-way reconcile")
    vas = get("/iip/vas/progress", "VAS progress")

    assert report, "Morning report is empty"
    assert any(row.get("dealer_code") == dealer_code for row in overdue.get("items", [])), "Expected overdue alert not found"
    assert any(row.get("dealer_code") == dealer_code for row in limits.get("items", [])), "Expected credit-limit alert not found"
    assert any(row.get("order_code") == order_code for row in low_price.get("items", [])), "Expected low-price alert not found"

    print("\nE2E OK")
    print("- Dealer:", dealer_code)
    print("- Order:", order_code)
    print("- Morning report keys:", sorted(report.keys()))
    print("- Overdue alerts:", len(overdue.get("items", [])))
    print("- Credit-limit alerts:", len(limits.get("items", [])))
    print("- Low-price alerts:", len(low_price.get("items", [])))
    print("- Reconcile summary keys:", sorted(reconcile.keys()))
    print("- VAS progress keys:", sorted(vas.keys()))


if __name__ == "__main__":
    main()
