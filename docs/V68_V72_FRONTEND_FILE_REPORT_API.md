# V68–V72 Frontend File Reader & Report API

Mục tiêu: frontend cho người dùng upload tài liệu, Finiip đọc nội dung file, tạo báo cáo và trả lại file kết quả để tải xuống. Luồng này **không nạp file vào RAG chính thức**. Nếu muốn nạp tài liệu làm tri thức lâu dài, dùng Admin Upload & Index riêng.

## Tính năng đã thêm

- **V68 Public frontend API**: endpoint cho frontend gọi trực tiếp bằng `X-API-Key`.
- **V69 Async job_id**: upload file lớn không bị timeout; frontend poll trạng thái.
- **V70 History**: lưu lịch sử job đã xử lý theo `workspace_id` / `user_id`.
- **V71 PDF export**: hỗ trợ trả file `.pdf` ngoài `.docx`, `.xlsx`, `.md`, `.txt`, `.json`, `.csv`.
- **V72 Multi-file**: upload nhiều file cùng lúc để tạo báo cáo tổng hợp.

## Bảo mật

Nếu có `FINIIP_API_KEY`, frontend phải gửi header:

```http
X-API-Key: <FINIIP_API_KEY>
```

Nếu local dev chưa set `FINIIP_API_KEY`, endpoint mở để test nhanh.

## Endpoint nhanh cho file nhỏ

```http
POST /ai/v68/file-report/create-sync
Content-Type: multipart/form-data
```

Form fields:

| Field | Kiểu | Ghi chú |
|---|---|---|
| `file` | file | Một file |
| `files` | file[] | Nhiều file, dùng field name `files` |
| `instruction` | string | Yêu cầu xử lý |
| `question` | string | Câu hỏi cụ thể nếu task `qa` |
| `task_type` | string | `auto_report`, `summary`, `accounting_review`, `legal_review`, `financial_report`, `qa`, `extract`, `study_questions` |
| `output_format` | string | `docx`, `xlsx`, `pdf`, `md`, `txt`, `json`, `csv` |
| `report_style` | string | `short`, `standard`, `detailed`, `executive`, `accounting_manager` |
| `workspace_id` | string | Workspace của user |
| `user_id` | string | ID user frontend |
| `title` | string | Tiêu đề báo cáo |
| `return_file` | boolean | `true` trả thẳng file; `false` trả JSON có `job_id` |

Ví dụ JavaScript trả thẳng file:

```js
const formData = new FormData();
formData.append("file", selectedFile);
formData.append("instruction", "Đọc tài liệu này và lập báo cáo phân tích kế toán chi tiết");
formData.append("task_type", "accounting_review");
formData.append("output_format", "docx");
formData.append("report_style", "accounting_manager");
formData.append("workspace_id", "default");
formData.append("user_id", "user_001");
formData.append("return_file", "true");

const res = await fetch("/ai/v68/file-report/create-sync", {
  method: "POST",
  headers: { "X-API-Key": FINIIP_API_KEY },
  body: formData,
});

const blob = await res.blob();
const url = URL.createObjectURL(blob);
const a = document.createElement("a");
a.href = url;
a.download = "finiip_report.docx";
a.click();
URL.revokeObjectURL(url);
```

## Endpoint job cho file lớn

### 1. Tạo job

```http
POST /ai/v69/file-report/jobs
Content-Type: multipart/form-data
```

Ví dụ upload nhiều file:

```js
const formData = new FormData();
for (const file of selectedFiles) {
  formData.append("files", file);
}
formData.append("instruction", "Đọc tất cả file và tạo báo cáo tổng hợp cho ban giám đốc");
formData.append("task_type", "auto_report");
formData.append("output_format", "pdf");
formData.append("report_style", "executive");
formData.append("workspace_id", "default");
formData.append("user_id", "user_001");

const res = await fetch("/ai/v69/file-report/jobs", {
  method: "POST",
  headers: { "X-API-Key": FINIIP_API_KEY },
  body: formData,
});
const job = await res.json();
console.log(job.job_id, job.status_url, job.download_url);
```

### 2. Poll trạng thái

```http
GET /ai/v69/file-report/jobs/{job_id}
```

Frontend poll tới khi:

```json
{
  "status": "done",
  "download_url": "/ai/v69/file-report/jobs/fr_xxx/download"
}
```

### 3. Tải file kết quả

```http
GET /ai/v69/file-report/jobs/{job_id}/download
```

## Lịch sử xử lý

```http
GET /ai/v70/file-report/history?workspace_id=default&user_id=user_001&limit=50
```

Xóa mềm:

```http
DELETE /ai/v70/file-report/history/{job_id}
```

Xóa cứng cả thư mục input/output:

```http
DELETE /ai/v70/file-report/history/{job_id}?hard_delete=true
```

## Kiểm tra năng lực

```http
GET /ai/v68/file-report/capabilities
```

Trả về danh sách format, task type, giới hạn dung lượng và endpoint hỗ trợ.

## Giới hạn mặc định

Có thể cấu hình bằng env:

```env
FINIIP_FILE_REPORT_MAX_MB=50
FINIIP_FILE_REPORT_MAX_FILES=10
```

## Gợi ý UI frontend

Nên có 2 khu vực rõ ràng:

1. **Nạp vào tri thức Finiip**: dùng RAG Upload & Index, dành cho admin/tài liệu chính thức.
2. **Đọc file và tạo báo cáo**: dùng V68–V72, dành cho user upload file một lần rồi tải báo cáo.

