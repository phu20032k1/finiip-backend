from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_v42_proposal_and_confirm_journal():
    r = client.post('/ai/v42/transaction-proposal', json={'message':'Thanh toán tiền điện 2 triệu bằng chuyển khoản'})
    assert r.status_code == 200
    data = r.json()
    assert data['version'] == 'V42'
    assert data['proposal']['amount'] == 2000000

    p = data['proposal']
    r2 = client.post('/ai/v42/confirm-journal', json={
        'description': p['description'],
        'amount': p['amount'],
        'category': p['category'],
        'debit_account': p['debit_account'],
        'credit_account': p['credit_account'],
        'payment_method': p['payment_method'],
        'vat_rate': 0.1,
        'risk_note': p['risk_note'],
        'post_immediately': False,
    })
    assert r2.status_code == 200
    saved = r2.json()
    assert saved['status'] == 'saved'
    assert saved['journal_draft']['balanced'] is True


def test_v47_feedback():
    r = client.post('/ai/v47/feedback', json={
        'user_message':'test',
        'ai_intent':'test_intent',
        'ai_prediction':{'a':1},
        'user_correction':'corrected',
        'final_result':{'ok':True},
        'rating':5,
    })
    assert r.status_code == 200
    assert r.json()['status'] == 'saved'
