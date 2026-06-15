"""Offline smoke test cho AI Quality Layer V3, không cần bật server."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai_quality import enhance_ai_result

sample_result = {
    "category": "Chi phí quảng cáo",
    "transaction_type": "expense",
    "debit_account_code": "641",
    "debit_account_name": "Chi phí bán hàng",
    "credit_account_code": "111",
    "credit_account_name": "Tiền mặt",
    "confidence": 0.95,
    "matched_keywords": ["facebook", "quảng cáo"],
    "source": "rule_based",
}

result = enhance_ai_result(
    "Thanh toán quảng cáo Facebook 5.000.000 bằng tiền mặt",
    5_000_000,
    sample_result,
)

print("AI version:", result["ai_version"])
print("Category:", result["category"])
print("Gate:", result["quality_gate"]["decision"])
print("Calibrated confidence:", result["calibrated_confidence"])
print("Explanation:", result["explainable_ai"]["human_readable"])
print("Risk flags:", [x["code"] for x in result["risk_flags"]])
