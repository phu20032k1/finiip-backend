from datetime import date
from io import BytesIO
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from openpyxl import Workbook

import main

client = TestClient(main.app)


def test_system_status():
    response = client.get('/system/status')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_setup_accounts():
    response = client.post('/setup/default-accounts')
    assert response.status_code == 200
    data = response.json()
    assert 'created' in data


def test_ai_create_validate_confirm():
    client.post('/setup/default-accounts')
    response = client.post('/ai/create-transaction', json={
        'description': 'Thanh toán tiền điện EVN tháng 5 bằng chuyển khoản',
        'amount': 2500000,
        'auto_create_journal': True,
    })
    assert response.status_code == 200
    tx_id = response.json()['transaction']['id']

    validation = client.get(f'/transactions/{tx_id}/validation')
    assert validation.status_code == 200
    assert validation.json()['journal_balance']['balanced'] is True

    confirmed = client.post(f'/transactions/{tx_id}/confirm')
    assert confirmed.status_code == 200
    assert confirmed.json()['status'] == 'confirmed'


def test_demo_reports_and_trial_balance():
    response = client.post('/demo/seed-full?reset=true')
    assert response.status_code == 200

    pl = client.get('/reports/profit-loss')
    assert pl.status_code == 200
    assert 'profit' in pl.json()

    trial_balance = client.get('/reports/trial-balance')
    assert trial_balance.status_code == 200
    assert trial_balance.json()['balanced'] is True


def test_import_excel_preview():
    wb = Workbook()
    ws = wb.active
    ws.append(['transaction_date', 'description', 'amount', 'note'])
    ws.append([date.today().isoformat(), 'Chi phí quảng cáo Facebook Ads có VAT 10%', 5500000, 'test import'])
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = client.post(
        '/import/transactions/excel?preview=true',
        files={'file': ('transactions.xlsx', buffer.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'preview'
    assert len(response.json()['items']) == 1
