# Finiip V16 - Large AI Training Pack

Bản V16 tập trung vào việc cho AI học nhiều dữ liệu hơn để backend dùng API ổn định hơn cho frontend.

## Đã thêm gì?

- `data/ai_training_examples_v2_large.json`: 2.220 mẫu giao dịch/hóa đơn mô phỏng.
- `data/ai_training_examples_v3_curated.json`: 304 mẫu ưu tiên để giảm nhầm lẫn nghiệp vụ.
- Cập nhật `scripts/seed_and_train_ai.py` để tự nạp **tất cả** file `data/ai_training_examples*.json`.
- Cập nhật `POST /ai/ml/seed-and-train` để seed toàn bộ dataset thay vì chỉ đọc file V1.
- Model đã được train sẵn tại `ai_models/transaction_classifier.json`.

## Tổng dữ liệu học hiện tại

- Dataset V1: 182 mẫu.
- Dataset V2 large: 2.220 mẫu.
- Dataset V3 curated: 304 mẫu.
- Tổng trong model đã train: khoảng 2.540 ví dụ, gồm cả dữ liệu cũ trong DB.

## Cách cho AI học lại

```bash
cd copy
python scripts/seed_and_train_ai.py
```

Hoặc qua API:

```bash
curl -X POST http://127.0.0.1:8000/ai/ml/seed-and-train
```

## Test AI đã học

```bash
curl -X POST http://127.0.0.1:8000/ai/ml/predict \
  -H "Content-Type: application/json" \
  -d '{"description":"Nộp thuế TNDN quý 2","amount":10000000}'
```

Kết quả tốt nên ra:

```json
{
  "category": "Thuế và phí",
  "debit_account_code": "3334",
  "credit_account_code": "112",
  "source": "ml_model"
}
```

## Lưu ý

Dữ liệu V16 là dữ liệu mẫu/synthetic để AI học nhanh hơn. Khi có dữ liệu thật từ doanh nghiệp, hãy import thêm và dùng `/ai/feedback` để sửa các kết quả sai. Dữ liệu thật sẽ quan trọng hơn dữ liệu mẫu.
