---
title: "Finiip V110 - Xử lý dữ liệu, Excel và thiết kế báo cáo"
doc_type: "data_reporting_playbook"
authority: "curated_internal"
status: "active"
verified_on: "2026-06-15"
source_completeness: "broad_practical_guide"
tags: [excel, data, reporting, reconciliation, automation]
---

# Xử lý dữ liệu, Excel và thiết kế báo cáo

## 1. Quy tắc dữ liệu đầu vào

- Mỗi hàng đại diện một giao dịch/đối tượng ở cùng mức chi tiết.
- Mỗi cột có tên duy nhất, kiểu dữ liệu nhất quán và đơn vị rõ ràng.
- Không dùng ô gộp trong bảng dữ liệu; không chèn dòng tổng vào giữa dữ liệu nguồn.
- Ngày lưu ở kiểu ngày, số lưu ở kiểu số, mã có số 0 đầu lưu dạng text.
- Có khóa giao dịch hoặc tổ hợp khóa để phát hiện trùng.
- Lưu bảng danh mục riêng cho tài khoản, khách hàng, nhà cung cấp, sản phẩm và bộ phận.

## 2. Làm sạch dữ liệu

1. Chuẩn hóa khoảng trắng, chữ hoa/thường và dấu phân cách.
2. Chuẩn hóa ngày, tiền tệ, đơn vị và dấu âm.
3. Xử lý giá trị trống theo ý nghĩa; không tự thay bằng 0 khi 0 có nghĩa khác “không biết”.
4. Phát hiện bản ghi trùng bằng khóa và chỉ tiêu kiểm tra.
5. Đối chiếu tổng trước và sau làm sạch.
6. Lưu log các quy tắc và số dòng bị thay đổi.

## 3. Đối chiếu hai nguồn

- Chuẩn hóa khóa ở cả hai nguồn.
- Ghép theo khóa chính; nếu không có khóa duy nhất, dùng tổ hợp ngày, số tiền, đối tượng, nội dung và tham chiếu.
- Phân loại: khớp hoàn toàn, khớp khóa nhưng lệch số, chỉ có ở nguồn A, chỉ có ở nguồn B, nhiều-nhiều cần xem xét.
- Thiết lập ngưỡng sai số cho làm tròn nhưng không che giấu chênh lệch thật.
- Báo cáo tổng số dòng, tổng tiền và danh sách ngoại lệ.

## 4. Công thức và kiểm tra bảng tính

- Dùng tham chiếu rõ ràng, ưu tiên bảng có cấu trúc và vùng dữ liệu động.
- Tách input, calculation và output.
- Tránh số cố định ẩn trong công thức; đặt giả định trong vùng riêng.
- Thêm kiểm tra: tổng Nợ - tổng Có = 0, số dư đầu + phát sinh = số dư cuối, tổng chi tiết = tổng hợp.
- Gắn nhãn đơn vị và kỳ; khóa vùng công thức khi phát hành.
- Phiên bản hóa file và ghi nguồn dữ liệu/ngày cập nhật.

## 5. Pivot và tổng hợp

Trước khi tổng hợp phải xác định:
- chỉ tiêu cần cộng/đếm/trung bình;
- chiều phân tích: thời gian, tài khoản, khách hàng, sản phẩm, bộ phận;
- cách xử lý giao dịch âm, hoàn trả và điều chỉnh;
- mức chi tiết và bộ lọc.

Không cộng các tỷ lệ trực tiếp; tính tỷ lệ từ tổng tử số và mẫu số khi phù hợp.

## 6. Thiết kế báo cáo quản trị

Một báo cáo tốt gồm:
1. Tiêu đề, kỳ, đơn vị và ngày cập nhật.
2. Tóm tắt điều hành.
3. KPI chính và so sánh kế hoạch/cùng kỳ.
4. Phân tích nguyên nhân.
5. Danh sách ngoại lệ và hành động.
6. Phụ lục dữ liệu và công thức.

Định dạng:
- Số âm và số bất thường hiển thị nhất quán.
- Cột số căn phải, tiêu đề rõ, đơn vị không lẫn.
- Không dùng quá nhiều màu; màu phải có ý nghĩa và chú giải.
- Freeze header, filter và độ rộng cột phù hợp.

## 7. Biểu đồ

- Đường: xu hướng theo thời gian.
- Cột: so sánh danh mục hoặc kỳ.
- Waterfall: cầu nối biến động từ đầu đến cuối.
- Scatter: quan hệ giữa hai biến.
- Không dùng biểu đồ tròn khi có nhiều nhóm hoặc chênh lệch nhỏ.
- Trục không phù hợp có thể gây hiểu sai; nêu rõ đơn vị và kỳ.

## 8. Khi Finiip đọc file

Finiip cần:
1. Nêu tên file/sheet, số dòng/cột đã đọc và phần bị giới hạn.
2. Nhận diện tiêu đề và kiểu dữ liệu.
3. Kiểm tra dòng trống, trùng, lỗi số/ngày và tổng kiểm soát.
4. Chỉ dùng dữ liệu có trong file, ghi rõ giả định.
5. Với file lớn, chọn các phần liên quan rồi tổng hợp, không cắt tùy ý phần cuối.
6. Khi xuất file, giữ bảng dữ liệu, bảng kết quả, công thức/giả định và ghi chú nguồn ở các sheet riêng.

## 9. Mẫu workbook xuất ra

- `Tong_quan`: mục tiêu, kỳ, nguồn file, trạng thái và cảnh báo.
- `Du_lieu`: dữ liệu đã chuẩn hóa.
- `Tinh_toan`: công thức, giả định và bước tính.
- `Ket_qua`: bảng báo cáo chính.
- `Ngoai_le`: dòng lỗi/chênh lệch cần xử lý.
- `Huong_dan`: định nghĩa cột và cách cập nhật.
