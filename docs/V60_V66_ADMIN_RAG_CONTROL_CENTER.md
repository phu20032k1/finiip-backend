# Finiip V60–V66 Admin RAG Control Center

Bản nâng cấp này biến Admin RAG từ màn upload/search đơn giản thành trung tâm kiểm soát chất lượng cho AI kế toán.

## V60 — Evaluation/Test Center

Admin UI có khung **V60 Test Center** để chạy nhiều câu hỏi một lần.

Định dạng test case:

```txt
Thông tư 43/2026 sửa đổi thông tư nào? => Thông tư 202/2014/TT-BTC
BCTC hợp nhất năm nộp chậm nhất bao nhiêu ngày? => 90 ngày
Lợi ích cổ đông không kiểm soát mã số nào? | 429 | Điều 13
```

Kết quả trả về gồm:

- AI answer
- expected answer
- expected source
- score
- pass/fail
- citations retrieved

Nếu Supabase active và đã chạy schema mới, kết quả eval được lưu vào `admin_rag_eval_results`.

## V61 — Legal Citation Engine

Citation được nâng từ `trang/chunk` lên dạng tốt hơn:

```txt
Thông tư 43/2026/TT-BTC — Điều 6 — trang 1 — chunk 2
```

Hệ thống cố gắng nhận diện:

- Số văn bản
- Điều
- Khoản
- Điểm
- Phụ lục
- Mẫu số
- Mã số chỉ tiêu
- Trang/chunk

## V62 — Answer Mode

Admin UI có chế độ trả lời:

- Auto
- Ngắn gọn
- Chi tiết
- Kế toán trưởng
- Có ví dụ
- Có bút toán/checklist
- Rủi ro/kiểm soát
- Chỉ nguồn

Các mode dài sẽ ép RAG trả lời theo cấu trúc rõ hơn thay vì chỉ rút đoạn ngắn.

## V63 — Accounting Workflow Engine

Với câu hỏi nghiệp vụ, câu trả lời có thêm phần quy trình:

1. Xác định nghiệp vụ và phạm vi áp dụng
2. Kiểm tra kỳ kế toán/chứng từ/chính sách nội bộ
3. Đối chiếu chỉ tiêu hoặc bút toán bị ảnh hưởng
4. Lập bảng tổng hợp điều chỉnh/hồ sơ xử lý
5. Soát xét rủi ro
6. Người phụ trách duyệt trước khi ghi sổ/khóa sổ

## V64 — Document Intelligence

Khi upload/re-index, metadata tài liệu có thêm `document_intelligence`:

```json
{
  "document_type": "circular",
  "document_number": "43/2026/TT-BTC",
  "issue_date": "20/04/2026",
  "effective_date": "kể từ ngày ký ban hành",
  "modified_documents": ["Thông tư số 202/2014/TT-BTC"],
  "tags": ["accounting_law", "consolidated_financial_statements"]
}
```

UI detail tài liệu hiển thị panel Document Intelligence.

## V65 — Conflict Checker

Khi trong RAG có văn bản mới sửa đổi/thay thế văn bản cũ, câu trả lời sẽ cảnh báo:

```txt
Lưu ý xung đột/cập nhật: Thông tư 43/2026/TT-BTC có nội dung sửa đổi/bổ sung/thay thế Thông tư 202/2014/TT-BTC.
```

Tính năng này giúp tránh trả lời theo văn bản cũ khi đã có văn bản mới hơn trong kho RAG.

## V66 — Persistent Memory

Ngoài local memory trong tab trình duyệt, bản này có bảng `admin_rag_chat_messages` để lưu hội thoại admin nếu Supabase schema mới đã chạy.

Câu hỏi tiếp kiểu:

```txt
Câu trước áp dụng thế nào cho công ty mẹ?
```

sẽ có thêm lịch sử ngắn từ server memory.

## Cần chạy lại SQL schema

Mở endpoint:

```txt
/admin/rag-ui/api/supabase-schema?key=YOUR_ADMIN_KEY
```

Copy SQL và chạy trong Supabase SQL Editor để tạo thêm bảng:

- `admin_rag_eval_results`
- `admin_rag_chat_messages`

Các bảng cũ vẫn giữ nguyên.

## Sau khi cập nhật code

1. Restart backend
2. Ctrl + F5 trình duyệt
3. Chạy lại SQL schema nếu chưa có bảng V60/V66
4. Bấm Re-index tài liệu để tạo `document_intelligence`
5. Chạy V60 Test Center
