from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_v44_cfo_summary_scenario_and_ask():
    seed = client.post('/import/v40-5/sample-data?auto_post=true')
    assert seed.status_code == 200

    summary = client.get('/ai/v44/cfo/summary')
    assert summary.status_code == 200
    body = summary.json()
    assert body['version'] == 'V44'
    assert 'metrics' in body
    assert body['metrics']['journal_entries'] >= 1

    scenario = client.post('/ai/v44/cfo/scenario', json={'revenue_change_percent': 20, 'expense_change_percent': 0})
    assert scenario.status_code == 200
    data = scenario.json()
    assert data['result']['revenue'] >= data['base_metrics']['revenue']
    assert 'Lợi nhuận dự kiến' in data['explanation']

    ask = client.post('/ai/v44/cfo/ask', json={'question': 'Nếu doanh thu tăng 20% thì lợi nhuận thế nào?'})
    assert ask.status_code == 200
    assert ask.json()['intent'] == 'scenario'


def test_v46_v47_vector_rag_text_upload_and_chat():
    status = client.get('/rag/v46/status')
    assert status.status_code == 200

    upload = client.post('/rag/v47/documents/upload-text', json={
        'title': 'Quy trình chi phí quảng cáo',
        'content': 'Chi phí quảng cáo Facebook phục vụ bán hàng thường hạch toán vào tài khoản 641. Cần có hóa đơn hợp lệ và chứng từ thanh toán.',
        'source': 'internal_policy',
        'tags': ['marketing', 'tax'],
    })
    assert upload.status_code == 200
    assert upload.json()['document']['chunk_count'] >= 1

    search = client.post('/rag/v46/search', json={'query': 'quảng cáo Facebook hạch toán tài khoản nào', 'limit': 3})
    assert search.status_code == 200
    results = search.json()['results']
    assert results
    assert results[0]['score'] > 0

    chat = client.post('/ai/v47/chat-with-vector-docs', json={'question': 'Chi phí quảng cáo Facebook hạch toán tài khoản nào?'})
    assert chat.status_code == 200
    assert chat.json()['intent'] == 'vector_rag_qa'
    assert chat.json()['sources']


def test_v47_upload_file_csv():
    csv_bytes = b'title,content\nVAT,VAT phai nop = VAT dau ra - VAT dau vao\n'
    res = client.post(
        '/rag/v47/documents/upload-file',
        files={'file': ('vat_policy.csv', csv_bytes, 'text/csv')},
        data={'source': 'csv_test', 'tags': 'vat,formula'},
    )
    assert res.status_code == 200
    assert res.json()['document']['file_type'] == 'csv'

    docs = client.get('/rag/v47/documents')
    assert docs.status_code == 200
    assert docs.json()['count'] >= 1

    upgrade = client.get('/ai/v44-v47/upgrade-status')
    assert upgrade.status_code == 200
    assert upgrade.json()['counts']['v46_chunks'] >= 1
