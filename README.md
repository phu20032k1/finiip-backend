# Finiip AI Accounting Backend API

Bản này là **backend-only**. Frontend được tách sang project riêng và gọi API qua HTTP.

## Mục tiêu

Finiip backend cung cấp API kế toán + AI kế toán:

- AI phân loại giao dịch kế toán
- AI gợi ý bút toán Nợ/Có
- AI V3 giải thích lý do phân loại
- Confidence calibration
- Risk flags / quality gate
- Review queue để kế toán duyệt AI
- OCR hóa đơn dạng preview
- Báo cáo doanh thu, chi phí, lợi nhuận, VAT
- Import / export Excel
- API contract cho frontend riêng

AI không tự ghi sổ chính thức. Luồng đúng là:

```text
Frontend nhập giao dịch
→ Backend AI phân tích
→ Backend trả gợi ý + confidence + risk flags
→ Frontend cho kế toán duyệt
→ Backend lưu draft / approved / posted theo API
```

## Cách chạy local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Trên macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Mở API docs:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
GET http://127.0.0.1:8000/api/v1/health
```

## Endpoint quan trọng cho frontend

### 1. Kiểm tra backend

```http
GET /api/v1/health
GET /system/status
GET /api/v1/frontend/contract
GET /api/v1/frontend/routes
GET /api/v1/frontend/bootstrap
```

### 2. AI V3 phân tích giao dịch

```http
POST /ai/v3/analyze
POST /ai/v3/batch-analyze
GET  /ai/v3/demo-cases
GET  /ai/v3/test-suite
```

Body mẫu:

```json
{
  "description": "Thanh toán quảng cáo Facebook 5000000 bằng tiền mặt",
  "amount": 5000000,
  "payment_method": "cash",
  "tax_rate": 0.1
}
```

Kết quả frontend nên đọc các field chính:

```json
{
  "category": "...",
  "debit_account_code": "...",
  "credit_account_code": "...",
  "confidence": 0.9,
  "calibrated_confidence": 0.82,
  "explanations": [],
  "risk_flags": [],
  "quality_gate": {
    "decision": "REVIEW_REQUIRED"
  },
  "review_questions": []
}
```

### 3. Review queue

```http
POST /ai/v19/review-queue/from-analyze
GET  /ai/v19/review-queue
POST /ai/v19/review-queue/{item_id}/decision
```

Frontend nên dùng luồng:

```text
POST /ai/v3/analyze
→ nếu quality_gate = REVIEW_REQUIRED hoặc BLOCK_AUTO_POSTING
→ POST /ai/v19/review-queue/from-analyze
→ GET /ai/v19/review-queue
→ POST /ai/v19/review-queue/{item_id}/decision
```

### 4. OCR hóa đơn

```http
POST /ai/v12/ocr-invoice-text
POST /api/v1/frontend/invoice-preview
```

OCR nên để preview trước, không tự ghi sổ.

### 5. Báo cáo / dashboard

```http
GET /api/v1/frontend/bootstrap
GET /ai/v24/quality-dashboard
```

### 6. Import / export Excel

Xem chi tiết ở `/docs`, tìm keyword:

```text
excel
import
export
```

## CORS

Backend hiện bật CORS rộng để frontend riêng gọi được:

```python
allow_origins=["*"]
```

Khi deploy thật, nên đổi thành domain frontend thật, ví dụ:

```python
allow_origins=["https://app.finiip.vn"]
```

## API key khi deploy thật

Có thể bật API key bằng biến môi trường:

```bash
FINIIP_API_KEY=your-secret-key
```

Khi bật, frontend cần gửi header:

```http
X-API-Key: your-secret-key
```

## Test AI V3 offline

```bash
python scripts/test_ai_v3_offline.py
```

## Test API nhanh

Sau khi chạy server:

```bash
python scripts/smoke_mvp.py
```

## Gợi ý cấu trúc frontend riêng

Frontend riêng có thể là React, Next.js, Vue hoặc mobile app. Chỉ cần gọi backend này.

Ví dụ `.env` bên frontend:

```env
VITE_FINIIP_API_BASE=http://127.0.0.1:8000
```

Ví dụ gọi API:

```js
const res = await fetch(`${import.meta.env.VITE_FINIIP_API_BASE}/ai/v3/analyze`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    description: 'Thanh toán quảng cáo Facebook 5000000 bằng tiền mặt',
    amount: 5000000,
    payment_method: 'cash'
  })
})
const data = await res.json()
```

## Ghi chú quan trọng

Bản này không kèm thư mục `frontend/`. Các route UI cũ như `/app`, `/v23/review-queue-ui`, `/v24/quality-dashboard-ui` chỉ trả JSON hướng dẫn API để tránh lỗi 404 khi frontend đã tách riêng.


## AI V4 - Bulk Import / Bank Statement Intelligence

Bản này đã thêm API V4 để frontend riêng có thể upload CSV/XLSX sao kê ngân hàng hoặc danh sách giao dịch, backend tự đọc từng dòng và phân tích AI hàng loạt.

Endpoint mới:

```text
GET  /ai/v4/capabilities
GET  /ai/v4/demo-bank-statement
POST /ai/v4/batch-analyze-items
POST /ai/v4/import-preview
POST /ai/v4/detect-duplicates
POST /ai/v4/validate-journal
```

File mẫu:

```text
data/sample_bank_statement_v4.csv
```

Luồng frontend nên dùng:

```text
Upload CSV/XLSX
→ POST /ai/v4/import-preview
→ Hiển thị preview AI
→ Dòng an toàn tạo draft
→ Dòng rủi ro đưa vào review queue
→ Kế toán duyệt/sửa/từ chối
→ Sau đó mới ghi sổ
```

Xem thêm: `docs/AI_V4_BULK_IMPORT_GUIDE.md`.

## AI V5-V9 full upgrade

Bản này đã thêm các API nâng cao:

- `POST /ai/v5/feedback` — lưu correction của người dùng để AI học.
- `POST /ai/v5/analyze-with-learning` — phân tích có áp dụng rule đã học.
- `POST /ai/v6/invoice-to-transaction` — OCR text hóa đơn sang transaction draft.
- `POST /ai/v7/knowledge/upload-text` và `POST /ai/v7/ask` — RAG/QA tài liệu kế toán nội bộ.
- `POST /ai/v8/anomaly-score` — chấm điểm bất thường cho danh sách giao dịch.
- `GET /ai/v9/security-status` — kiểm tra API key guard.

Xem thêm: `docs/AI_V5_TO_V9_FULL_UPGRADE_GUIDE.md`.

Test nhanh offline:

```bash
python scripts/test_ai_v5_v9_offline.py
```
