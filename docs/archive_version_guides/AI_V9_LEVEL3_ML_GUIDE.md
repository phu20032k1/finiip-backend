# Finiip V9 - Nâng cấp AI Cấp 3 thật

## Mục tiêu

Đưa Finiip từ **Cấp 2.5 / Cấp 3 nhẹ** lên **Cấp 3 thật** bằng cách thêm model học máy có thể train lại từ dữ liệu người dùng sửa.

## Thành phần mới

### 1. `ai_ml.py`

Module học máy thuần Python, triển khai Multinomial Naive Bayes cho mô tả giao dịch kế toán.

Model học 4 thông tin cùng lúc:

- danh mục giao dịch,
- loại giao dịch: income / expense / unknown,
- tài khoản Nợ,
- tài khoản Có.

### 2. Dataset từ correction

Nguồn dữ liệu train lấy từ bảng `ai_corrections`, được tạo khi:

- người dùng sửa giao dịch qua `/ai/transactions/{id}/correct`,
- người dùng dạy AI trực tiếp qua `/ai/teach`,
- người dùng dạy hàng loạt qua `/ai/teach-batch`.

### 3. API mới

- `GET /ai/ml/dataset`
- `GET /ai/ml/status`
- `POST /ai/ml/train`
- `POST /ai/ml/predict`

### 4. Luồng phân tích mới

`/ai/analyze` sử dụng thứ tự ưu tiên:

1. `learning_memory`: nếu có ví dụ correction rất giống.
2. `ml_model`: nếu model ML đã train và confidence đủ cao.
3. `rule_based`: fallback an toàn nếu chưa đủ dữ liệu.

## Khi nào được xem là Cấp 3?

Khi bạn đã có dữ liệu correction/teaching, gọi `/ai/ml/train`, sau đó `/ai/analyze` hoặc `/ai/ml/predict` trả về:

```json
"source": "ml_model"
```

Lúc đó Finiip không chỉ dùng rule nữa, mà đã có model tự học từ dữ liệu gán nhãn.

## Lệnh kiểm tra

```bash
pip install -r requirements.txt
pytest
```

Kết quả mong muốn:

```text
8 passed
```
