---
title: "Quy trình kế toán nội bộ và kiểm soát AI"
doc_type: "internal_process"
authority: "internal_policy"
status: "active"
verified_on: "2026-06-13"
source_completeness: "comprehensive_summary"
tags: [workflow, approval, internal_control, feedback]
---

# Quy trình kế toán nội bộ và kiểm soát AI

## Luồng từ giao dịch đến ghi sổ

1. Người dùng nhập mô tả, ngày, số tiền, đối tượng, thanh toán và chứng từ.
2. OCR/parser trích xuất nhưng giữ liên kết tới file và vùng nguồn.
3. Bộ định tuyến phân loại: bút toán, pháp lý/RAG, dữ liệu doanh nghiệp hay trò chuyện.
4. Rule engine tạo ứng viên bút toán; RAG giải thích và kiểm tra điều kiện.
5. Bộ lọc thời gian loại nguồn chưa hiệu lực/hết hiệu lực theo ngày nghiệp vụ.
6. Quality gate kiểm tra cân Nợ/Có, VAT, công nợ, kho, tài sản, nguồn và dữ liệu thiếu.
7. AI trả lời kèm giả định, citation, confidence và trạng thái.
8. Kế toán sửa/xác nhận; kế toán trưởng hoặc người có quyền duyệt.
9. Chức năng riêng mới thực hiện ghi sổ.
10. Lưu audit log và feedback.

## Trạng thái

- `draft`: nháp có thể xem.
- `needs_information`: thiếu dữ liệu làm thay đổi kết luận.
- `needs_review`: nhiều phương án hoặc rủi ro cao.
- `blocked`: vi phạm quality gate.
- `approved`: đã được người có quyền duyệt.
- `posted`: đã ghi sổ qua chức năng riêng.
- `rejected`: bị từ chối, lưu lý do.

## Dữ liệu bắt buộc

Ngày nghiệp vụ/kỳ, mô tả, số tiền và tiền tệ, đối tượng, thanh toán, VAT, bộ phận/mục đích, hóa đơn/hợp đồng, giao nhận/nghiệm thu và tài khoản/chế độ kế toán workspace.

## Feedback loop an toàn

Lưu đề xuất cũ, kết quả đúng, người sửa, lý do, chứng từ và phiên bản rule. Chỉ nâng thành rule dùng chung sau review nhiều trường hợp; không tự học từ một lần sửa.

## Phân quyền

Người nhập không tự duyệt giao dịch nhạy cảm. Thay đổi tài khoản, thuế, ngày, đối tượng hoặc số tiền sau duyệt phải tạo phiên bản mới và audit trail.

## Upload tài liệu

File giao dịch của người dùng không tự động trở thành knowledge chính thức. Chỉ admin đưa văn bản đã kiểm tra vào kho RAG, kèm metadata hiệu lực và nguồn.
