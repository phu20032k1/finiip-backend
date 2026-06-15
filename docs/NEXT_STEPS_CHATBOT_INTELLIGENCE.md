# Finiip - Nâng cấp chatbot thông minh và nghiệp vụ hơn

## Những phần đã bổ sung
- `ai_intents.json`: định nghĩa intent và action.
- `accounting_rules.json`: rule nghiệp vụ để phân loại giao dịch và gợi ý tài khoản.
- `knowledge_base/*.md`: bộ tri thức kế toán, tài khoản, VAT/hóa đơn, quy trình nội bộ và FAQ.
- `data/sample_transactions.xlsx`: dữ liệu mẫu có nhãn để test phân loại.
- `demo_questions.md`: bộ câu hỏi dùng để demo và kiểm thử chatbot.
- `finiip_v25_v40.py`: nâng cấp endpoint `/ai/v41/chat` để xử lý greeting, help, phân loại giao dịch, gợi ý bút toán, kiểm tra rủi ro và hỏi kiến thức cơ bản.

## Luồng xử lý mới
Người dùng hỏi → detect intent → chọn nhánh xử lý:
- greeting/help → trả lời template
- transaction/journal/tax risk → đọc `accounting_rules.json`
- report → đọc dữ liệu hiện có trong store/database
- knowledge → tìm trong `knowledge_base`
- unknown → hỏi lại thông tin còn thiếu

## Việc nên làm tiếp
1. Chạy backend và test `/ai/v41/chat` bằng 30 câu trong `demo_questions.md`.
2. Import `data/sample_transactions.xlsx` qua endpoint import nếu cần dữ liệu demo.
3. Bổ sung thêm rule vào `accounting_rules.json` dựa trên nghiệp vụ thật.
4. Bổ sung tài liệu thuế/kế toán chuẩn vào `knowledge_base` rồi index vào RAG nếu đã có pipeline vector.
5. Tạo bảng `ai_feedback` để lưu câu trả lời bị sửa và cải thiện rule/model.

## Lưu ý an toàn
AI chỉ nên gợi ý bút toán và cảnh báo rủi ro. Việc ghi sổ chính thức vẫn cần kế toán xác nhận.
