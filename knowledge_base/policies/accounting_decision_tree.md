---
title: "Cây quyết định xử lý nghiệp vụ kế toán"
doc_type: "decision_tree"
authority: "internal_policy"
status: "active"
verified_on: "2026-06-13"
tags: [decision_tree, accounting, vat, tndn, bookkeeping]
---

# Cây quyết định xử lý nghiệp vụ kế toán

## Khi gặp một nghiệp vụ mới

AI phải lần lượt xác định:

1. Đây là nghiệp vụ gì?
   - mua hàng
   - bán hàng
   - chi phí
   - tài sản cố định
   - công cụ dụng cụ
   - lương
   - vay vốn
   - thuế
   - điều chỉnh/sai sót

2. Có đủ chứng từ chưa?
   - hợp đồng
   - hóa đơn
   - chứng từ thanh toán
   - biên bản giao nhận
   - phiếu nhập/xuất kho
   - bảng lương/bảng chấm công
   - quyết định/phê duyệt nội bộ

3. Xử lý theo 3 lớp riêng biệt:
   - ghi nhận kế toán
   - khấu trừ/khai thuế GTGT
   - chi phí được trừ khi tính TNDN

Không được gộp 3 lớp này thành một kết luận duy nhất.

## Cấu trúc trả lời chuẩn

Khi người dùng hỏi nghiệp vụ, trả lời theo mẫu:

1. Kết luận nhanh
2. Bút toán đề xuất
3. Điều kiện chứng từ
4. Điều kiện VAT nếu có
5. Điều kiện TNDN nếu có
6. Rủi ro/sai sót thường gặp
7. Cần hỏi thêm gì nếu thiếu dữ liệu

## Nếu thiếu dữ liệu

Không được đoán. Phải nói:

"Để kết luận chắc, cần thêm: ngày nghiệp vụ, loại doanh nghiệp/chế độ kế toán, hóa đơn, giá trị thanh toán, hình thức thanh toán và mục đích sử dụng."

## Ví dụ: mua hàng hóa

Nếu mua hàng hóa nhập kho:

Nợ 156  
Nợ 1331 nếu đủ điều kiện khấu trừ VAT  
Có 111/112/331

Nếu mua về dùng ngay:

Nợ 642/641/627 tùy mục đích  
Nợ 1331 nếu đủ điều kiện  
Có 111/112/331

## Ví dụ: mua CCDC

Nếu giá trị nhỏ, dùng ngay:

Nợ 642/641/627  
Nợ 1331 nếu đủ điều kiện  
Có 111/112/331

Nếu phân bổ nhiều kỳ:

Nợ 242  
Nợ 1331 nếu đủ điều kiện  
Có 111/112/331

Khi phân bổ:

Nợ 642/641/627  
Có 242

## Ví dụ: mua TSCĐ

Khi ghi nhận:

Nợ 211  
Nợ 1332 nếu đủ điều kiện  
Có 111/112/331

Khi trích khấu hao:

Nợ 642/641/627  
Có 214

## Nguyên tắc tránh sai

- Không thấy hóa đơn thì không tự kết luận được khấu trừ VAT.
- Không thấy thanh toán thì không tự kết luận được chi phí được trừ với khoản bắt buộc thanh toán không dùng tiền mặt.
- Không biết mục đích sử dụng thì không tự chọn 641, 642 hay 627.
- Không biết chế độ kế toán thì phải nêu giả định.