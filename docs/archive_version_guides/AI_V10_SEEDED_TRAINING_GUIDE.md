# Finiip V10 - AI đã có dữ liệu học mẫu

Bản này đã được nạp sẵn dữ liệu học mẫu và đã train model ML.

## Trạng thái hiện tại

- Dataset mẫu: `data/ai_training_examples_v1.json`
- Số ví dụ mẫu: 182
- Số nhóm nhãn kế toán mẫu: 21+
- Model đã train: `ai_models/transaction_classifier.json`
- Script train nhanh: `scripts/seed_and_train_ai.py`

## Chạy lại train nếu cần

```bash
cd copy
python scripts/seed_and_train_ai.py
```

Script này sẽ tự tạo tài khoản mặc định, nạp dữ liệu học mẫu, bỏ qua dữ liệu đã tồn tại và train lại model.

## Cách test nhanh

Chạy server:

```bash
uvicorn main:app --reload
```

Kiểm tra model:

```bash
curl http://127.0.0.1:8000/ai/ml/status
```

Dự đoán bằng model:

```bash
curl -X POST http://127.0.0.1:8000/ai/ml/predict \
  -H "Content-Type: application/json" \
  -d '{"description":"Chạy quảng cáo Facebook cho sản phẩm mới","amount":2000000}'
```

Hoặc dùng endpoint tự nạp và train:

```bash
curl -X POST http://127.0.0.1:8000/ai/ml/seed-and-train
```

Nếu kết quả có:

```json
"source": "ml_model"
```

thì AI đang dùng model học máy, không chỉ rule-based.

## Cách làm cho AI học tiếp

Mỗi khi AI đoán sai, dùng `/ai/teach` hoặc `/ai/teach-batch` để nhập đáp án đúng, sau đó gọi:

```bash
curl -X POST http://127.0.0.1:8000/ai/ml/train
```

Dữ liệu càng nhiều thì model càng ổn. Mục tiêu tiếp theo nên là 500-1000 ví dụ thật từ giao dịch kế toán.
