# V67 - File Reader & Return File

V67 bổ sung luồng **đọc file tạm và trả file kết quả** trong Admin RAG UI.

## Mục tiêu

- Admin upload một file tạm để Finiip đọc/xử lý.
- Hệ thống tạo file kết quả để tải xuống.
- File tạm **không tự động đưa vào RAG chính thức**.
- Muốn đưa tài liệu vào tri thức RAG thì vẫn dùng form **Upload & Index** riêng.

## Đường dẫn

Admin UI:

```txt
/admin/rag-ui?key=YOUR_ADMIN_KEY&workspace_id=default
```

Tính năng mới nằm trong panel:

```txt
V67 Đọc file & trả file kết quả
```

Download file kết quả:

```txt
/admin/rag-ui/file/download?key=YOUR_ADMIN_KEY&job_id=<job_id>
```

## Kiểu xử lý

```txt
summary           Tóm tắt tài liệu
extract           Đọc & trích xuất text
qa                Trả lời câu hỏi theo file
accounting_review Review kế toán/kiểm soát
questions         Tạo câu hỏi ôn tập + đáp án
```

## Định dạng trả về

```txt
.docx
.xlsx
.md
.txt
.json
.csv
```

## File hỗ trợ

Dùng chung parser với RAG admin:

```txt
PDF, DOCX, TXT, MD, CSV, JSON, XLSX, XLSM, HTML
```

## Lưu file kết quả

Kết quả được lưu local tại:

```txt
data/admin_file_outputs/
```

Mỗi lần xử lý sẽ sinh:

```txt
file_<job_id>.<format>
file_<job_id>.json.meta
```

## Lưu ý bảo mật

- Endpoint download yêu cầu admin key.
- `job_id` được sanitize để tránh path traversal.
- Tính năng này không upload file vào Supabase RAG Storage.
- Đây là luồng xử lý tạm, phù hợp để đọc file người dùng đưa vào và trả lại file kết quả.

## Test nhanh

1. Mở Admin UI.
2. Chọn panel **V67 Đọc file & trả file kết quả**.
3. Upload PDF/DOCX/XLSX.
4. Chọn `Review kế toán/kiểm soát`.
5. Chọn output `Word .docx`.
6. Bấm **Đọc file & tạo file kết quả**.
7. Tải file kết quả.
