# Finiip AI - Hướng dẫn thêm kiến thức và cải thiện AI

## Bạn đang ở đâu?

Backend hiện ở mức **Cấp 3 nhẹ+**:

- Rule-based AI: nhận diện giao dịch theo keyword và luật kế toán.
- Learning memory: AI học từ các lần người dùng sửa kết quả.
- Manual teaching: có thể dạy AI trực tiếp bằng API, không cần frontend.
- Knowledge pack: đã thêm nhiều nghiệp vụ kế toán SME/e-commerce.

## Nâng cấp đã thêm

### 1. Thêm gói kiến thức kế toán mới

Đã thêm các nhóm nghiệp vụ:

- Khấu hao tài sản cố định
- Công cụ dụng cụ / phân bổ CCDC
- Chi phí trả trước
- Lãi vay ngân hàng
- Nộp thuế GTGT, TNDN
- BHXH, BHYT, BHTN
- Giá vốn hàng bán
- Phí sàn Shopee / TikTok Shop / Lazada
- Đối soát sàn TMĐT thu hộ
- Hoàn tiền / hoàn hàng sàn TMĐT
- Phí COD / vận chuyển thu hộ
- Thu hộ / chi hộ
- Thu công nợ khách hàng
- Trả công nợ nhà cung cấp

### 2. Thêm API dạy AI trực tiếp

Dùng khi AI phân loại sai hoặc bạn muốn thêm ví dụ mới.

```http
POST /ai/teach
```

Ví dụ body:

```json
{
  "description": "Chi phí chạy Zalo Ads tháng 6",
  "amount": 4200000,
  "user_category": "Chi phí marketing",
  "user_type": "expense",
  "user_debit_account_code": "641",
  "user_credit_account_code": "112",
  "note": "Dạy AI nhận diện Zalo Ads là chi phí marketing"
}
```

Sau đó test lại:

```http
POST /ai/analyze-with-learning
```

```json
{
  "description": "Thanh toán Zalo Ads tháng 7 qua ngân hàng",
  "amount": 5000000
}
```

Nếu AI học đúng, kết quả sẽ có:

```json
"source": "learning_memory"
```

### 3. Thêm API dạy nhiều ví dụ một lúc

```http
POST /ai/teach-batch
```

Body:

```json
{
  "items": [
    {
      "description": "Phí sàn Shopee tháng 5",
      "amount": 850000,
      "user_category": "Chi phí sàn thương mại điện tử",
      "user_type": "expense",
      "user_debit_account_code": "641",
      "user_credit_account_code": "112"
    },
    {
      "description": "Đối soát TikTok Shop sàn thu hộ",
      "amount": 15000000,
      "user_category": "Sàn TMĐT thu hộ khách hàng",
      "user_type": "income",
      "user_debit_account_code": "112",
      "user_credit_account_code": "131"
    }
  ]
}
```

### 4. Thêm API kiểm tra sức khỏe kiến thức AI

```http
GET /ai/knowledge-health
```

API này cho biết:

- AI có bao nhiêu rule.
- Đã học bao nhiêu ví dụ correction.
- Có bao nhiêu giao dịch confidence thấp.
- Có bao nhiêu giao dịch chưa phân loại.
- Nên dạy thêm phần nào.

## Luồng cải thiện AI nên dùng hằng ngày

1. Gọi `/ai/analyze-with-learning` để AI phân tích giao dịch.
2. Nếu đúng, có thể tạo/confirm giao dịch.
3. Nếu sai, gọi `/ai/teach` hoặc `/ai/transactions/{id}/correct`.
4. Sau khi có nhiều correction cùng loại, gọi `/ai/rule-suggestions`.
5. Chuyển rule lặp lại vào `ai_engine.py` để thành kiến thức cố định.
6. Gọi `/ai/knowledge-health` để xem AI còn yếu phần nào.

## Test nhanh bằng Python

```bash
python - <<'PY'
import ai_engine
cases = [
    ("Nộp thuế GTGT quý 2 qua ngân hàng", 12000000),
    ("Phí sàn Shopee tháng 5", 850000),
    ("Trích khấu hao tài sản cố định tháng 5", 3000000),
    ("Đối soát TikTok Shop sàn thu hộ", 15000000),
]
for description, amount in cases:
    r = ai_engine.suggest_journal_entry(description, amount)
    print(description, "=>", r["category"], r["debit_account_code"], r["credit_account_code"], r["confidence"])
PY
```

## Lưu ý quan trọng

AI hiện vẫn chưa phải ChatGPT kế toán thật. Nó là **Cấp 3 nhẹ+**, tức là rule-based + học từ correction. Muốn lên Cấp 6 giống ChatGPT chuyên kế toán, sau này cần thêm:

- RAG / vector database
- Tài liệu kế toán làm knowledge base
- Chat endpoint đọc dữ liệu database
- Agent phân tích báo cáo
- Kiểm soát quyền truy cập và bảo mật
