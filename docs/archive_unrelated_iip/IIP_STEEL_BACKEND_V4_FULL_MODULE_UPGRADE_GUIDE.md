# Finiip + IIP Steel Backend V4 - Full 5 Module Upgrade

Bản V4 nâng sâu backend cho 5 module Giai đoạn 1 theo kế hoạch IIP.

## Chạy nhanh

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Mở Swagger:

```text
http://127.0.0.1:8000/docs
```

Seed dữ liệu demo V4:

```bash
curl -X POST http://127.0.0.1:8000/iip/demo/seed-v4
```

Kiểm tra:

```bash
curl http://127.0.0.1:8000/iip/v4/status
curl http://127.0.0.1:8000/iip/v4/roadmap/completion-score
```

## Module 1 - Công nợ, dòng tiền, nhân viên

V4 bổ sung:

- Giá vốn theo sản phẩm/khu vực: `POST /iip/v4/cost-prices`
- Chi phí vận chuyển theo đơn: `POST /iip/v4/transport-costs`
- Lãi thật từng đơn: `GET /iip/v4/profit/orders/{order_code}`
- Xếp hạng nhân viên theo lãi thật: `GET /iip/v4/profit/staff-ranking`
- Cảnh báo đơn âm lãi: `GET /iip/v4/risk/negative-margin-orders`
- Dự báo dòng tiền 7-180 ngày: `GET /iip/v4/cashflow/forecast?days=30`
- Workflow duyệt ngoại lệ: `/iip/v4/approvals/*`

## Module 2 - Hóa đơn & VAT

V4 bổ sung:

- Upload/parse XML hóa đơn điện tử: `POST /iip/v4/invoices/xml/upload`
- VAT summary theo tháng: `GET /iip/v4/vat/summary?month=2026-05`
- Đối soát 4 chiều chi tiết: `GET /iip/v4/reconcile/4-way/detail`
- Risk score đối soát: `GET /iip/v4/reconcile/4-way/risk-score`
- Resolve cảnh báo đối soát: `POST /iip/v4/reconcile/4-way/resolve`

## Module 3 - Thưởng doanh số VAS

V4 bổ sung:

- Chương trình thưởng nhiều bậc: `POST /iip/v4/bonus/programs`
- Mốc thưởng: `POST /iip/v4/bonus/tiers`
- Tiến độ thưởng: `GET /iip/v4/bonus/progress`
- Mô phỏng chiết khấu/lợi nhuận/thưởng: `POST /iip/v4/vas/simulate`
- Gợi ý bán theo vùng/đại lý còn hạn mức: `GET /iip/v4/vas/recommendations/by-region`

## Module 4 - Xuất kho & vận chuyển

V4 bổ sung:

- QR token ký chống sửa phiếu xuất: `GET /iip/v4/warehouse/slips/{slip_code}/qr-token`
- Verify QR: `POST /iip/v4/warehouse/slips/verify`
- GPS route points: `POST /iip/v4/deliveries/{delivery_code}/location`
- Xem route: `GET /iip/v4/deliveries/{delivery_code}/route`
- Event ảnh/chữ ký/geofence/scan: `POST /iip/v4/deliveries/{delivery_code}/event`
- Xe tải và ghép đơn: `POST /iip/v4/vehicles`, `POST /iip/v4/logistics/route-suggestions`

## Module 5 - Đại lý cấp 2 & tín dụng

V4 bổ sung:

- Credit score sâu: `GET /iip/v4/dealers/{dealer_code}/credit-score`
- Lịch sử điểm tín dụng: `GET /iip/v4/dealers/{dealer_code}/credit-score-history`
- Xu hướng mua hàng: `GET /iip/v4/dealers/{dealer_code}/purchase-trend`
- Gợi ý giữ chân đại lý: `GET /iip/v4/dealers/{dealer_code}/retention-suggestions`
- Dealer self-service API: `/iip/v4/dealer/me`, `/iip/v4/dealer/wallet`, `/iip/v4/dealer/orders`

## Login demo

Sau seed V4:

```bash
curl -X POST http://127.0.0.1:8000/iip/v3/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

Dealer demo:

```bash
curl -X POST http://127.0.0.1:8000/iip/v3/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"dealer_sonla","password":"dealer123"}'
```

## Mức hoàn thiện sau V4

- Backend logic 5 module: khoảng 93%.
- Mức sẵn sàng triển khai nếu chưa có frontend/mobile: khoảng 82%.
- Phần còn lại chủ yếu là frontend dashboard, mobile tài xế/đại lý, kết nối ngân hàng/hóa đơn điện tử/Zalo thật và test với dữ liệu khách hàng thật.
