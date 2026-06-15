---
title: "Chính sách truy xuất RAG cho kế toán và pháp lý"
doc_type: "rag_policy"
authority: "internal_policy"
status: "active"
verified_on: "2026-06-13"
tags: [rag, retrieval, rerank, temporal, legal]
---

# Chính sách truy xuất RAG

## 1. Phân tích câu hỏi

Trích xuất: chủ đề, loại nghiệp vụ, ngày nghiệp vụ, chế độ kế toán, phương pháp VAT/TNDN, loại tài liệu cần tìm, số văn bản/điều khoản và mức độ rủi ro.

## 2. Truy xuất hai tầng

- Tầng 1: tìm rộng bằng semantic + keyword + alias tiếng Việt không dấu.
- Tầng 2: rerank theo đúng chủ đề, số văn bản, điều khoản, ngày hiệu lực, authority và độ đầy đủ.

## 3. Lọc hiệu lực trước khi sinh câu trả lời

Điểm nguồn = relevance × authority × temporal_fit × completeness.

Loại hoặc hạ điểm mạnh nếu:
- ngày nghiệp vụ nằm trước `effective_from`;
- ngày nghiệp vụ sau `effective_to`;
- tài liệu `future_effective` nhưng câu hỏi là hiện hành;
- chunk là FAQ trong khi có văn bản chính thức;
- chunk thiếu điều kiện/ngoại lệ quan trọng.

## 4. Không trộn chunk sai phạm vi

Không ghép ngưỡng VAT với điều kiện TNDN như một quy tắc duy nhất. Không ghép tài khoản của chế độ này với biểu mẫu chế độ khác. Không ghép điều khoản trước và sau sửa đổi mà không giải thích.

## 5. Chunking khuyến nghị

- Văn bản pháp luật: một điều/khoản hoặc nhóm khoản liên quan; giữ tiêu đề chương và metadata.
- Tài liệu nghiệp vụ: một tình huống + bút toán + điều kiện + cảnh báo.
- FAQ: một câu hỏi/một chunk.
- Bảng biểu: giữ tiêu đề cột, đơn vị và chú thích.

Mỗi chunk nên có `doc_id`, `title`, `doc_type`, `authority`, `status`, `effective_from`, `effective_to`, `verified_on`, `article`, `tags`, `source_url`.

## 6. Khi nguồn xung đột

Ưu tiên nguồn chính thức mới hơn và đang hiệu lực. Nếu vẫn không giải quyết được, trình bày xung đột và chuyển `needs_review`, không tự chọn theo số lượng chunk.

## 7. Yêu cầu đầu ra

Mỗi kết luận pháp lý phải có nguồn; bút toán phải nêu chế độ giả định; dữ liệu thiếu làm thay đổi kết luận phải được liệt kê; câu trả lời không đủ căn cứ phải nói rõ giới hạn.
