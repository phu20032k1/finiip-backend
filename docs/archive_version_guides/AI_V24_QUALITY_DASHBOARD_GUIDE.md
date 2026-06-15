# Finiip V24 - Dashboard chất lượng AI kế toán

V24 bổ sung dashboard để kiểm soát chất lượng AI trước khi đi tiếp sang tự động hóa bút toán.

## API mới

```text
GET /ai/v24/quality-dashboard
```

Trả về các nhóm số liệu:

- `summary`: tổng item review, pending, feedback examples, avg confidence, quality score
- `rates`: pending/approved/corrected/rejected rate
- `status_counts`: số lượng theo trạng thái review queue
- `priority_counts`: số lượng theo priority high/medium/low
- `confidence_buckets`: confidence thấp/trung bình/cao
- `journal_counts`: draft/posted journal entries
- `model`: trạng thái model Naive Bayes tự viết
- `recommendations`: gợi ý vận hành tiếp theo

## UI mới

```text
GET /v24/quality-dashboard-ui
```

Mở dashboard HTML trực tiếp trong trình duyệt.

## Luồng dùng đề xuất

1. Tạo review item ở V19 hoặc từ màn hình V23.
2. Kế toán approve/correct/reject.
3. Mở V24 để xem tỷ lệ sai/sửa/confidence.
4. Nếu corrected rate cao, gọi:

```text
POST /ai/v20/retrain-from-feedback
```

5. Khi dashboard ổn định hơn, chuyển sang V25 - Auto Journal Draft Flow.

## Vì sao cần V24?

V22 đã sinh được bút toán kép, V23 đã duyệt được kết quả AI. Nhưng trước khi để AI tạo bút toán nhiều hơn, cần dashboard đo chất lượng để tránh ghi sổ sai hàng loạt.
