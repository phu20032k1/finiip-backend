# Finiip Backend API Contract cho Frontend riêng

## Base URL local

```text
http://127.0.0.1:8000
```

## Luồng frontend khuyến nghị

### Màn hình 1: Dashboard khởi động

Gọi:

```http
GET /api/v1/health
GET /api/v1/frontend/bootstrap
```

Dùng để lấy trạng thái backend, tài khoản, dashboard summary, thông tin AI.

---

### Màn hình 2: AI phân tích giao dịch

Gọi:

```http
POST /ai/v3/analyze
```

Body:

```json
{
  "description": "Thanh toán tiền điện EVN 2300000 bằng tiền mặt",
  "amount": 2300000,
  "payment_method": "cash",
  "tax_rate": 0.1
}
```

Frontend nên hiển thị:

- Category
- Debit account
- Credit account
- Confidence
- Calibrated confidence
- Explanations
- Risk flags
- Quality gate decision
- Review questions

---

### Màn hình 3: Review Queue

Tạo item cần duyệt:

```http
POST /ai/v19/review-queue/from-analyze
```

Lấy danh sách:

```http
GET /ai/v19/review-queue
```

Duyệt / sửa / từ chối:

```http
POST /ai/v19/review-queue/{item_id}/decision
```

Frontend nên có 3 nút:

```text
Approve
Correct
Reject
```

---

### Màn hình 4: OCR hóa đơn

Preview OCR:

```http
POST /api/v1/frontend/invoice-preview
```

Không tự ghi sổ. Sau OCR, frontend đưa dữ liệu sang màn hình review.

---

### Màn hình 5: AI Quality Dashboard

Gọi:

```http
GET /ai/v24/quality-dashboard
```

Hiển thị:

- Tổng review items
- Pending
- Approved
- Corrected
- Rejected
- Avg confidence
- Quality score
- Recommendations

---

## Quy tắc an toàn frontend nên tuân thủ

```text
Nếu quality_gate.decision = AUTO_DRAFT_ALLOWED
→ Cho phép tạo draft nhưng vẫn nên hiển thị cho người dùng xem.

Nếu quality_gate.decision = REVIEW_REQUIRED
→ Bắt buộc đưa vào review queue.

Nếu quality_gate.decision = BLOCK_AUTO_POSTING
→ Không cho tạo bút toán tự động; yêu cầu kế toán nhập/sửa lại.
```

## Header khi deploy có API key

```http
X-API-Key: your-secret-key
```

---

## V68–V72 File Reader & Report API

Dành cho frontend khi người dùng upload tài liệu để Finiip đọc và trả báo cáo.

- Capabilities: `GET /ai/v68/file-report/capabilities`
- File nhỏ / trả ngay: `POST /ai/v68/file-report/create-sync`
- File lớn / async: `POST /ai/v69/file-report/jobs`
- Poll job: `GET /ai/v69/file-report/jobs/{job_id}`
- Tải kết quả: `GET /ai/v69/file-report/jobs/{job_id}/download`
- Lịch sử: `GET /ai/v70/file-report/history`
- Xóa lịch sử: `DELETE /ai/v70/file-report/history/{job_id}`

Output hỗ trợ: `docx`, `xlsx`, `pdf`, `md`, `txt`, `json`, `csv`.
Multi-file: append nhiều field `files` trong `FormData`.

Xem chi tiết: `docs/V68_V72_FRONTEND_FILE_REPORT_API.md`.
