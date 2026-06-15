# V111 – Legal RAG citation and document-binding fix

## Đã sửa

1. Đọc DOCX đúng thứ tự khối XML (đoạn văn và bảng), không còn đẩy bảng đầu văn bản xuống cuối.
2. Nhận diện đúng số văn bản của chính tài liệu theo thứ tự ưu tiên: dòng `Số:` → tiêu đề → tên tệp → phần mở đầu.
3. Citation không còn lấy nhầm văn bản được viện dẫn trong phần căn cứ, ví dụ `88/2015/QH`.
4. Câu hỏi có đại từ như “Thông tư này”, “văn bản này” được ràng buộc vào tài liệu pháp lý mới nhất trong workspace.
5. Tách và trả lời riêng các câu hỏi bị dán liền nhau; mỗi ý có nguồn riêng.
6. Bổ sung intent “đối tượng áp dụng” để không nhầm với “thời điểm áp dụng/hiệu lực”.
7. Giảm lặp tiêu đề điều trong phần trả lời trực tiếp.

## Tệp thay đổi

- `services/rag_v66_v67.py`
- `services/rag_storage_v101.py`
- `services/accounting_ai_enterprise.py`
- `tests/test_v111_legal_rag_citation_fix.py`

## Sau khi triển khai

Vào Admin RAG và **Re-index** tài liệu đã tải lên trước đây để tạo lại nội dung chunk và metadata theo bộ đọc DOCX mới.

Các câu kiểm thử:

- `Thông tư này áp dụng cho những đối tượng nào?`
- `Thông tư này có dùng để xác định nghĩa vụ thuế không?`
- `Tổ chức phát hành tài sản mã hóa hạch toán như thế nào?`

Citation mong đợi: `Thông tư 15/2026/TT-BTC`, không phải `88/2015/QH`.
