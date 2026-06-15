"""Smoke test nhẹ cho Finiip MVP.
Chạy sau khi backend đã bật:
    python scripts/smoke_mvp.py
"""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"

def request(path, method="GET", payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as res:
        raw = res.read().decode("utf-8")
        return json.loads(raw) if raw else {}

if __name__ == "__main__":
    print("1. Health:", request("/api/v1/health")["ok"])
    print("2. Setup accounts:", request("/setup/default-accounts", "POST"))
    preview = request("/api/v1/ai/transaction-preview", "POST", {
        "description": "Thanh toán quảng cáo Facebook 5.000.000 bằng tiền mặt",
        "amount": 5000000,
        "min_confidence": 0.55,
    })
    print("3. AI category:", preview.get("ai_result", {}).get("category"))
    review = request("/ai/v19/review-queue/from-analyze", "POST", {
        "description": "Thanh toán quảng cáo Facebook 5.000.000 bằng tiền mặt",
        "amount": 5000000,
    })
    print("4. Review item:", review.get("item", {}).get("id"))
    print("5. Reports:", request("/reports/profit-loss"))
    ocr = request("/api/v1/ocr/invoice-preview", "POST", {
        "raw_text": "HÓA ĐƠN GTGT\nSố: HD001\nNhà cung cấp: EVN\nTiền hàng: 2300000\nThuế GTGT 10%: 230000\nTổng cộng: 2530000",
        "create_drafts": False,
    })
    print("6. OCR keys:", sorted(ocr.keys()))
