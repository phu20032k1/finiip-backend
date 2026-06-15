from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_v405_seed_sample_data_chatbot_reports_learning():
    seed = client.post('/import/v40-5/sample-data?auto_post=true')
    assert seed.status_code == 200
    assert seed.json()['batch']['posted_count'] >= 1

    status = client.get('/import/v40-5/status')
    assert status.status_code == 200
    assert status.json()['raw_transactions'] >= 1

    vat_chat = client.post('/ai/v41/chat', json={'message': 'Tính VAT tháng này'})
    assert vat_chat.status_code == 200
    assert vat_chat.json()['intent'] == 'vat_report'
    assert 'VAT phải nộp' in vat_chat.json()['answer']

    summary_chat = client.post('/ai/v41/chat', json={'message': 'Làm báo cáo tổng hợp tháng này'})
    assert summary_chat.status_code == 200
    assert summary_chat.json()['intent'] == 'summary_report'

    memory = client.get('/ai/learning/v40-5/memory')
    assert memory.status_code == 200
    assert memory.json()['count'] >= 1


def test_v405_bulk_import_and_v42_confirmation_flow():
    bulk = client.post('/import/v40-5/transactions/bulk', json={
        'source': 'pytest_bulk',
        'auto_create_drafts': True,
        'auto_approve_safe': True,
        'items': [
            {'description': 'Bán hàng test bulk chuyển khoản', 'amount': 1000000, 'vat_rate': 0.1, 'payment_method': 'bank'},
            {'description': 'Chi phí marketing test bulk', 'amount': 500000, 'vat_rate': 0.1, 'payment_method': 'bank'},
        ]
    })
    assert bulk.status_code == 200
    assert bulk.json()['batch']['draft_count'] == 2

    action = client.post('/ai/v42/chat-action', json={'message': 'Ghi sổ các bút toán đã duyệt'})
    assert action.status_code == 200
    data = action.json()
    assert data['need_confirmation'] is True
    assert data['confirmation_id']

    confirmed = client.post('/ai/v42/confirm-action', json={'confirmation_id': data['confirmation_id'], 'confirm': True})
    assert confirmed.status_code == 200
    assert 'result' in confirmed.json()


def test_v41_chatbot_ui_available():
    res = client.get('/v41/chatbot-ui')
    assert res.status_code == 200
    assert 'Chatbot' in res.text
