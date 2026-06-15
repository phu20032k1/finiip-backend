import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ai_autopilot import autopilot_response, decide_ai_action, labels_match


def test_labels_match_same_accounting_label():
    a = {"category": "Marketing", "transaction_type": "expense", "debit_account_code": "641", "credit_account_code": "112"}
    b = {"category": "Marketing", "transaction_type": "expense", "debit_account_code": "641", "credit_account_code": "112"}
    assert labels_match(a, b) is True


def test_autopilot_auto_approve_for_high_confidence_ml_without_warning():
    result = {
        "source": "ml_model",
        "confidence": 0.93,
        "category": "Marketing",
        "transaction_type": "expense",
        "debit_account_code": "641",
        "credit_account_code": "112",
    }
    decision = decide_ai_action(result)
    assert decision["action"] == "auto_approve"


def test_autopilot_review_when_rule_and_ml_disagree():
    result = {
        "source": "rule_based",
        "confidence": 0.7,
        "category": "Điện nước",
        "transaction_type": "expense",
        "debit_account_code": "642",
        "credit_account_code": "112",
        "ml_candidate": {
            "category": "Marketing",
            "transaction_type": "expense",
            "debit_account_code": "641",
            "credit_account_code": "112",
            "confidence": 0.52,
        },
    }
    wrapped = autopilot_response("Thanh toán quảng cáo Facebook", 3000000, result)
    assert wrapped["autopilot"]["action"] == "needs_review"
    assert wrapped["teaching_suggestion"] is not None
