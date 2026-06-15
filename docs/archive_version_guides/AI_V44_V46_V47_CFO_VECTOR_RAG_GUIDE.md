# Finiip V44 + V46 + V47 Guide

Bản này nâng Finiip sau V43 lên 3 phần lớn:

- V44: AI CFO mini
- V46: Vector RAG thật hơn bằng local TF-cosine vector search
- V47: Upload tài liệu kế toán nhiều định dạng và tự chunk/index

## 1. Chạy dự án

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Mở Swagger:

```text
http://127.0.0.1:8000/docs
```

## 2. Kiểm tra trạng thái

```text
GET /ai/v44-v47/upgrade-status
GET /rag/v46/status
```

## 3. V44 — AI CFO mini

### Tóm tắt tài chính

```text
GET /ai/v44/cfo/summary
```

Trả về doanh thu, chi phí, lợi nhuận, biên lợi nhuận, VAT phải nộp, ước tính tiền/ngân hàng, phải thu, phải trả, cảnh báo rủi ro và khuyến nghị.

### Tính kịch bản

```text
POST /ai/v44/cfo/scenario
```

Body mẫu:

```json
{
  "revenue_change_percent": 20,
  "expense_change_percent": 0,
  "extra_revenue": 0,
  "extra_expense": 0,
  "note": "Nếu doanh thu tăng 20%"
}
```

### Dự báo dòng tiền MVP

```text
GET /ai/v44/cfo/cashflow-forecast
```

### Cảnh báo rủi ro

```text
GET /ai/v44/cfo/risk-alerts
```

### Hỏi CFO bằng tiếng Việt

```text
POST /ai/v44/cfo/ask
```

Body mẫu:

```json
{
  "question": "Nếu doanh thu tăng 20% thì lợi nhuận thế nào?"
}
```

Các câu có thể hỏi:

```text
Tháng này tình hình tài chính thế nào?
Nếu doanh thu tăng 20% thì lợi nhuận ra sao?
Có rủi ro tài chính nào không?
Dự báo dòng tiền 30 ngày tới thế nào?
```

## 4. V47 — Upload tài liệu kế toán nhiều định dạng

Upload text trực tiếp:

```text
POST /rag/v47/documents/upload-text
```

Body mẫu:

```json
{
  "title": "Quy trình chi phí quảng cáo",
  "content": "Chi phí quảng cáo Facebook phục vụ bán hàng thường hạch toán vào tài khoản 641...",
  "source": "internal_policy",
  "tags": ["marketing", "tax"],
  "auto_chunk": true
}
```

Upload file:

```text
POST /rag/v47/documents/upload-file
```

Hỗ trợ MVP:

```text
txt, md, csv, json, docx, xlsx, pdf có text-layer
```

Lưu ý: PDF scan ảnh chưa OCR trong V47; cần OCR riêng nếu file là ảnh scan.

Xem tài liệu đã upload:

```text
GET /rag/v47/documents
```

## 5. V46 — Vector RAG

Search bằng vector local:

```text
POST /rag/v46/search
```

Body mẫu:

```json
{
  "query": "chi phí quảng cáo Facebook hạch toán tài khoản nào",
  "limit": 5,
  "min_score": 0
}
```

Hỏi chatbot với tài liệu vector:

```text
POST /ai/v47/chat-with-vector-docs
```

Body mẫu:

```json
{
  "question": "Chi phí quảng cáo Facebook hạch toán tài khoản nào?",
  "limit": 5,
  "save_learning": true
}
```

## 6. Quy trình test nhanh

1. Tạo dữ liệu mẫu:

```text
POST /import/v40-5/sample-data?auto_post=true
```

2. Test CFO:

```text
GET /ai/v44/cfo/summary
POST /ai/v44/cfo/ask
```

3. Upload tài liệu:

```text
POST /rag/v47/documents/upload-text
```

4. Search tài liệu:

```text
POST /rag/v46/search
```

5. Hỏi tài liệu:

```text
POST /ai/v47/chat-with-vector-docs
```

## 7. Kiểm thử tự động

```bash
PYTHONPATH=. pytest -q
```

Kết quả hiện tại:

```text
45 passed
```

## 8. Mức độ hiện tại

V46 hiện là vector RAG local MVP, không dùng OpenAI/LLM API bên ngoài. Nó tốt hơn keyword search V43 vì có chunking, vector term-frequency, cosine score và matched terms. Sau này có thể nâng tiếp lên Chroma, FAISS hoặc Qdrant.
