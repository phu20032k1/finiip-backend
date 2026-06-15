# Finiip V25-V40 Productization Pack

Bản này nâng Finiip từ prototype AI kế toán sang bản MVP có thể dùng thử theo quy trình an toàn: AI tạo nháp, kế toán duyệt, rồi mới ghi sổ.

## Các phiên bản đã thêm

- V25 Auto Journal Draft: `POST /ai/v25/journal-draft/create`, `GET /ai/v25/journal-draft/list`, approve/reject draft.
- V26 Sổ cái / Nhật ký chung: `POST /ledger/post-entry`, `GET /ledger/general-journal`, `GET /ledger/general-ledger`.
- V27 Xuất Excel: `GET /reports/v27/export-excel`.
- V28 Báo cáo VAT: `GET /reports/vat`, `GET /reports/vat/export`.
- V29 Báo cáo kết quả kinh doanh: `GET /reports/income-statement`.
- V30 Dashboard tài chính: `GET /dashboard/v30/financial`, `GET /v30/financial-dashboard-ui`.
- V31 AI giải thích bút toán: `POST /ai/v31/explain-journal`.
- V32 AI phát hiện lỗi kế toán: `POST /ai/v32/detect-accounting-errors`.
- V33 AI hỏi lại khi thiếu thông tin: `POST /ai/v33/missing-info-questions`.
- V34 OCR hóa đơn nâng cao từ text: `POST /ocr/v34/invoice-enhanced/text`.
- V35 Hóa đơn → bút toán nháp: `POST /ai/v35/invoice-to-journal-draft`.
- V36 User / Role MVP: `POST /admin/v36/users`, `GET /admin/v36/users`.
- V37 Login / token MVP: `POST /auth/v37/login`.
- V38 Database health: `GET /system/v38/database-health`.
- V39 Audit log: `GET /audit/v39/logs`.
- V40 Backup / Restore: `POST /backup/v40/create`, `GET /backup/v40/download/{backup_name}`, `POST /backup/v40/restore`.

## Luồng chạy thử nhanh

1. Tạo journal draft:

```bash
curl -X POST http://127.0.0.1:8000/ai/v25/journal-draft/create \
  -H "Content-Type: application/json" \
  -d '{"description":"Mua máy tính 20 triệu có VAT","amount":20000000,"vat_rate":0.1,"payment_method":"bank"}'
```

2. Approve draft:

```bash
curl -X POST http://127.0.0.1:8000/ai/v25/journal-draft/DRAFT-00001/approve -H "Content-Type: application/json" -d '{}'
```

3. Post vào nhật ký chung:

```bash
curl -X POST http://127.0.0.1:8000/ledger/post-entry \
  -H "Content-Type: application/json" \
  -d '{"draft_id":"DRAFT-00001"}'
```

4. Xem dashboard:

```text
http://127.0.0.1:8000/v30/financial-dashboard-ui
```

5. Tạo backup:

```bash
curl -X POST http://127.0.0.1:8000/backup/v40/create
```

## Lưu ý

V25-V40 là MVP chạy được, chưa phải hệ thống kế toán production. Trước khi dùng thật cần kiểm thử nghiệp vụ, phân quyền thật, bảo mật token, migration database và audit theo chuẩn doanh nghiệp.
