import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_v11_feedback_training_examples_and_evaluation_flow():
    client.post('/setup/default-accounts')
    seed = client.post('/ai/ml/seed-and-train')
    assert seed.status_code == 200

    feedback = client.post('/ai/feedback', json={
        'description': 'Thanh toán chi phí chạy LinkedIn Ads tháng 5',
        'amount': 4600000,
        'ai_category': 'Chưa phân loại',
        'ai_type': 'unknown',
        'ai_debit_account_code': None,
        'ai_credit_account_code': None,
        'ai_confidence': 0.2,
        'correct_category': 'Chi phí marketing',
        'correct_type': 'expense',
        'correct_debit_account_code': '641',
        'correct_credit_account_code': '112',
        'note': 'Feedback test V11',
        'train_after': True,
    })
    assert feedback.status_code == 200
    body = feedback.json()
    assert body['trained'] is True
    example_id = body['item']['id']

    listing = client.get('/ai/training-examples', params={'limit': 5})
    assert listing.status_code == 200
    assert listing.json()['total'] >= 1
    assert 'items' in listing.json()

    updated = client.put(f'/ai/training-examples/{example_id}', json={
        'note': 'Feedback test V11 updated',
        'user_category': 'Chi phí marketing',
    })
    assert updated.status_code == 200
    assert updated.json()['item']['note'] == 'Feedback test V11 updated'

    evaluated = client.get('/ai/ml/evaluate', params={'min_examples': 10, 'test_ratio': 0.2})
    assert evaluated.status_code == 200
    report = evaluated.json()
    assert 'accuracy_percent' in report
    assert report['test_samples'] >= 1
    assert 'weak_categories' in report

    deleted = client.delete(f'/ai/training-examples/{example_id}')
    assert deleted.status_code == 200
    assert deleted.json()['deleted_id'] == example_id
