# Finiip AI V4 - Bulk Import / Bank Statement Intelligence

Bản V4 nâng cấp backend theo hướng dùng thật: frontend có thể upload CSV/XLSX sao kê ngân hàng hoặc danh sách giao dịch, backend tự chuẩn hoá dữ liệu, gọi AI V3 phân tích từng dòng, phát hiện rủi ro, kiểm tra bút toán và báo giao dịch nghi trùng.

## Endpoint chính

### 1. Xem khả năng V4

```http
GET /ai/v4/capabilities
```

### 2. Demo dữ liệu sao kê

```http
GET /ai/v4/demo-bank-statement
```

Lấy `items` trả về rồi POST sang `/ai/v4/batch-analyze-items`.

### 3. Phân tích danh sách giao dịch JSON

```http
POST /ai/v4/batch-analyze-items
```

Body mẫu:

```json
{
  "items": [
    {
      "transaction_date": "2026-06-01",
      "description": "Thanh toán quảng cáo Facebook bằng chuyển khoản",
      "amount": 5000000,
      "reference": "GD002"
    }
  ]
}
```

### 4. Upload CSV/XLSX để preview import

```http
POST /ai/v4/import-preview
Content-Type: multipart/form-data
file=@data/sample_bank_statement_v4.csv
```

Backend chưa ghi database. Nó chỉ preview:

- Dòng đã đọc được
- AI phân loại
- Gợi ý bút toán
- Explanation
- Risk flags
- Journal validation
- Recommended workflow
- Duplicate groups

### 5. Kiểm tra bút toán

```http
POST /ai/v4/validate-journal
```

Body 1 dòng:

```json
{
  "description": "Thanh toán quảng cáo Facebook",
  "amount": 5000000,
  "debit_account_code": "641",
  "credit_account_code": "112"
}
```

Body nhiều dòng:

```json
{
  "entries": [
    {"side": "debit", "account": "641", "amount": 5000000},
    {"side": "credit", "account": "112", "amount": 5000000}
  ]
}
```

## Luồng frontend nên dùng

```text
User upload CSV/XLSX
→ POST /ai/v4/import-preview
→ Hiển thị bảng preview
→ Dòng an toàn: cho tạo draft
→ Dòng REVIEW_REQUIRED: đưa kế toán duyệt
→ Dòng BLOCK_AUTO_POSTING: bắt buộc sửa dữ liệu trước
→ Người dùng approve/correct/reject
→ Sau đó mới ghi sổ
```

## Cột CSV/XLSX được nhận diện tự động

Backend cố gắng nhận nhiều tên cột khác nhau:

- Ngày: `date`, `ngày`, `ngay`, `transaction_date`, `ngày giao dịch`
- Mô tả: `description`, `mô tả`, `nội dung`, `diễn giải`, `memo`, `details`
- Số tiền: `amount`, `số tiền`, `credit`, `debit`, `thu`, `chi`, `value`
- Mã giao dịch: `reference`, `ref`, `mã giao dịch`, `số chứng từ`
- Đối tác: `counterparty`, `đối tác`, `beneficiary`, `sender`, `receiver`

## Test bằng PowerShell

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/ai/v4/import-preview" `
  -Method Post `
  -Form @{ file = Get-Item "data/sample_bank_statement_v4.csv" }
```

Hoặc chạy script:

```bash
python scripts/test_ai_v4_offline.py
```
