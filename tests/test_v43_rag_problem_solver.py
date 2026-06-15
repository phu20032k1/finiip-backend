from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_v43_formula_account_and_rag_qa():
    status = client.get('/ai/v43/status')
    assert status.status_code == 200
    assert 'V43' in status.json()['version']

    formula = client.post('/ai/v43/accounting-qa', json={'question': 'Công thức tính VAT phải nộp là gì?'})
    assert formula.status_code == 200
    assert formula.json()['intent'] == 'formula'
    assert 'VAT phải nộp' in formula.json()['answer']

    account = client.post('/ai/v43/accounting-qa', json={'question': 'Tài khoản 642 là gì?'})
    assert account.status_code == 200
    assert account.json()['intent'] == 'account_lookup'
    assert '642' in account.json()['answer']

    upload = client.post('/rag/v43/documents/upload', json={
        'title': 'Quy định nội bộ chi phí quảng cáo',
        'content': 'Chi phí quảng cáo Facebook phục vụ bán hàng được hạch toán vào tài khoản 641 nếu có hóa đơn chứng từ hợp lệ và phục vụ hoạt động kinh doanh.',
        'source': 'pytest_manual',
        'tags': ['chi phí', 'quảng cáo']
    })
    assert upload.status_code == 200

    qa = client.post('/ai/v43/accounting-qa', json={'question': 'Chi phí quảng cáo Facebook hạch toán tài khoản nào?'})
    assert qa.status_code == 200
    assert qa.json()['intent'] in {'rag_accounting_qa', 'account_lookup'}
    assert '641' in qa.json()['answer'] or qa.json()['sources']


def test_v435_problem_solver_and_check_answer_learning():
    question = 'Công ty mua hàng hóa 100 triệu, VAT 10%, chưa thanh toán. Sau đó bán một nửa số hàng với giá 80 triệu, VAT 10%, khách hàng chưa trả tiền. Hãy định khoản, tính VAT phải nộp và lợi nhuận.'
    solved = client.post('/ai/v43-5/problem-solver', json={'question': question, 'standard': 'TT200'})
    assert solved.status_code == 200
    data = solved.json()
    assert data['check']['balanced'] is True
    assert data['calculations']['vat_payable'] == -2000000
    assert data['calculations']['gross_profit'] == 30000000
    assert 'Nợ 156' in data['answer']

    checked = client.post('/ai/v43-5/check-answer', json={'question': question, 'user_answer': 'Nợ 156, Nợ 1331, Có 331; Nợ 131, Có 511, Có 3331; Nợ 632, Có 156'})
    assert checked.status_code == 200
    assert checked.json()['score'] >= 80

    memory = client.get('/ai/v45/qa-learning/memory')
    assert memory.status_code == 200
    assert memory.json()['count'] >= 1
