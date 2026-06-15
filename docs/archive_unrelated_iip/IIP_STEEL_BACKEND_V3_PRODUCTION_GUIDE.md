# Finiip + IIP Steel Backend V3 Production Guide

## V3 thêm gì

V3 nâng backend từ bản demo API lên khung production:

- JWT-like auth tự triển khai bằng chuẩn HMAC SHA256, không cần thêm thư viện JWT.
- RBAC theo role: admin, chairman, accounting, sales, warehouse, driver, dealer.
- Audit log cho login, import, tạo đơn, cập nhật trạng thái, scheduler.
- Import Excel theo 2 bước: preview/validate rồi commit.
- Scheduler tick để tạo báo cáo sáng 6h30.
- Notification channel config cho Telegram/Zalo/Email/Webhook ở mức backend skeleton.
- Backup JSON toàn bộ dữ liệu IIP Steel.
- Dockerfile + docker-compose PostgreSQL.

## Chạy local bằng SQLite

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Seed demo V3:

```bash
curl -X POST http://127.0.0.1:8000/iip/demo/seed-v3
```

Login:

```bash
curl -X POST http://127.0.0.1:8000/iip/v3/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

Dùng token trả về:

```bash
curl http://127.0.0.1:8000/iip/v3/status \
  -H "Authorization: Bearer <TOKEN>"
```

## Chạy bằng Docker + PostgreSQL

```bash
docker compose up --build
```

Mở Swagger:

```text
http://127.0.0.1:8000/docs
```

## Luồng import Excel production

1. Tải template từ API V2:

```text
GET /iip/import/template/dealers
GET /iip/import/template/debts
GET /iip/import/template/orders
```

2. Preview file:

```text
POST /iip/v3/import/{data_type}/preview
```

3. Nếu valid thì commit:

```text
POST /iip/v3/import/{batch_code}/commit
```

## Các API V3 chính

```text
GET  /iip/v3/status
POST /iip/v3/auth/bootstrap-admin
POST /iip/v3/auth/login
GET  /iip/v3/auth/me
POST /iip/v3/users
GET  /iip/v3/users
POST /iip/v3/import/{data_type}/preview
POST /iip/v3/import/{batch_code}/commit
POST /iip/v3/orders
PATCH /iip/v3/orders/{order_code}/status
POST /iip/v3/reports/scheduler/tick
GET  /iip/v3/audit-logs
GET  /iip/v3/backup/export
GET  /iip/v3/deployment/checklist
```

## Mức hoàn thiện sau V3

- Backend logic theo kế hoạch IIP Giai đoạn 1: khoảng 86-88%.
- Sẵn sàng demo kỹ thuật có auth/import/audit: khoảng 90%.
- Sẵn sàng triển khai thật: khoảng 70-75%, còn cần frontend, notification thật, migration Alembic và kiểm thử dữ liệu thật.

## Việc tiếp theo

Sau V3 nên làm frontend:

1. Dashboard Chủ tịch.
2. Màn import Excel cho kế toán.
3. Màn AI hỏi đáp dữ liệu thật.
4. Màn đơn hàng/công nợ/đại lý.
5. Màn kho/tài xế mobile.
