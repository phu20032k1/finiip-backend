import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai_v5_v9 import save_feedback_event, apply_learning, add_knowledge_doc, search_knowledge, anomaly_score

print('V5 feedback learning')
e = save_feedback_event('Thanh toán AWS hosting bằng chuyển khoản', 3000000, {}, {'category':'Chi phí dịch vụ mua ngoài','debit_account':'642','credit_account':'112'}, 'test')
print(e['id'])
print(apply_learning('Trả tiền AWS cloud hosting tháng 6', {'confidence':0.7}))

print('\nV7 knowledge')
doc = add_knowledge_doc('Chi phí marketing', 'Quảng cáo Facebook phục vụ bán hàng thường hạch toán Nợ 641, Có 111/112. Nếu có VAT hợp lệ ghi nhận 1331.', 'manual', ['641','vat'])
print(search_knowledge('Facebook hạch toán vào đâu?'))

print('\nV8 anomaly')
print(anomaly_score([
 {'description':'Thu tiền bán hàng','amount':12000000},
 {'description':'Rút tiền mặt chi dịch vụ tư vấn','amount':80000000},
 {'description':'Thu tiền bán hàng','amount':12000000},
]))
