import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_ai_learning_from_correction_memory():
    client.post('/setup/default-accounts')

    created = client.post('/ai/create-transaction', json={
        'description': 'Chi phí chạy Zalo Ads tháng 5',
        'amount': 3500000,
        'auto_create_journal': False,
    })
    assert created.status_code == 200
    tx_id = created.json()['transaction']['id']

    corrected = client.post(f'/ai/transactions/{tx_id}/correct', json={
        'user_category': 'Chi phí marketing',
        'user_type': 'expense',
        'user_debit_account_code': '641',
        'user_credit_account_code': '112',
        'note': 'Dạy AI nhận diện Zalo Ads là chi phí marketing',
    })
    assert corrected.status_code == 200

    learned = client.post('/ai/analyze-with-learning', json={
        'description': 'Chi phí chạy Zalo Ads tháng 6',
        'amount': 4200000,
    })
    assert learned.status_code == 200
    result = learned.json()['ai_result']
    assert result['source'] == 'learning_memory'
    assert result['category'] == 'Chi phí marketing'
    assert result['debit_account_code'] == '641'
    assert result['credit_account_code'] == '112'


def test_ai_accuracy_and_rule_suggestions_available():
    accuracy = client.get('/ai/accuracy')
    assert accuracy.status_code == 200
    assert 'estimated_accuracy_percent' in accuracy.json()

    suggestions = client.get('/ai/rule-suggestions')
    assert suggestions.status_code == 200
    assert 'items' in suggestions.json()
