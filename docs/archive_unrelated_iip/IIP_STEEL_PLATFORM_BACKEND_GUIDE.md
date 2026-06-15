# Finiip + IIP Steel Platform Backend Guide

Đã bổ sung module backend `/iip/*` theo kế hoạch nền tảng bảo vệ lợi nhuận và dòng tiền cho đại lý thép cấp 1.

## Chạy backend

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Mở Swagger:

```text
http://127.0.0.1:8000/docs
```

## Test nhanh dữ liệu demo

1. Nạp demo:

```bash
curl -X POST http://127.0.0.1:8000/iip/demo/seed
```

2. Xem báo cáo sáng Chủ tịch:

```bash
curl http://127.0.0.1:8000/iip/chairman/morning-report
```

## API chính đã bổ sung

### 1. Nhập 8 loại dữ liệu giai đoạn 1

```text
POST /iip/import/dealers
POST /iip/import/debts
POST /iip/import/sales-staff
POST /iip/import/price-floors
POST /iip/import/credit-limits
POST /iip/import/orders
POST /iip/import/payments
POST /iip/import/invoices
```

Có thể upload Excel hoặc CSV. Header tiếng Việt phổ biến được tự map, ví dụ: `mã đại lý`, `tên đại lý`, `tỉnh`, `hạn mức`, `công nợ`, `ngày đến hạn`, `mã đơn`, `mã sản phẩm`, `giá bán`, `số lượng`.

### 2. Module 1 - Công nợ, dòng tiền, nhân viên

```text
GET  /iip/dealers/{dealer_code}/wallet
GET  /iip/risk/overdue-debts
GET  /iip/risk/credit-limit-violations
GET  /iip/risk/low-price-sales
GET  /iip/staff/profit-ranking
POST /iip/orders/{order_code}/check-before-approve
POST /iip/orders/{order_code}/approve
```

### 3. Module 2 - Hóa đơn/VAT và đối soát 4 chiều

```text
POST /iip/invoices
GET  /iip/reconcile/4-way
```

Đối soát giữa: đơn hàng/xuất kho/hóa đơn/công nợ/tiền về.

### 4. Module 3 - Thưởng doanh số VAS

```text
POST /iip/vas-targets
GET  /iip/vas/progress
```

Tự tính sản lượng VAS, dự báo cuối năm, gap còn thiếu và bonus có nguy cơ mất.

### 5. Module 4 - Xuất kho và vận chuyển

```text
POST /iip/warehouse-slips
POST /iip/deliveries
POST /iip/deliveries/{delivery_code}/confirm-delivered
```

Phiếu xuất kho tự sinh QR dạng text để frontend hiển thị QR thật.

### 6. Module 5 - Đại lý cấp 2 và tín dụng

```text
POST /iip/dealers
POST /iip/credit-limits
GET  /iip/dealers/{dealer_code}/wallet
```

Dealer wallet trả về: tổng đơn hàng, tổng tiền đã thanh toán, công nợ hiện tại, hạn mức, còn được mua thêm, tình trạng vượt hạn mức, chính sách theo rank A/B/C/D.

## API quan trọng nhất để frontend gọi

```text
GET /iip/chairman/morning-report
```

API này trả về:

- Hôm nay cần thu bao nhiêu
- Nợ quá hạn
- Đại lý vượt hạn mức
- Đơn bán dưới giá sàn
- Rủi ro hụt thưởng VAS
- Dự báo dòng tiền 30 ngày
- Executive summary cho Chủ tịch

## Gợi ý frontend

Frontend riêng chỉ cần gọi các API sau trước:

```text
/iip/chairman/morning-report
/iip/risk/overdue-debts
/iip/risk/low-price-sales
/iip/reconcile/4-way
/iip/vas/progress
/iip/dealers/{dealer_code}/wallet
```

Sau đó mới làm màn import Excel và màn quản trị đơn hàng/xuất kho.
