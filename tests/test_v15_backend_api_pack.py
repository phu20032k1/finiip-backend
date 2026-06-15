from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_v15_health_meta_routes():
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True
    assert health.json()["version"] in {"15.0.0", "16.0.0"}

    meta = client.get("/api/v1/meta")
    assert meta.status_code == 200
    assert meta.json()["api_prefix"] == "/api/v1"

    routes = client.get("/api/v1/routes")
    assert routes.status_code == 200
    assert any(r["path"] == "/api/v1/frontend/bootstrap" for r in routes.json()["routes"])


def test_v15_frontend_preview_and_bootstrap():
    client.post("/setup/default-accounts")

    bootstrap = client.get("/api/v1/frontend/bootstrap")
    assert bootstrap.status_code == 200
    data = bootstrap.json()
    assert data["version"] in {"15.0.0", "16.0.0"}
    assert data["counts"]["accounts"] > 0

    preview = client.post(
        "/api/v1/ai/transaction-preview",
        json={"description": "Thanh toán tiền điện EVN tháng 5", "amount": 2200000},
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["ai_result"]["category"]
    assert body["journal_balance"]["balanced"] is True
    assert "frontend_decision" in body


def test_v15_invoice_preview_no_persist():
    client.post("/setup/default-accounts")
    payload = {
        "raw_text": "HÓA ĐƠN GTGT\nSố hóa đơn: HD009\nNgày 20/05/2026\nĐơn vị bán hàng: Công ty Điện lực EVN\nCộng tiền hàng: 2.000.000\nThuế suất GTGT: 10%\nTiền thuế GTGT: 200.000\nTổng cộng thanh toán: 2.200.000",
        "create_drafts": False,
    }
    res = client.post("/api/v1/ocr/invoice-preview", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["stage"].startswith(("V15", "V16"))
    assert body["created_purchase_invoice"] is None
    assert body["frontend_decision"]["can_show_confirmation_screen"] is True
