# AI V48 - Global Legal RAG Starter

Bản này đã được chèn thêm module RAG luật/thông tư mẫu vào project.

## File đã thêm

```text
knowledge_base/global/legal/tai_san_co_dinh.md
knowledge_base/global/legal/chi_phi_duoc_tru.md
knowledge_base/global/accounting/cong_cu_dung_cu.md
scripts/index_global_knowledge.py
scripts/ask_global_rag.py
scripts/legal_prompt.py
```

## Mục tiêu

Cho AI có kho kiến thức nền để trả lời các câu hỏi về:

- tài sản cố định
- công cụ dụng cụ
- chi phí được trừ
- hạch toán cơ bản liên quan

Đây là bản RAG offline bằng keyword search để test luồng trước. Sau khi ổn, có thể đổi phần search sang ChromaDB/FAISS/Qdrant.

## Cách chạy

Mở terminal tại thư mục gốc project, sau đó chạy:

```bash
python scripts/index_global_knowledge.py
```

Nếu thành công sẽ thấy:

```text
✅ Đã index ... chunks
📄 File index: .../data/rag_index.json
```

Sau đó test hỏi RAG:

```bash
python scripts/ask_global_rag.py "Mua laptop 18 triệu có hóa đơn VAT, thanh toán chuyển khoản, có được ghi nhận tài sản cố định không?"
```

Test câu khác:

```bash
python scripts/ask_global_rag.py "Chi phí quảng cáo Facebook có được tính vào chi phí được trừ không?"
```

## Kết quả in ra gồm 3 phần

### 1. TOP CHUNKS

Các đoạn kiến thức liên quan mà RAG tìm được.

### 2. OFFLINE DEMO ANSWER

Câu trả lời demo không cần API AI.

### 3. PROMPT GỬI CHO AI

Prompt hoàn chỉnh để đưa vào AI engine/chatbot. Khi tích hợp thật, lấy prompt này gửi cho LLM.

## Cách mở rộng tài liệu

Thêm file `.md` vào:

```text
knowledge_base/global/legal/
knowledge_base/global/accounting/
```

Sau đó chạy lại:

```bash
python scripts/index_global_knowledge.py
```

## Nguyên tắc trả lời luật/thông tư

AI không được bịa căn cứ. Nếu RAG không tìm thấy tài liệu liên quan, phải nói:

```text
Chưa đủ căn cứ để kết luận.
```

Format trả lời chuẩn:

```text
## 1. Kết luận ngắn
## 2. Căn cứ từ tài liệu RAG
## 3. Diễn giải dễ hiểu
## 4. Áp dụng vào tình huống
## 5. Rủi ro/lưu ý
## 6. Thông tin còn thiếu
## 7. Kết luận cuối
```
