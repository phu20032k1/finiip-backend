# IIP Stage 1 - Test thực chiến end-to-end

Mục tiêu của bước này là kiểm tra backend theo đúng luồng thực tế trước khi làm frontend riêng.

## Đã bổ sung

- Script test end-to-end: `scripts/test_iip_e2e_real_workflow.py`
- Tài liệu map màn hình frontend với API: `docs/IIP_FRONTEND_SCREEN_API_MAP.md`
- Checklist kiểm tra trước khi bàn giao frontend: tài liệu này

## Cách chạy test nhanh

Từ thư mục `copy`:

```bash
pip install -r requirements.txt
python scripts/test_iip_e2e_real_workflow.py
```

Script này không cần mở `uvicorn`, vì chạy trực tiếp qua FastAPI `TestClient`.

## Test này làm gì?

Script tự tạo một bộ dữ liệu thật dạng mẫu:

1. Nhân viên kinh doanh
2. Đại lý cấp 2
3. Sản phẩm thép VAS
4. Giá sàn
5. Hạn mức tín dụng
6. Đơn hàng bán dưới giá sàn
7. Công nợ quá hạn và vượt hạn mức
8. Thanh toán
9. Hóa đơn

Sau đó script gọi các API chính:

```text
GET /iip/chairman/morning-report
GET /iip/risk/overdue-debts
GET /iip/risk/credit-limit-violations
GET /iip/risk/low-price-sales
GET /iip/reconcile/4-way
GET /iip/vas/progress
```

## Kết quả mong muốn

Nếu chạy đúng, terminal sẽ hiện:

```text
E2E OK
```

Đồng thời backend phải phát hiện được:

- Có đại lý nợ quá hạn
- Có đại lý vượt hạn mức
- Có đơn hàng bán dưới giá sàn
- Báo cáo sáng Chủ tịch trả dữ liệu được
- Đối soát 4 chiều trả dữ liệu được

## Sau khi E2E OK thì làm frontend

Frontend riêng chỉ cần đọc `docs/IIP_FRONTEND_SCREEN_API_MAP.md` và gọi API theo từng màn.
