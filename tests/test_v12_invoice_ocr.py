import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


SAMPLE_INVOICE = '''
HÓA ĐƠN GIÁ TRỊ GIA TĂNG
Số hóa đơn: HD001234
Ngày 15/05/2026
Đơn vị bán hàng: Công ty Điện lực EVN Hà Nội
Mã số thuế: 0100100417
Đơn vị mua hàng: Công ty Finiip
Cộng tiền hàng: 2.000.000
Thuế suất GTGT: 10%
Tiền thuế GTGT: 200.000
Tổng cộng thanh toán: 2.200.000
'''


def test_v12_invoice_ocr_from_text_and_create_records():
    client.post('/setup/default-accounts')
    response = client.post('/ocr/invoice/text', json={
        'raw_text': SAMPLE_INVOICE,
        'create_purchase_invoice': True,
        'create_transaction': True,
        'auto_create_journal': False,
    })
    assert response.status_code == 200
    body = response.json()
    extracted = body['extracted']
    assert extracted['invoice_number'] == 'HD001234'
    assert extracted['invoice_date'] == '2026-05-15'
    assert extracted['supplier_name'] == 'Công ty Điện lực EVN Hà Nội'
    assert extracted['subtotal'] == 2000000
    assert extracted['vat_rate'] == 10
    assert extracted['vat_amount'] == 200000
    assert extracted['total_amount'] == 2200000
    assert body['ai_suggestion']['ai_result'] is not None
    assert body['created_purchase_invoice']['invoice_number'] == 'HD001234'
    assert body['created_transaction']['amount'] == 2200000


def test_v12_invoice_ocr_upload_txt():
    client.post('/setup/default-accounts')
    response = client.post(
        '/ocr/invoice/upload',
        files={'file': ('invoice.txt', SAMPLE_INVOICE.encode('utf-8'), 'text/plain')},
    )
    assert response.status_code == 200
    body = response.json()
    assert body['source']['method'].startswith('text_decode')
    assert body['extracted']['invoice_number'] == 'HD001234'
    assert body['extracted']['total_amount'] == 2200000
