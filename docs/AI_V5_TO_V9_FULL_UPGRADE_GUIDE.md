# Finiip Backend AI V5-V9 Full Upgrade

Bản này giữ backend-only và thêm các API AI thực tế cho frontend riêng.

## V5 - AI học từ correction

Lưu khi người dùng sửa kết quả AI:

```http
POST /ai/v5/feedback
```

Sau đó phân tích có áp dụng learning:

```http
POST /ai/v5/analyze-with-learning
```

Xem rule đã học:

```http
GET /ai/v5/learning-rules
GET /ai/v5/learning-stats
```

## V6 - OCR hóa đơn sang transaction draft

```http
POST /ai/v6/invoice-to-transaction
```

Input là text OCR hoặc text hóa đơn. Backend parse hóa đơn, tạo draft giao dịch và chạy AI analyze nếu `auto_analyze=true`.

## V7 - RAG nội bộ nhẹ

Upload tài liệu:

```http
POST /ai/v7/knowledge/upload-text
```

Hỏi tài liệu:

```http
POST /ai/v7/ask
```

## V8 - Anomaly scoring

```http
POST /ai/v8/anomaly-score
```

Dùng sau khi import sao kê V4 để đánh dấu giao dịch bất thường, tiền mặt lớn, dịch vụ lớn, nghi trùng.

## V9 - API key guard

Mặc định local demo không cần key. Muốn bật bảo vệ V5-V8:

```env
FINIIP_API_KEY=your-secret-key
```

Frontend gửi header:

```http
X-API-Key: your-secret-key
```

Kiểm tra trạng thái:

```http
GET /ai/v9/security-status
```
