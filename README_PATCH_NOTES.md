# Bản đã dọn nhanh để chạy/deploy an toàn hơn

## Đã sửa

1. Không đóng gói file `.env` thật vào ZIP.
2. Thêm `.gitignore` để tránh commit secret, database local, cache Python.
3. Thêm `.env.local.example` để copy thành `.env` khi chạy local.
4. Sửa CORS trong `main.py` để đọc từ biến môi trường `CORS_ORIGINS`.
   - Local: `CORS_ORIGINS=*`
   - Deploy: `CORS_ORIGINS=https://domain-frontend-cua-ban.vercel.app`

## Cách chạy local

```bash
cd copy18_fixed
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.local.example .env
uvicorn main:app --reload
```

macOS/Linux:

```bash
cd copy18_fixed
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.local.example .env
uvicorn main:app --reload
```

## Endpoint nên test

- `GET /api/v1/health`
- `GET /ai/v68/rag/health`
- `POST /ai/v68/rag/init-schema`
- `POST /ai/v66/rag/upload-file`
- `POST /ai/v69/rag/answer`

## Lưu ý bảo mật

Nếu file `.env` cũ từng chứa key thật và đã gửi lên đâu đó, nên đổi lại Supabase service role key/database password/API key.


## V81 backend update

Đã thêm backend RAG Sources & Metadata:

- Upload RAG nhận metadata: số văn bản, ngày ban hành, ngày hiệu lực, cơ quan ban hành, trạng thái, version, workspace/user.
- Supabase schema tự nâng cấp thêm metadata columns và indexes.
- `/ai/v69/rag/answer` trả về `citations` và `sources` giàu thông tin hơn.
- `/ai/v70/rag/documents` lọc thêm `workspace_id`, `user_id`, `status`.
- Thêm hướng dẫn tại `docs/V81_RAG_SOURCES_METADATA_GUIDE.md`.


## V85 - Full Accounting AI Core

Đã thêm core AI kế toán đầy đủ tại `services/accounting_ai_full.py`, endpoint `/ai/accounting/*`, playbook RAG `knowledge_base/accounting_full_playbook_v85.md`, seed training `data/accounting_training_examples_full_v85.json`, và test `tests/test_v85_accounting_ai_full.py`.

Chạy kiểm tra:

```bash
python -m pytest -q tests/test_v85_accounting_ai_full.py
```

## V100 — Backend RAG Admin UI

Thêm giao diện HTML trắng đơn giản ngay trong FastAPI backend để Admin/Owner upload và quản lý tài liệu RAG chính thức.

Mở local:

```txt
http://localhost:8000/admin/rag-ui
```

Khi deploy nên đặt:

```bash
FINIIP_ADMIN_KEY="your-strong-admin-key"
```

Sau đó mở:

```txt
https://your-backend-domain.com/admin/rag-ui?key=your-strong-admin-key&workspace_id=default
```

Xem chi tiết: `docs/V100_BACKEND_RAG_ADMIN_UI_GUIDE.md`.

## V68–V72 File Reader & Report API

Đã thêm API cho frontend upload file để Finiip đọc và trả file báo cáo:

- V68: `POST /ai/v68/file-report/create-sync` cho file nhỏ / trả ngay.
- V69: `POST /ai/v69/file-report/jobs` tạo `job_id` xử lý file lớn không timeout.
- V70: `GET /ai/v70/file-report/history` xem lịch sử xử lý theo workspace/user.
- V71: output `.pdf` ngoài `.docx`, `.xlsx`, `.md`, `.txt`, `.json`, `.csv`.
- V72: upload nhiều file cùng lúc bằng field `files`.

Chi tiết frontend: `docs/V68_V72_FRONTEND_FILE_REPORT_API.md`.
