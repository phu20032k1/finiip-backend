import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
import main

client = TestClient(main.app)


def test_v18_feedback_learning_and_v20_retrain():
    client.post('/setup/default-accounts')
    response = client.post('/ai/v18/feedback-learning', json={
        'description': 'Thanh toán quảng cáo Facebook tháng 5',
        'amount': 3000000,
        'ai_category': 'Chưa phân loại',
        'ai_type': 'expense',
        'ai_debit_account_code': '642',
        'ai_credit_account_code': '112',
        'ai_confidence': 0.42,
        'correct_category': 'Marketing',
        'correct_type': 'expense',
        'correct_debit_account_code': '641',
        'correct_credit_account_code': '112',
        'train_after': True,
    })
    assert response.status_code == 200
    body = response.json()
    assert body['stage'].startswith('V18')
    assert body['trained_after_save'] is True
    assert body['learning_item']['user_debit_account_code'] == '641'

    retrain = client.post('/ai/v20/retrain-from-feedback', json={'min_examples': 1, 'evaluate_after': False})
    assert retrain.status_code == 200
    assert retrain.json()['model']['example_count'] >= 1


def test_v19_review_queue_decision_correct():
    client.post('/setup/default-accounts')
    created = client.post('/ai/v19/review-queue/from-analyze', json={
        'description': 'Mua laptop văn phòng chưa VAT',
        'amount': 20000000,
    })
    assert created.status_code == 200
    item_id = created.json()['item']['id']
    decision = client.post(f'/ai/v19/review-queue/{item_id}/decision', json={
        'action': 'correct',
        'correct_category': 'Tài sản cố định',
        'correct_type': 'expense',
        'correct_debit_account_code': '211',
        'correct_credit_account_code': '112',
        'train_after_correction': True,
    })
    assert decision.status_code == 200
    body = decision.json()
    assert body['item']['status'] == 'corrected'
    assert body['correction_id'] is not None


def test_v21_ocr_and_v22_double_entry_generate():
    client.post('/setup/default-accounts')
    invoice_text = '''
HÓA ĐƠN GIÁ TRỊ GIA TĂNG
Số hóa đơn: HDV21
Ngày 20/05/2026
Đơn vị bán hàng: Công ty Facebook Việt Nam
Mã số thuế: 0312345678
Cộng tiền hàng: 3.000.000
Thuế suất GTGT: 10%
Tiền thuế GTGT: 300.000
Tổng cộng thanh toán: 3.300.000
'''
    ocr = client.post('/ocr/v21/invoice-improved/text', json={'raw_text': invoice_text})
    assert ocr.status_code == 200
    assert ocr.json()['stage'].startswith('V21')
    assert ocr.json()['extracted']['total_amount'] == 3300000

    gen = client.post('/ai/v22/double-entry/generate', json={
        'description': 'Thanh toán quảng cáo Facebook có VAT',
        'amount': 3300000,
        'mode': 'expense',
        'vat_rate': 10,
        'auto_create_journal': False,
    })
    assert gen.status_code == 200
    body = gen.json()
    assert body['stage'].startswith('V22')
    assert body['balance_check']['balanced'] is True
    assert len(body['journal_lines']) >= 2
