# Finiip V12 - OCR đọc hóa đơn

Bản V12 thêm luồng đọc hóa đơn bằng OCR-lite:

```text
Upload hóa đơn / gửi text hóa đơn
→ Trích xuất số hóa đơn, ngày, nhà cung cấp, MST, subtotal, VAT, tổng tiền
→ AI gợi ý loại giao dịch và bút toán
→ Có thể tạo purchase invoice
→ Có thể tạo transaction draft
```

## API mới

### 1. Đọc hóa đơn từ text

Dùng khi bạn copy được text từ hóa đơn điện tử/PDF.

```bash
curl -X POST http://127.0.0.1:8000/ocr/invoice/text \
  -H "Content-Type: application/json" \
  -d '{
    "raw_text": "HÓA ĐƠN GIÁ TRỊ GIA TĂNG\nSố hóa đơn: HD001234\nNgày 15/05/2026\nĐơn vị bán hàng: Công ty Điện lực EVN Hà Nội\nCộng tiền hàng: 2.000.000\nThuế suất GTGT: 10%\nTiền thuế GTGT: 200.000\nTổng cộng thanh toán: 2.200.000",
    "create_purchase_invoice": true,
    "create_transaction": true,
    "auto_create_journal": false
  }'
```

### 2. Upload hóa đơn

Hỗ trợ tốt nhất với TXT và PDF có text-layer. Ảnh JPG/PNG cần cài Tesseract OCR trên máy.

```bash
curl -X POST "http://127.0.0.1:8000/ocr/invoice/upload?create_purchase_invoice=true&create_transaction=true" \
  -F "file=@invoice.pdf"
```

### 3. Demo nhanh

```bash
curl http://127.0.0.1:8000/ocr/invoice/demo
```

## Cài thêm OCR ảnh

Python packages đã có trong `requirements.txt`:

```text
pypdf
pillow
pytesseract
```

Nhưng để OCR ảnh thật, máy cần cài thêm Tesseract binary.

Windows: cài Tesseract OCR rồi thêm vào PATH.
Ubuntu/Debian:

```bash
sudo apt-get install tesseract-ocr tesseract-ocr-vie tesseract-ocr-eng
```

macOS:

```bash
brew install tesseract tesseract-lang
```

## Kết quả trả về

```json
{
  "extracted": {
    "invoice_number": "HD001234",
    "invoice_date": "2026-05-15",
    "supplier_name": "Công ty Điện lực EVN Hà Nội",
    "subtotal": 2000000,
    "vat_rate": 10,
    "vat_amount": 200000,
    "total_amount": 2200000,
    "confidence": 0.8
  },
  "ai_suggestion": {
    "ai_result": {
      "category": "Chi phí điện nước",
      "debit_account_code": "642",
      "credit_account_code": "111"
    }
  }
}
```

## Lưu ý

Đây là OCR-lite phù hợp backend prototype. Với hóa đơn thật ở Việt Nam, bước tiếp theo nên nâng lên OCR chuyên nghiệp hơn: đọc XML hóa đơn điện tử, PDF text-layer, hoặc tích hợp OCR service như Google Vision/Azure/AWS sau này.
