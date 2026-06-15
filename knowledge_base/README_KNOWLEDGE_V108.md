---
title: "Finiip Knowledge Pack V108"
doc_type: "knowledge_manifest"
authority: "curated_internal"
status: "active"
verified_on: "2026-06-13"
version: "108"
source_completeness: "curated_summary_plus_controls"
tags: [manifest, accounting, tax, rag, vietnam]
---

# Finiip Knowledge Pack V108

Bộ tri thức dùng cho AI kế toán/RAG tại Việt Nam. V108 tập trung vào ba mục tiêu: trả lời đúng bản chất nghiệp vụ, không trộn hiệu lực pháp lý và tạo bút toán nháp có kiểm soát.

## Thứ tự ưu tiên nguồn

1. Văn bản quy phạm pháp luật chính thức đang có hiệu lực tại ngày nghiệp vụ.
2. Văn bản sửa đổi, bổ sung và văn bản hợp nhất có thể hiện rõ quan hệ hiệu lực.
3. Tài liệu nghiệp vụ kế toán đã được kiểm duyệt.
4. Chính sách nội bộ của doanh nghiệp/workspace.
5. FAQ, ví dụ và tình huống minh họa.

FAQ không được dùng để lấn át văn bản pháp luật. Bản tóm tắt không được dùng một mình để kết luận mức phạt, thời hạn, người ký hoặc toàn bộ nghĩa vụ pháp lý.

## Trạng thái hiệu lực bắt buộc

- `active`: đang có hiệu lực tại `verified_on`.
- `future_effective`: đã ban hành nhưng chưa đến ngày hiệu lực.
- `superseded`: đã được thay thế hoặc nội dung đã bị sửa.
- `historical`: chỉ dùng cho câu hỏi về giai đoạn trước.
- `internal_only`: quy trình nội bộ, không phải căn cứ pháp luật.

AI phải so sánh `transaction_date` với `effective_from` và `effective_to`. Không lấy ngày người dùng hỏi thay cho ngày phát sinh nghiệp vụ nếu hai ngày khác nhau.

## Phạm vi tài liệu

- Nền tảng kế toán, hệ thống tài khoản và bút toán kép.
- Mua, bán, thu, chi, công nợ, kho, giá vốn và sản xuất.
- VAT, hóa đơn, thanh toán không dùng tiền mặt và chi phí được trừ.
- TSCĐ, CCDC, chi phí trả trước, lương, bảo hiểm, TNCN.
- Vay, ngoại tệ, vốn chủ sở hữu, khóa sổ và báo cáo tài chính.
- Chế độ kế toán doanh nghiệp siêu nhỏ theo Thông tư 58/2026/TT-BTC ở trạng thái `future_effective` tại ngày 13/06/2026.
- Chính sách truy xuất RAG, citation, confidence và bộ câu hỏi đánh giá.

## File quan trọng

- `policies/ai_answer_policy.md`: cách AI trả lời và kiểm soát rủi ro.
- `policies/rag_retrieval_policy.md`: cách truy xuất, rerank và lọc hiệu lực.
- `sources/legal_source_registry.md`: danh mục văn bản và trạng thái hiệu lực.
- `global/accounting/`: nghiệp vụ kế toán chuyên sâu.
- `global/legal/`: tóm tắt pháp lý đã kiểm chứng.
- `tests/rag_eval_questions.jsonl`: bộ test regression cho RAG.

## Giới hạn

AI tạo đề xuất, giải thích và checklist; không tự ghi sổ, kê khai, ký, duyệt hoặc xác nhận tuân thủ khi thiếu chứng từ và dữ liệu thực tế. Câu hỏi pháp lý có hậu quả đáng kể phải kiểm tra văn bản gốc còn hiệu lực.
