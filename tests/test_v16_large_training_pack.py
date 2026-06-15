import json
from pathlib import Path

from ai_ml import model_status, predict_with_model
from scripts.seed_and_train_ai import load_items


def test_v16_large_dataset_files_are_loaded():
    items = load_items()
    assert len(items) >= 2500
    descriptions = "\n".join(item["description"] for item in items[:3000])
    assert "Facebook" in descriptions or "TikTok" in descriptions
    assert any(item["user_debit_account_code"] == "3334" for item in items)


def test_v16_model_was_trained_with_large_dataset():
    status = model_status()
    assert status["trained"] is True
    assert status["example_count"] >= 2500
    assert status["label_count"] >= 20


def test_v16_priority_predictions_are_better():
    tax = predict_with_model("Nộp thuế TNDN quý 2")
    assert tax["category"] == "Thuế và phí"
    assert tax["debit_account_code"] == "3334"

    tool = predict_with_model("Mua bàn ghế văn phòng cho công ty")
    assert tool["category"] == "Công cụ dụng cụ"
    assert tool["debit_account_code"] == "153"

    invoice = predict_with_model("Hóa đơn EVN tổng thanh toán 2.200.000 VAT 10%")
    assert invoice["category"] == "Chi phí điện nước"
    assert invoice["debit_account_code"] in {"642", "6427"}
