# Finiip V109 — Smart Chat, Memory, Calculation & Clean Sources

## Những phần đã nâng

1. **Nhận diện Finiip và lời chào**
   - `xin chào` → giới thiệu: Finiip là trợ lý AI thuộc CTCP IIP Việt Nam.
   - `bạn là ai`, `Finiip là ai` → trả lời đúng danh tính.
   - `bạn có thể làm gì` → liệt kê kế toán, thuế, tính toán, báo cáo, đọc file, RAG và hỗ trợ hệ thống.

2. **Nguồn không còn nằm xấu trong bong bóng trả lời**
   - Không còn dòng như `Nguồn nội bộ: knowledge_base/accounting_accounts.md` trong `answer`.
   - Backend trả nguồn riêng qua `citations` và `source_cards`.
   - Tên kỹ thuật được đổi thành tên đẹp, ví dụ `Hệ thống tài khoản kế toán Finiip`.

3. **Nhớ ngữ cảnh tốt hơn**
   - Nhận cả hai định dạng lịch sử: `Q:/A:` và `user:/assistant:`.
   - Tăng lịch sử gần nhất lên tối đa khoảng 10.000 ký tự (có thể chỉnh bằng env).
   - Hiểu câu nối tiếp như `còn 112 thì sao?`, `vậy nếu chuyển khoản?`, `trường hợp trên thì sao?`.

4. **Tính toán chính xác hơn**
   - Sửa lỗi câu `Tính VAT 10% của 100 triệu` bị hiểu 10% là số tiền.
   - Kết quả đúng: VAT 10 triệu, tổng thanh toán 110 triệu.
   - Giữ engine VAT, khấu hao/phân bổ và nghiệp vụ định khoản.

5. **Trả lời rộng và tự nhiên hơn khi có LLM**
   - Khi có `OPENAI_API_KEY`, backend tự dùng LLM cho câu hỏi tổng quát, câu hỏi dài và câu có nguồn RAG.
   - LLM không được tự bịa điều luật, thuế suất, thời hạn hoặc mức phạt.
   - Với tài liệu RAG, nguồn vẫn được giữ riêng để frontend hiển thị bằng thẻ.

6. **Tận tâm hơn**
   - Câu trả lời có lời gợi ý tiếp theo theo ngữ cảnh, ví dụ hỗ trợ lập bút toán, kiểm tra chứng từ hoặc chuyển nội dung thành báo cáo/checklist.

## Biến môi trường cần đặt trên Render

```env
OPENAI_API_KEY=sk-...
OPENAI_CHAT_MODEL=gpt-4o-mini
FINIIP_LLM_MODE=auto
FINIIP_CHAT_CONTEXT_CHARS=10000
```

`FINIIP_LLM_MODE`:
- `auto`: dùng LLM cho câu hỏi tổng quát, câu dài hoặc câu có nguồn.
- `always`: dùng LLM cho phần lớn câu hỏi, trừ công thức và hội thoại đơn giản.
- `off`: chỉ dùng engine nội bộ/RAG, không gọi LLM.

## API frontend nên dùng

`POST /api/v1/chat/conversations/{conversation_id}/messages`

Frontend hiển thị:
- Nội dung chính: `response.message.content`
- Nguồn đẹp: `response.source_cards`
- Không nối tên file/path vào nội dung chính.

Ví dụ `source_cards`:

```json
[
  {
    "index": 1,
    "title": "Hệ thống tài khoản kế toán Finiip",
    "badge": "Nguồn nội bộ",
    "location": "Kho kiến thức Finiip",
    "excerpt": "..."
  }
]
```

Gợi ý UI: chỉ hiện nút `1 nguồn tham khảo`; khi bấm mới mở danh sách thẻ nguồn.

## Test nhanh

```bash
pytest -q tests/test_v109_smart_chat.py
```

Các câu nên test trên giao diện:

```text
xin chào
bạn là ai
bạn có thể làm gì
tài khoản 111 là gì
còn 112 thì sao?
Tính VAT 10% của 100 triệu
Hãy phân tích chi tiết quy trình mua hàng chưa thanh toán và nêu bút toán, chứng từ, rủi ro
```
