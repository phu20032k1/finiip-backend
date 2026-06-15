# Finiip V43 / V43.5 / V45 MVP

Bản nâng cấp này thêm lớp kiến thức kế toán cho chatbot:

- V43: hỏi công thức, hỏi tài khoản, hỏi tài liệu/luật/quy trình bằng RAG MVP
- V43.5: giải câu hỏi dài/bài tập kế toán từng bước
- V45 MVP: lưu Q&A learning memory từ câu hỏi, đáp án và tài liệu đã dùng

## 1. Kiểm tra trạng thái

```bash
GET /ai/v43/status
```

## 2. Hỏi công thức và tài khoản kế toán

```bash
POST /ai/v43/accounting-qa
```

Body:

```json
{
  "question": "Công thức tính VAT phải nộp là gì?"
}
```

Ví dụ khác:

```json
{
  "question": "Tài khoản 642 là gì?"
}
```

## 3. Upload tài liệu cho RAG

```bash
POST /rag/v43/documents/upload
```

Body:

```json
{
  "title": "Quy định nội bộ chi phí quảng cáo",
  "content": "Chi phí quảng cáo Facebook phục vụ bán hàng được hạch toán vào tài khoản 641 nếu có hóa đơn chứng từ hợp lệ.",
  "source": "manual",
  "tags": ["chi phí", "quảng cáo"]
}
```

Sau đó hỏi:

```json
{
  "question": "Chi phí quảng cáo Facebook hạch toán tài khoản nào?"
}
```

API liên quan:

```bash
GET  /rag/v43/documents
POST /rag/v43/search
POST /ai/v43/chat-with-docs
```

Lưu ý: bản MVP upload-file ưu tiên `.txt`, `.md`, `.csv`. PDF/DOCX cần parser nâng cao ở các bản sau.

## 4. Giải bài tập/câu hỏi dài

```bash
POST /ai/v43-5/problem-solver
```

Body mẫu:

```json
{
  "question": "Công ty mua hàng hóa 100 triệu, VAT 10%, chưa thanh toán. Sau đó bán một nửa số hàng với giá 80 triệu, VAT 10%, khách hàng chưa trả tiền. Hãy định khoản, tính VAT phải nộp và lợi nhuận.",
  "standard": "TT200",
  "mode": "step_by_step"
}
```

Kết quả trả về gồm:

- các nghiệp vụ đã tách
- định khoản từng bước
- tính VAT đầu vào, VAT đầu ra, VAT phải nộp
- tính giá vốn/lợi nhuận gộp nếu có đủ dữ liệu
- kiểm tra tổng Nợ = tổng Có
- giả định/cảnh báo nếu đề thiếu dữ liệu

## 5. Kiểm tra đáp án người dùng

```bash
POST /ai/v43-5/check-answer
```

Body mẫu:

```json
{
  "question": "Công ty mua hàng hóa 100 triệu, VAT 10%, chưa thanh toán. Sau đó bán một nửa số hàng với giá 80 triệu, VAT 10%, khách hàng chưa trả tiền. Hãy định khoản, tính VAT phải nộp và lợi nhuận.",
  "user_answer": "Nợ 156, Nợ 1331, Có 331; Nợ 131, Có 511, Có 3331; Nợ 632, Có 156"
}
```

## 6. Xem bộ nhớ học từ Q&A

```bash
GET /ai/v45/qa-learning/memory
```

Bộ nhớ này lưu câu hỏi, loại ý định, preview đáp án và nguồn tài liệu đã dùng. Đây là nền móng để sau này train lại classifier hoặc gợi ý rule mới.

## 7. Test

```bash
pytest -q
```

Kết quả hiện tại:

```text
42 passed
```
