# Finiip Admin RAG V54-V59 Quality Upgrade

Bản nâng cấp này tập trung vào chất lượng trả lời sau khi Admin upload tài liệu vào Supabase RAG.

## V54 - Hybrid Search

`services/rag_storage_v101.py` đã nâng search từ lexical đơn giản sang hybrid nhẹ:

- giữ nguyên câu hỏi gốc;
- mở rộng query bằng synonym/ngữ cảnh kế toán/pháp lý;
- cộng điểm theo token overlap, phrase match, số liệu, Điều/Khoản/Mã số;
- trả thêm `score_breakdown` để debug trong Admin UI.

Không cần cài pgvector để chạy bản này.

## V55 - Rerank

Top chunks được rerank lại theo khả năng trả lời ở cấp câu/đoạn nhỏ. Mục tiêu là giảm tình trạng lấy đúng tài liệu nhưng sai đoạn.

## V56 - Citation theo Điều/Khoản/Phụ lục

Nguồn giờ cố gắng hiển thị:

```txt
Điều 6 (được sửa đổi, bổ sung) — trang 1 — chunk 1
```

thay vì chỉ:

```txt
trang 1
```

Bộ nhận diện hoạt động best-effort từ `heading`, `content`, và excerpt được chọn, không cần migrate database.

## V57 - Conversation Memory trong Admin tab

Admin UI lưu 6 lượt hỏi gần nhất trong `localStorage` của trình duyệt. Khi hỏi tiếp kiểu “điều đó”, “câu trước”, “cái trên”, phần history được gửi kèm backend để tăng khả năng hiểu ngữ cảnh.

Lưu ý: memory này chỉ để test trong tab trình duyệt, không lưu server.

## V58 - Formula Engine

Một số câu hỏi tính toán có số liệu sẽ được xử lý bằng engine công thức trước RAG, ví dụ:

```txt
Tính VAT 10% cho hóa đơn 11.000.000 đã gồm thuế
Tính khấu hao tài sản 120.000.000 trong 60 tháng
```

Nếu không phải câu tính toán, hệ thống quay lại RAG như bình thường.

## V59 - Long Answer Mode

Với câu hỏi dài hoặc có từ khóa như “chi tiết”, “quy trình”, “giải thích”, “toàn bộ”, câu trả lời sẽ có cấu trúc:

1. Kết luận nhanh
2. Căn cứ chính trong tài liệu
3. Cách hiểu / cách áp dụng
4. Nguồn

## Cách test nhanh

Sau khi chép patch:

```bash
uvicorn main:app --reload
```

Mở:

```txt
/admin/rag-ui?key=finiip&workspace_id=default
```

Nên bấm `Ctrl + F5` để tải JS mới.

Các câu test:

```txt
Thông tư 43/2026 sửa đổi thông tư nào?
Báo cáo tài chính hợp nhất năm phải nộp chậm nhất bao nhiêu ngày?
Hãy giải thích chi tiết thời hạn nộp báo cáo tài chính hợp nhất và căn cứ điều khoản nào?
Lợi ích cổ đông không kiểm soát được trình bày ở đâu?
Tính khấu hao tài sản 120.000.000 trong 60 tháng
```

## Test đã chạy

```bash
PYTHONPATH=. pytest -q tests/test_v100_rag_admin_ui.py tests/test_v101_supabase_intents.py
```

Kết quả:

```txt
8 passed
```
