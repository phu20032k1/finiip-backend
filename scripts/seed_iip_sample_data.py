"""Seed dữ liệu mẫu IIP Steel cho backend-first.

Run:
    python scripts/seed_iip_sample_data.py

Script này chạy trực tiếp bằng FastAPI TestClient, không cần mở uvicorn.
Sau khi seed xong, mở Swagger hoặc chạy scripts/test_iip_backend.py.
"""
from pathlib import Path
import sys
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import main

client = TestClient(main.app)


def must(method: str, path: str, json_body=None):
    res = client.request(method, path, json=json_body)
    if res.status_code >= 300:
        print(f"FAIL {method} {path}: {res.status_code}")
        print(res.text[:1000])
        raise SystemExit(1)
    return res.json()


# Seed demo lõi đã có sẵn trong backend.
must("POST", "/iip/demo/seed")

# Bổ sung thêm một số dữ liệu mẫu để frontend test nhiều trạng thái.
sample_calls = [
    ("POST", "/iip/sales-staff", {"code": "NV002", "name": "Trần Thị B", "region": "Tây Bắc"}),
    ("POST", "/iip/dealers", {"code": "DL_LAOCAI", "name": "Đại lý Lào Cai", "province": "Lào Cai", "sales_staff_code": "NV002", "rank": "A"}),
    ("POST", "/iip/dealers", {"code": "DL_LAICHAU", "name": "Đại lý Lai Châu", "province": "Lai Châu", "sales_staff_code": "NV001", "rank": "C"}),
    ("POST", "/iip/products", {"code": "VAS_D12", "name": "Thép VAS D12", "brand": "VAS", "category": "thép cây"}),
    ("POST", "/iip/credit-limits", {"dealer_code": "DL_LAOCAI", "limit_amount": 3000000000, "debt_term_days": 45, "rank": "A"}),
    ("POST", "/iip/credit-limits", {"dealer_code": "DL_LAICHAU", "limit_amount": 1000000000, "debt_term_days": 30, "rank": "C", "require_deposit_pct": 20}),
    ("POST", "/iip/price-floors", {"product_code": "VAS_D12", "province": "ALL", "floor_price": 15100000, "allowed_discount_pct": 1}),
]

for method, path, body in sample_calls:
    must(method, path, body)

# Các POST orders/invoices có khóa unique, nên bỏ qua nếu đã seed trước đó.
optional_calls = [
    ("POST", "/iip/orders", {
        "order_code": "ORD_SAMPLE_002",
        "dealer_code": "DL_LAOCAI",
        "sales_staff_code": "NV002",
        "status": "approved",
        "items": [{"product_code": "VAS_D12", "quantity_ton": 80, "unit_price": 15200000, "discount_pct": 0}]
    }),
    ("POST", "/iip/orders", {
        "order_code": "ORD_SAMPLE_003",
        "dealer_code": "DL_LAICHAU",
        "sales_staff_code": "NV001",
        "status": "approved",
        "items": [{"product_code": "VAS_D12", "quantity_ton": 50, "unit_price": 14900000, "discount_pct": 0}]
    }),
    ("POST", "/iip/invoices", {"invoice_number": "INV_SAMPLE_002", "dealer_code": "DL_LAOCAI", "order_code": "ORD_SAMPLE_002", "vat_rate": 0.1}),
    ("POST", "/iip/payments", {"dealer_code": "DL_LAOCAI", "amount": 500000000, "bank_ref": "BANK_SAMPLE_002", "matched_order_code": "ORD_SAMPLE_002", "matched_invoice_number": "INV_SAMPLE_002"}),
    ("POST", "/iip/warehouse-slips", {"slip_code": "WH_SAMPLE_002", "order_code": "ORD_SAMPLE_002", "status": "exported"}),
    ("POST", "/iip/deliveries", {"delivery_code": "DEL_SAMPLE_002", "order_code": "ORD_SAMPLE_002", "driver_name": "Lái xe mẫu", "driver_phone": "0900000000", "route_note": "Hà Nội - Lào Cai", "status": "planned"}),
]

for method, path, body in optional_calls:
    res = client.request(method, path, json=body)
    if res.status_code not in (200, 201, 409):
        print(f"WARN {method} {path}: {res.status_code} {res.text[:300]}")

report = must("GET", "/iip/chairman/morning-report")
print("Seed OK. Morning report preview:")
print(json.dumps(report, ensure_ascii=False, indent=2, default=str)[:2000])
