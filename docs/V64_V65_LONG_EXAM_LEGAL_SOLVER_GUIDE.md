# V64/V65 - Long Exam Legal Solver

Mục tiêu: cho AI xử lý câu hỏi dài kiểu đề thi, có cả tính toán kế toán và câu hỏi liên quan thông tư/nghị định.

## Endpoint chính

```http
POST /ai/v64/long-exam-legal-solver
```

Payload mẫu:

```json
{
  "question": "Công ty mua hàng hóa 100 triệu, VAT 10%, chưa thanh toán. Sau đó bán một nửa với giá 80 triệu, VAT 10%, khách chưa trả tiền. Hãy định khoản, tính VAT phải nộp và lợi nhuận. Theo thông tư hiện hành chi phí này có được ghi nhận không?",
  "standard": "TT200",
  "use_rag": true,
  "require_sources": true,
  "save_learning": false
}
```

## Endpoint kiểm tra trạng thái

```http
GET /ai/v64/long-exam-legal-solver/status
```

## Cách AI xử lý

1. Nhận diện câu hỏi dài, câu hỏi tính toán, định khoản, và yếu tố thông tư/nghị định.
2. Tách đề thành từng ý nhỏ.
3. Với phần tính toán, AI giải theo toàn đề để không mất dữ kiện giữa các câu.
4. Với phần pháp lý, AI tra RAG local và trả `sources`, `confidence`, `missing_info`.
5. Trả lời theo cấu trúc:
   - Tóm tắt đề
   - Dữ kiện đã phát hiện
   - Tách yêu cầu và cách xử lý
   - Căn cứ thông tư/nghị định / nguồn RAG
   - Kết luận và cảnh báo

## Dạng đã hỗ trợ

- Câu hỏi dài nhiều ý.
- Định khoản mua hàng, bán hàng, VAT đầu vào/đầu ra.
- Tính VAT phải nộp.
- Tính lợi nhuận gộp.
- Khấu hao đường thẳng theo tháng.
- Phân bổ CCDC/chi phí trả trước theo tháng.
- Đơn giá bình quân xuất kho mức cơ bản.
- Câu hỏi thông tư/nghị định dựa trên kho RAG local.

## Giới hạn hiện tại

- Chưa thay thế kế toán hoặc luật sư.
- Nếu chưa upload văn bản gốc, câu hỏi pháp lý sẽ trả `low confidence`.
- FIFO, thuế TNDN nhiều điều kiện, bảng dữ liệu phức tạp cần solver riêng.
- Với câu hỏi pháp lý, frontend nên hiển thị nguồn trước khi hiển thị kết luận.

## Gợi ý frontend

Gọi endpoint chính và hiển thị các trường:

- `answer`: nội dung đã format sẵn.
- `sub_questions`: từng ý nhỏ AI đã tách.
- `sources`: nguồn RAG.
- `confidence`: mức tin cậy.
- `missing_info`: thông tin còn thiếu.
