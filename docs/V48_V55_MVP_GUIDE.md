# Finiip V48-V55 MVP Guide

## Chạy backend
```bash
cd copy
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Giao diện demo
- V55 tổng hợp: `http://localhost:8000/v55/mvp-demo`
- V52 dashboard: `http://localhost:8000/v52/dashboard`

## API chính
### V48 Upload Excel giao dịch
```bash
curl -X POST http://localhost:8000/ai/v48/upload-transactions -F "file=@data/sample_transactions.xlsx"
```

### V48 review batch
```bash
curl "http://localhost:8000/ai/v48/transactions/review?batch_id=BATCH-..."
```

### V48 confirm batch
```bash
curl -X POST http://localhost:8000/ai/v48/transactions/confirm-batch \
  -H "Content-Type: application/json" \
  -d '{"batch_id":"BATCH-...","post_immediately":false}'
```

### V49 OCR hóa đơn/chứng từ
```bash
curl -X POST http://localhost:8000/ai/v49/ocr-invoice -F "file=@sample_invoice.txt"
```

### V50 RAG chat
```bash
curl -X POST http://localhost:8000/ai/v50/rag-chat \
  -H "Content-Type: application/json" \
  -d '{"query":"Tài khoản 641 dùng khi nào?","limit":5}'
```

### V51 hỏi báo cáo
```bash
curl -X POST http://localhost:8000/ai/v51/ask-report \
  -H "Content-Type: application/json" \
  -d '{"question":"VAT tháng này bao nhiêu?"}'
```

### V53 audit rủi ro
```bash
curl -X POST http://localhost:8000/ai/v53/audit-transactions \
  -H "Content-Type: application/json" \
  -d '{"include_drafts":true,"include_journal_entries":true}'
```

### V54 feedback -> rule suggestions
```bash
curl http://localhost:8000/ai/v54/rule-suggestions
```

## Ghi chú
V49 OCR ảnh phụ thuộc Tesseract trên máy chạy. Nếu chưa cài, hãy upload TXT/XML/PDF có text-layer để test trước.
