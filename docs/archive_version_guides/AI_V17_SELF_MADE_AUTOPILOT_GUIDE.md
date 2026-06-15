# Finiip V17 - Self-made AI Accounting Autopilot

Bản V17 nâng Finiip theo hướng **AI tự làm**, không dùng OpenAI, không Ollama, không LLM ngoài.

## Mục tiêu

V16 đã có dữ liệu học lớn và model Naive Bayes tự viết. V17 thêm một lớp sản phẩm để AI dùng được an toàn hơn:

- So sánh kết quả từ rule-based, correction memory và ML model.
- Chỉ cho `auto_approve` khi confidence cao và không có xung đột.
- Đưa case yếu vào `needs_review` hoặc `reject_or_teach`.
- Sinh giải thích ngắn cho kế toán hiểu vì sao AI chọn bút toán.
- Tạo payload mẫu để dạy lại AI qua `/ai/teach`.

## API mới

```text
POST /ai/v17/autopilot-analyze
GET  /ai/v17/upgrade-status
```

## Test nhanh

```bash
curl -X POST http://127.0.0.1:8000/ai/v17/autopilot-analyze \
  -H "Content-Type: application/json" \
  -d '{"description":"Thanh toán quảng cáo Facebook tháng 5", "amount":3000000}'
```

## Ý nghĩa action

| Action | Nghĩa |
|---|---|
| `auto_approve` | AI đủ tự tin để frontend có thể cho áp dụng nhanh |
| `needs_review` | Cần kế toán kiểm tra trước khi ghi sổ |
| `reject_or_teach` | Không nên dùng trực tiếp, cần sửa/dạy thêm |

## Vì sao đây là nâng cấp quan trọng?

Trước V17, AI có thể trả lời đúng nhưng hệ thống chưa biết khi nào nên tin. V17 biến AI từ “đoán kết quả” thành “quy trình kiểm soát AI”, phù hợp hơn với kế toán vì kế toán cần kiểm chứng, audit và giảm rủi ro sai bút toán.

## Trạng thái cấp độ

Sau V17, Finiip vẫn chưa phải ChatGPT kế toán Cấp 6, nhưng đã là **Cấp 3+ thực tế**:

```text
Rule-based + ML tự train + feedback loop + OCR parser + accounting engine + autopilot safety layer
```

Bước tiếp theo hợp lý: nâng OCR thực chiến và tạo màn hình review/dạy AI cho người dùng cuối.
