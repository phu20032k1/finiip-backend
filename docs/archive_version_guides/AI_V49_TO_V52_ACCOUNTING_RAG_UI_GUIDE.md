# Finiip V49-V52 - AI kế toán RAG UI

## Đã làm trong bản này

- **V49**: thêm giao diện `/v49/accounting-ai-ui` để upload tài liệu kế toán.
- **V50**: thêm chatbot kế toán gọi API `/ai/v47/chat-with-vector-docs`.
- **V51**: chuẩn hóa câu trả lời AI thành: kết luận ngắn, căn cứ tìm thấy, việc cần kiểm tra thêm.
- **V52**: thêm guard an toàn: nếu kho tài liệu chưa có nguồn phù hợp, AI nói chưa đủ căn cứ thay vì bịa luật/thông tư/tài khoản.

## Cách chạy

```bash
cd copy
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

Mở trình duyệt:

```text
http://127.0.0.1:8000/v49/accounting-ai-ui
```

## Luồng test nhanh

1. Mở `/v49/accounting-ai-ui`.
2. Upload file PDF/DOCX/XLSX/TXT/CSV/JSON có nội dung kế toán, thuế, thông tư hoặc quy trình nội bộ.
3. Hỏi ví dụ:

```text
Mua laptop 18 triệu có hóa đơn VAT, thanh toán chuyển khoản, hạch toán tài khoản nào và cần kiểm tra gì?
```

4. Xem câu trả lời gồm:

- độ tin cậy: high / medium / low;
- kết luận ngắn;
- căn cứ tìm thấy từ tài liệu upload;
- thông tin còn thiếu cần kiểm tra;
- nguồn snippets.

## API mới/đã nâng cấp

```text
GET  /v49/accounting-ai-ui
GET  /ai/v49-v52/upgrade-status
POST /ai/v47/chat-with-vector-docs
```

`POST /ai/v47/chat-with-vector-docs` vẫn giữ path cũ để không phá frontend/API cũ, nhưng response đã được nâng lên format V49-V52.

## Lưu ý quan trọng

Bản này vẫn là RAG local MVP dùng TF-cosine. Nó phù hợp để demo và test quy trình. Khi làm sản phẩm thật nên nâng vector database sang Chroma, FAISS hoặc Qdrant và thêm OCR cho PDF scan ảnh.
