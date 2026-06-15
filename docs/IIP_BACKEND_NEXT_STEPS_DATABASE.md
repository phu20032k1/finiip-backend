# IIP Backend Next Steps - Database + API thật

Bản này đi theo hướng: backend trước, frontend tách riêng gọi API sau.

## Trạng thái hiện tại

Backend IIP đã có:

- Database models cho đại lý, nhân viên, sản phẩm, giá sàn, hạn mức, công nợ, đơn hàng, thanh toán, hóa đơn, xuất kho, giao hàng, VAS.
- API nhập tay cho dữ liệu lõi.
- API import CSV/Excel.
- API báo cáo sáng Chủ tịch.
- API cảnh báo nợ quá hạn, vượt hạn mức, bán dưới giá sàn.
- API đối soát 4 chiều.
- API VAS progress.
- Seed dữ liệu demo.

## Việc làm tiếp theo

### 1. Chốt dữ liệu mẫu thực tế

Dùng script:

```bash
python scripts/seed_iip_sample_data.py
```

Sau đó kiểm tra:

```bash
python scripts/test_iip_backend.py
```

### 2. Test bằng Swagger

Mở:

```text
http://127.0.0.1:8000/docs
```

Test nhóm API `/iip/*`.

### 3. Gửi API contract cho đội frontend

File:

```text
docs/IIP_API_CONTRACT_FRONTEND.md
```

Frontend nên làm 4 màn hình trước:

1. Dashboard Chủ tịch
2. Công nợ & đại lý
3. Cảnh báo rủi ro
4. Đối soát 4 chiều + VAS

### 4. Khi có dữ liệu thật từ khách

Nhập theo thứ tự:

1. Nhân viên kinh doanh
2. Đại lý cấp 2
3. Sản phẩm thép
4. Bảng giá sàn
5. Hạn mức tín dụng
6. Công nợ đầu kỳ
7. Đơn hàng
8. Hóa đơn
9. Thanh toán/sao kê

### 5. Chưa cần làm ngay

Chưa ưu tiên:

- OCR hóa đơn
- Kết nối ngân hàng
- AI đọc ảnh
- Mobile app
- Dashboard đẹp
- Phân quyền phức tạp

Lý do: Giai đoạn 1 trong kế hoạch IIP ưu tiên nhập tay đơn giản, kế toán nhập 10-15 phút/ngày, hệ thống tự tổng hợp và cảnh báo.
