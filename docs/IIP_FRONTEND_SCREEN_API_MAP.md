# IIP Frontend Screen API Map

Frontend làm riêng, backend giữ logic nghiệp vụ. File này là contract thực dụng để đội frontend biết màn nào gọi API nào.

## 1. Màn Dashboard Chủ tịch

### API chính

```text
GET /iip/chairman/morning-report
```

### API phụ

```text
GET /iip/risk/overdue-debts
GET /iip/risk/credit-limit-violations
GET /iip/risk/low-price-sales
GET /iip/reconcile/4-way
GET /iip/vas/progress
```

### Hiển thị

- Hôm nay cần thu bao nhiêu
- Tổng nợ quá hạn
- Đại lý vượt hạn mức
- Đơn bán dưới giá sàn
- Rủi ro đối soát 4 chiều
- Tiến độ thưởng VAS

## 2. Màn nhập đại lý cấp 2

### API

```text
POST /iip/dealers
GET /iip/dealers/{dealer_code}/wallet
POST /iip/credit-limits
```

### Form tối thiểu

```json
{
  "code": "DL001",
  "name": "Đại lý Sơn La",
  "province": "Sơn La",
  "phone": "09xxxxxxxx",
  "sales_staff_code": "NV001",
  "rank": "B",
  "status": "active"
}
```

## 3. Màn nhập nhân viên kinh doanh

### API

```text
POST /iip/sales-staff
```

### Form tối thiểu

```json
{
  "code": "NV001",
  "name": "Nguyễn Văn A",
  "phone": "09xxxxxxxx",
  "region": "Tây Bắc",
  "status": "active"
}
```

## 4. Màn bảng giá sàn

### API

```text
POST /iip/products
POST /iip/price-floors
```

### Frontend cần cảnh báo người nhập

- Giá sàn phải lớn hơn 0
- Mã sản phẩm phải thống nhất với đơn hàng
- Ngày hiệu lực không được bỏ trống

## 5. Màn đơn hàng

### API

```text
POST /iip/orders
POST /iip/orders/{order_code}/check-before-approve
POST /iip/orders/{order_code}/approve
```

### Khi người dùng bấm tạo đơn

Frontend gửi `POST /iip/orders`.

### Khi người dùng bấm kiểm tra rủi ro trước duyệt

Frontend gọi:

```text
POST /iip/orders/{order_code}/check-before-approve
```

Backend sẽ trả về rủi ro giá sàn, hạn mức, công nợ.

## 6. Màn công nợ

### API

```text
POST /iip/debts
POST /iip/payments
GET /iip/risk/overdue-debts
GET /iip/risk/credit-limit-violations
```

### Hiển thị

- Công nợ từng đại lý
- Số tiền đã thanh toán
- Số tiền còn nợ
- Ngày đến hạn
- Số ngày quá hạn
- Trạng thái cảnh báo

## 7. Màn hóa đơn và đối soát

### API

```text
POST /iip/invoices
GET /iip/reconcile/4-way
```

### Hiển thị

- Hàng xuất nhưng chưa có hóa đơn
- Hóa đơn có nhưng chưa thấy tiền về
- Tiền về chưa gán được hóa đơn
- Công nợ còn mở

## 8. Màn import Excel

### API

```text
GET /iip/import/template-workbook
POST /iip/import/{data_type}
POST /iip/v3/import/{data_type}/preview
POST /iip/v3/import/{batch_code}/commit
```

### data_type hỗ trợ

```text
dealers
sales_staff
products
price_floors
credit_limits
orders
debts
payments
invoices
vas_targets
```

## 9. Màn phân quyền sau này

Backend đã có nhóm API V3 cho auth/RBAC:

```text
POST /iip/v3/auth/bootstrap-admin
POST /iip/v3/auth/login
GET /iip/v3/auth/me
POST /iip/v3/users
GET /iip/v3/users
```

Vai trò tối thiểu:

```text
admin
chairman
accountant
sales_manager
sales_staff
dealer
```

## 10. Thứ tự frontend nên làm

```text
1. Dashboard Chủ tịch
2. Import Excel
3. Đại lý + công nợ
4. Đơn hàng
5. Hóa đơn + đối soát
6. Phân quyền
```
