# Finiip AI V3 — ưu tiên nâng cấp AI

Bản V3 tập trung nâng cấp lõi AI, chưa ưu tiên SaaS/phân quyền.

## AI V3 có gì mới?

1. **Explainable AI**  
   Mỗi kết quả AI có phần `explainable_ai` để giải thích vì sao AI chọn nhóm nghiệp vụ và tài khoản Nợ/Có.

2. **Confidence calibration**  
   AI vẫn giữ `confidence` gốc, nhưng thêm `calibrated_confidence` để trừ điểm khi có rủi ro như: thiếu tài khoản, VAT chưa rõ, thanh toán tiền mặt số tiền lớn, keyword mâu thuẫn.

3. **Risk flags**  
   Kết quả có danh sách `risk_flags`, ví dụ:
   - `LOW_CONFIDENCE`
   - `VAT_MENTIONED_BUT_NOT_MODELED`
   - `LARGE_CASH_PAYMENT`
   - `PAYMENT_METHOD_CONFLICT`
   - `UNKNOWN_ACCOUNTING_CASE`

4. **Quality gate**  
   AI tự quyết định workflow:
   - `AUTO_DRAFT_ALLOWED`: có thể tạo draft, vẫn nên duyệt trước khi posted
   - `REVIEW_REQUIRED`: cần kế toán duyệt
   - `BLOCK_AUTO_POSTING`: chặn tự ghi sổ

5. **Review questions**  
   AI tự tạo câu hỏi cho kế toán kiểm tra, ví dụ: “Hóa đơn có VAT không, thuế suất bao nhiêu?”

6. **AI V3 test suite**  
   Có endpoint test nhanh để chứng minh AI chạy ổn trên các nghiệp vụ mẫu.

## Endpoint mới

```text
POST /ai/v3/analyze
POST /ai/v3/batch-analyze
GET  /ai/v3/demo-cases
GET  /ai/v3/test-suite
```

## Cách test nhanh

Chạy backend:

```bash
uvicorn main:app --reload
```

Mở giao diện:

```text
http://127.0.0.1:8000/app
```

Ở phần **AI V3 Workbench**, bấm:

```text
Phân tích bằng AI V3
Chạy test suite AI V3
```

## Cách demo khi đi làm

Nên nói:

> AI của Finiip không tự ý ghi sổ. AI phân tích nghiệp vụ, giải thích lý do, chấm confidence, phát hiện rủi ro, rồi đưa vào hàng chờ duyệt nếu chưa đủ an toàn.

Không nên nói:

> AI thay kế toán hoàn toàn.

## Việc nên nâng cấp tiếp sau V3

1. Lưu kết quả người dùng duyệt đúng/sai rõ ràng hơn.
2. Tự đề xuất rule mới từ nhiều correction giống nhau.
3. Tách VAT thành bút toán nhiều dòng khi đủ dữ liệu hóa đơn.
4. Thêm bộ test case riêng cho từng ngành: bán hàng, dịch vụ, thương mại điện tử, xây dựng.
5. Đưa AI V3 vào import Excel hàng loạt để cảnh báo dòng nào cần kiểm tra.
