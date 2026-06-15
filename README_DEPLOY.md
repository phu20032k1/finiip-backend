# Finiip Backend — bản deploy

Backend FastAPI đã có lớp API ổn định cho frontend chat tại `/api/v1/chat`.

## Chạy local

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Kiểm tra:

- `http://localhost:8000/api/v1/health`
- `http://localhost:8000/api/v1/chat/status`
- `http://localhost:8000/docs`

## API frontend sử dụng

```text
POST   /api/v1/chat/conversations
GET    /api/v1/chat/conversations
GET    /api/v1/chat/conversations/{id}/messages
POST   /api/v1/chat/conversations/{id}/messages
DELETE /api/v1/chat/conversations/{id}
POST   /api/v1/chat/attachments
DELETE /api/v1/chat/attachments/{id}
POST   /api/v1/chat/messages/{id}/feedback
```

Frontend gửi hai header:

```text
X-User-ID: ID lưu trong trình duyệt
X-Workspace-ID: personal
```

Nếu bật `FINIIP_API_KEY`, frontend còn phải gửi `X-API-Key`. Không đưa secret thật vào frontend công khai.

## Deploy bằng Docker/Render

Thư mục đã có `Dockerfile`, `Procfile` và `render.yaml`.

Biến môi trường nên đặt:

```text
CORS_ORIGINS=https://TEN-FRONTEND.vercel.app
OPENAI_API_KEY=...
OPENAI_CHAT_MODEL=gpt-4o-mini
DATABASE_URL=postgresql://...
RAG_STORAGE_MODE=local
```

`DATABASE_URL` có thể để trống để chạy SQLite, nhưng dữ liệu có thể mất khi dịch vụ không có ổ đĩa bền vững. Production nên dùng PostgreSQL/Supabase.

Sau khi deploy, URL API gốc có dạng:

```text
https://TEN-BACKEND.onrender.com
```

Dùng URL đó trong `frontend/config.js`.
