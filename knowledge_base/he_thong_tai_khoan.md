---
title: "Cách chọn hệ thống tài khoản và tài khoản đối ứng"
doc_type: "accounting_guide"
authority: "curated_internal"
status: "active"
verified_on: "2026-06-13"
source_completeness: "comprehensive_summary"
tags: [tai_khoan, doi_ung, mapping, che_do_ke_toan]
---

# Cách chọn hệ thống tài khoản và tài khoản đối ứng

## Bước 1 — Xác định chế độ kế toán

Không khẳng định số tài khoản chi tiết trước khi biết doanh nghiệp đang áp dụng chế độ nào. Tối thiểu cần đọc `accounting_regime`, `inventory_method`, `vat_method` và sơ đồ tài khoản của workspace.

Nếu không có cấu hình, AI chỉ được nêu tài khoản phổ biến và gắn trạng thái `needs_review`.

## Bước 2 — Xác định đối tượng kinh tế

- Tiền mặt: 111; ngân hàng: 112; ngoại tệ phải theo dõi nguyên tệ và tỷ giá.
- Khách hàng còn nợ: 131; nhà cung cấp còn phải trả: 331; tạm ứng nhân viên: 141.
- Hàng mua để bán: 156; nguyên vật liệu: 152; CCDC: 153; sản phẩm dở dang: 154; thành phẩm: 155.
- TSCĐ hữu hình/vô hình: 211/213; hao mòn: 214; chi phí trả trước: 242.
- VAT đầu vào: 1331/1332; VAT đầu ra và nghĩa vụ VAT: 3331.
- Doanh thu chính: 511; giảm trừ doanh thu: 521; giá vốn: 632.
- Chi phí sản xuất: 621/622/627; bán hàng: 641; quản lý: 642; tài chính: 635.

## Bước 3 — Xác định đối ứng theo thanh toán

- Trả ngay bằng tiền mặt: Có 111.
- Trả ngay qua ngân hàng: Có 112.
- Mua chưa trả: Có 331.
- Ứng trước nhà cung cấp: Nợ 331/Có 111 hoặc 112, theo dõi chi tiết đối tượng.
- Khách trả tiền: Nợ 111/112/Có 131 nếu doanh thu đã ghi nhận.
- Bán chưa thu: Nợ 131.
- Nhận trước của khách: Có 131 theo chi tiết hoặc tài khoản phù hợp với chế độ, chưa tự ghi Có 511 khi chưa đủ điều kiện doanh thu.

## Bước 4 — Xử lý VAT

- VAT đầu vào đủ điều kiện: Nợ 1331 hoặc 1332.
- VAT đầu ra: Có 3331.
- VAT không được khấu trừ: xem xét cộng vào nguyên giá, giá trị hàng tồn kho hoặc chi phí phù hợp; không mặc định đưa toàn bộ vào 811.
- Hàng hóa/dịch vụ vừa dùng cho hoạt động chịu VAT vừa không chịu VAT cần hạch toán riêng hoặc phân bổ theo quy định.

## Bước 5 — Kiểm tra logic

- Tổng Nợ = tổng Có.
- Tài khoản phải phù hợp với bản chất và bộ phận sử dụng.
- Không dùng đồng thời 153 và 242 cho cùng một giá trị tại cùng thời điểm nếu thiếu bước xuất dùng/chuyển theo dõi.
- Không ghi 511 khi chỉ thu tiền công nợ hoặc nhận tiền đặt cọc chưa đủ điều kiện.
- Không ghi 632 nếu chưa có căn cứ giá vốn, xuất kho hoặc hoàn thành dịch vụ.
- Mọi bút toán phải kèm lý do, giả định và phương án thay thế khi dữ liệu chưa đủ.
