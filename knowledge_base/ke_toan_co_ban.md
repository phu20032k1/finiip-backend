---
title: "Kiến thức kế toán nền tảng và cách AI xử lý nghiệp vụ"
doc_type: "accounting_guide"
authority: "curated_internal"
status: "active"
verified_on: "2026-06-13"
source_completeness: "comprehensive_summary"
tags: [ke_toan_co_ban, but_toan_kep, chung_tu, recognition, workflow]
---

# Kiến thức kế toán nền tảng và cách AI xử lý nghiệp vụ

## Phương trình và bút toán kép

Tài sản = Nợ phải trả + Vốn chủ sở hữu. Mỗi nghiệp vụ có ít nhất một dòng Nợ và một dòng Có; tổng Nợ phải bằng tổng Có. Nợ/Có không đồng nghĩa trực tiếp với thu/chi hoặc tăng/giảm.

- Tài sản và chi phí thường tăng bên Nợ, giảm bên Có.
- Nợ phải trả, vốn chủ sở hữu và doanh thu thường tăng bên Có, giảm bên Nợ.
- Một dòng tiền có thể không tạo doanh thu hoặc chi phí, ví dụ thu hồi công nợ hay trả nợ gốc vay.

## Tám câu hỏi trước khi định khoản

1. Bản chất giao dịch là mua, bán, thu, chi, công nợ, tài sản, lương, thuế hay điều chỉnh?
2. Quyền kiểm soát hàng hóa/dịch vụ và nghĩa vụ đã phát sinh chưa?
3. Ngày chứng từ, ngày giao nhận/nghiệm thu và kỳ kế toán là ngày nào?
4. Đối tượng liên quan là khách hàng, nhà cung cấp, nhân viên, bên liên kết hay chủ sở hữu?
5. Số tiền là trước VAT, VAT, tổng thanh toán, ngoại tệ hay đã quy đổi?
6. Thanh toán bằng tiền mặt, ngân hàng, công nợ, bù trừ, ủy quyền hay tạm ứng?
7. Khoản chi dùng cho bán hàng, quản lý, sản xuất, đầu tư hay nhiều kỳ?
8. Hồ sơ có đủ hợp đồng/đề nghị, giao nhận/nghiệm thu, hóa đơn và chứng từ thanh toán không?

## Phân biệt ghi nhận kế toán và xử lý thuế

Một khoản có thể được ghi nhận kế toán nhưng chưa chắc được trừ khi tính thuế TNDN hoặc được khấu trừ VAT. AI phải đưa ra ba kết luận riêng khi cần:

- Kế toán ghi nhận vào đâu và thời điểm nào.
- VAT đầu vào/đầu ra xử lý ra sao.
- Chi phí có đủ điều kiện thuế TNDN hay cần theo dõi điều chỉnh.

## Luồng xử lý chuẩn

1. Trích xuất dữ liệu từ mô tả/chứng từ.
2. Chuẩn hóa ngày, tiền tệ, số tiền, đối tượng, thuế suất và phương thức thanh toán.
3. Xác định chế độ kế toán và chính sách workspace.
4. Phân loại nghiệp vụ, thời điểm ghi nhận và tài khoản ứng viên.
5. Tách VAT chỉ khi đủ căn cứ.
6. Tạo bút toán nháp cân Nợ/Có.
7. Chạy kiểm tra công nợ, kho, tài sản, thuế và hiệu lực pháp lý.
8. Trả lời rõ giả định, dữ liệu thiếu, mức rủi ro và trạng thái nháp.
9. Người có thẩm quyền duyệt trước khi ghi sổ.

## Lỗi AI phải tránh

- Ghi doanh thu lần hai khi khách hàng chỉ thanh toán công nợ.
- Ghi chi phí ngay cho khoản tạo tài sản hoặc lợi ích nhiều kỳ.
- Tách VAT chỉ vì nhìn thấy một con số giống thuế suất.
- Coi hóa đơn là bằng chứng duy nhất của giao dịch thực tế.
- Dùng quy định chưa có hiệu lực để trả lời nghiệp vụ hiện hành.
- Trộn tài khoản của các chế độ kế toán mà không cảnh báo.
