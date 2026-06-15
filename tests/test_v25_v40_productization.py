from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_v25_to_v40_status():
    res = client.get('/ai/v25-v40/upgrade-status')
    assert res.status_code == 200
    data = res.json()
    assert 'V25 Auto Journal Draft' in data['completed']
    assert 'V40 Backup / Restore' in data['completed']


def test_journal_draft_post_reports_and_backup():
    payload = {
        'description': 'Mua máy tính văn phòng 20 triệu có VAT',
        'amount': 20000000,
        'vat_rate': 0.1,
        'payment_method': 'bank'
    }
    draft_res = client.post('/ai/v25/journal-draft/create', json=payload)
    assert draft_res.status_code == 200
    draft = draft_res.json()
    assert draft['balanced'] is True
    draft_id = draft['id']

    approve_res = client.post(f'/ai/v25/journal-draft/{draft_id}/approve', json={'note': 'ok'})
    assert approve_res.status_code == 200
    assert approve_res.json()['status'] == 'approved'

    post_res = client.post('/ledger/post-entry', json={'draft_id': draft_id})
    assert post_res.status_code == 200
    entry = post_res.json()
    assert entry['debit_total'] == entry['credit_total']

    assert client.get('/ledger/general-journal').status_code == 200
    assert client.get('/ledger/general-ledger').status_code == 200
    assert client.get('/reports/vat').status_code == 200
    assert client.get('/reports/income-statement').status_code == 200
    assert client.get('/dashboard/v30/financial').status_code == 200
    assert client.get('/v30/financial-dashboard-ui').status_code == 200

    backup = client.post('/backup/v40/create')
    assert backup.status_code == 200
    assert backup.json()['backup_file'].endswith('.zip')


def test_ai_safety_user_auth_and_audit():
    lines = [
        {'account': '642', 'debit': 1000, 'credit': 0},
        {'account': '111', 'debit': 0, 'credit': 900},
    ]
    err = client.post('/ai/v32/detect-accounting-errors', json={'description': 'Chi phí', 'lines': lines})
    assert err.status_code == 200
    assert any(e['code'] == 'UNBALANCED' for e in err.json()['errors'])

    missing = client.post('/ai/v33/missing-info-questions', json={'description': 'Hóa đơn mua dịch vụ'})
    assert missing.status_code == 200
    assert missing.json()['need_more_info'] is True

    user_payload = {'name': 'Test Accountant', 'email': 'v25v40@example.com', 'role': 'accountant', 'password': 'secret'}
    user = client.post('/admin/v36/users', json=user_payload)
    assert user.status_code in (200, 400)  # okay if previous test run already created it
    login = client.post('/auth/v37/login', json={'email': 'v25v40@example.com', 'password': 'secret'})
    assert login.status_code == 200
    assert login.json().get('token')

    health = client.get('/system/v38/database-health')
    assert health.status_code == 200
    logs = client.get('/audit/v39/logs')
    assert logs.status_code == 200


def test_invoice_ocr_to_journal():
    text = 'CÔNG TY TNHH ABC\nMã số thuế: 0123456789\nSố: HD001\nNgày 01/05/2026\nTổng cộng: 1.100.000'
    ocr = client.post('/ocr/v34/invoice-enhanced/text', json={'text': text})
    assert ocr.status_code == 200
    assert ocr.json()['tax_code'] == '0123456789'
    mapped = client.post('/ai/v35/invoice-to-journal-draft', json={'text': text})
    assert mapped.status_code == 200
    assert mapped.json()['journal_draft']['balanced'] is True
