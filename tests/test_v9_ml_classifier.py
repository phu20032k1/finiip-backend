import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_level3_ml_train_and_predict_from_teaching_examples():
    client.post('/setup/default-accounts')

    # Dạy ít nhất 2 nhãn để model học được phân biệt category.
    payload = {
        'items': [
            {
                'description': 'Chi phí chạy Zalo Ads tháng 5',
                'amount': 3500000,
                'user_category': 'Chi phí marketing',
                'user_type': 'expense',
                'user_debit_account_code': '641',
                'user_credit_account_code': '112',
                'note': 'Training ML marketing',
            },
            {
                'description': 'Thanh toán tiền điện EVN văn phòng',
                'amount': 2500000,
                'user_category': 'Chi phí điện nước',
                'user_type': 'expense',
                'user_debit_account_code': '642',
                'user_credit_account_code': '112',
                'note': 'Training ML utility',
            },
            {
                'description': 'Trả lương nhân viên qua ngân hàng',
                'amount': 35000000,
                'user_category': 'Chi phí nhân sự',
                'user_type': 'expense',
                'user_debit_account_code': '642',
                'user_credit_account_code': '112',
                'note': 'Training ML payroll',
            },
        ]
    }
    taught = client.post('/ai/teach-batch', json=payload)
    assert taught.status_code == 200

    dataset = client.get('/ai/ml/dataset')
    assert dataset.status_code == 200
    assert dataset.json()['example_count'] >= 3

    trained = client.post('/ai/ml/train', json={'min_examples': 3, 'include_corrections': True})
    assert trained.status_code == 200
    assert trained.json()['stage'].startswith('Cấp 3')

    predicted = client.post('/ai/ml/predict', json={
        'description': 'Chi phí quảng cáo Zalo Ads tháng 6',
        'amount': 4200000,
        'min_confidence': 0.0,
    })
    assert predicted.status_code == 200
    result = predicted.json()['ai_result']
    assert result['source'] == 'ml_model'
    assert result['category']
    assert result['debit_account_code']
    assert result['credit_account_code']

    analyzed = client.post('/ai/analyze', json={
        'description': 'Chi phí quảng cáo Zalo Ads tháng 7',
        'amount': 5000000,
    })
    assert analyzed.status_code == 200
    assert analyzed.json()['ai_result']['source'] in {'learning_memory', 'ml_model', 'rule_based'}
