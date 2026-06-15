"""Smoke test API nhập liệu thật IIP từ các file Excel mẫu.

Chạy:
    python scripts/test_iip_real_input_api.py

Test này dùng FastAPI TestClient, không cần bật uvicorn.
"""
from pathlib import Path
import sys
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from main import app

client = TestClient(app)

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "iip_stage1_inputs"
IMPORT_ORDER = [
    ("02_sales_staff.xlsx", "sales-staff"),
    ("01_dealers.xlsx", "dealers"),
    ("03_price_floors.xlsx", "price-floors"),
    ("04_credit_limits.xlsx", "credit-limits"),
    ("05_orders.xlsx", "orders"),
    ("06_debts.xlsx", "debts"),
    ("07_payments.xlsx", "payments"),
    ("08_invoices.xlsx", "invoices"),
    ("09_vas_targets.xlsx", "vas-targets"),
]


def main():
    status = client.get("/iip/status")
    assert status.status_code == 200, status.text
    print("/iip/status OK")

    for filename, data_type in IMPORT_ORDER:
        path = TEMPLATE_DIR / filename
        assert path.exists(), f"Missing template: {path}"
        with path.open("rb") as f:
            res = client.post(
                f"/iip/import/{data_type}",
                files={"file": (filename, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
        assert res.status_code == 200, res.text
        body = res.json()
        print(f"IMPORT {data_type}: rows={body.get('rows')} created={body.get('created')} updated={body.get('updated')} errors={len(body.get('errors', []))}")
        assert not body.get("errors"), body

    report = client.get("/iip/chairman/morning-report")
    assert report.status_code == 200, report.text
    data = report.json()
    print("/iip/chairman/morning-report OK")
    print("today_need_collect=", data.get("today_need_collect"))
    print("overdue_debt=", data.get("overdue_debt"))
    print("top_risks=", data.get("top_risks"))

    reconcile = client.get("/iip/reconcile/4-way")
    assert reconcile.status_code == 200, reconcile.text
    print("/iip/reconcile/4-way OK", reconcile.json().get("warnings"))


if __name__ == "__main__":
    main()
