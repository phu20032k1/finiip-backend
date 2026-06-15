# Finiip V23 - Frontend AI Review Queue

## Mục tiêu

V23 biến phần V19 AI Review Queue thành một màn hình dùng thử được trong trình duyệt. Kế toán có thể xem kết quả AI, duyệt, sửa, từ chối và lưu feedback để V20 retrain model.

## Cách chạy

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Mở trình duyệt:

```text
http://127.0.0.1:8000/v23/review-queue-ui
```

Hoặc API health:

```text
http://127.0.0.1:8000/ai/v23/review-ui/status
```

## Luồng sử dụng

1. Nhập mô tả giao dịch và số tiền ở ô đầu trang.
2. Bấm **Đưa vào queue** để AI phân tích và tạo item chờ duyệt.
3. Với từng item, kế toán chọn:
   - **Approve**: chấp nhận kết quả AI.
   - **Approve + tạo nháp**: chấp nhận và tạo journal entry trạng thái `draft`.
   - **Correct**: sửa category, type, TK Nợ, TK Có rồi lưu feedback.
   - **Reject**: từ chối kết quả AI.
4. Sau khi có nhiều correction, bấm **Retrain từ feedback**.

## Các API dùng trong V23

- `GET /v23/review-queue-ui`
- `GET /ai/v23/review-ui/status`
- `GET /ai/v19/review-queue?status=pending&limit=100`
- `POST /ai/v19/review-queue/from-analyze`
- `POST /ai/v19/review-queue/{id}/decision`
- `POST /ai/v20/retrain-from-feedback`
- `GET /ai/v18-v22/upgrade-status`

## Vị trí file

- Giao diện: `frontend/v23_review_queue.html`
- Route backend: `main.py`

## Ghi chú an toàn

V23 vẫn giữ nguyên nguyên tắc an toàn: AI không tự posted bút toán thật. Khi tạo journal entry từ UI, hệ thống chỉ tạo trạng thái `draft` để kế toán kiểm tra trước.
