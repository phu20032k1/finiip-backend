# V66 - File Upload Router

Mục tiêu: tách rõ 2 luồng upload khi deploy:

1. **Tài liệu nền đưa vào RAG lâu dài**: thông tư, nghị định, luật, quy trình nội bộ, sổ tay nghiệp vụ.
2. **File chỉ xử lý một lần**: đề thi, bài tập kế toán, bảng Excel số liệu, file Word/PDF chứa câu hỏi.

Frontend chỉ chọn file và gửi request. Backend mới đọc file, trích text, định tuyến, lưu RAG hoặc gọi solver.

---

## 1. Kiểm tra V66 đã sẵn sàng

```http
GET /ai/v66/file-upload-router/status
```

Trả về danh sách endpoint, target và số lượng tài liệu/chunk hiện có.

---

## 2. Upload tài liệu vào RAG lâu dài

Dùng khi admin upload:

- Thông tư
- Nghị định
- Luật
- Quy định nội bộ
- Quy trình nghiệp vụ
- Tài liệu đào tạo
- Sổ tay kế toán/thuế

```http
POST /ai/v66/rag/upload-file
Content-Type: multipart/form-data
```

Form-data:

| Field | Bắt buộc | Ví dụ |
|---|---:|---|
| file | Có | Thong-tu-200.pdf |
| title | Không | Thông tư 200 |
| category | Không | che_do_ke_toan |
| document_type | Không | thong_tu |
| source | Không | admin_upload |
| tags | Không | tt200,ke_toan,thong_tu |
| auto_chunk | Không | true |

Ví dụ curl:

```bash
curl -X POST http://localhost:8000/ai/v66/rag/upload-file \
  -F "file=@Thong-tu-200.pdf" \
  -F "title=Thông tư 200" \
  -F "category=che_do_ke_toan" \
  -F "document_type=thong_tu" \
  -F "tags=tt200,ke_toan"
```

Sau khi upload xong, hỏi AI bằng:

```http
POST /ai/v64/long-exam-legal-solver
```

Payload:

```json
{
  "question": "Theo Thông tư 200, nghiệp vụ mua hàng có VAT định khoản thế nào?",
  "use_rag": true,
  "require_sources": true,
  "standard": "TT200"
}
```

---

## 3. Upload file để giải một lần, không lưu RAG

Dùng khi người dùng upload:

- Đề thi
- Bài tập
- File Word/PDF câu hỏi
- Excel bảng số liệu
- Chứng từ muốn phân tích một lần

```http
POST /ai/v66/solve/upload-question-file
Content-Type: multipart/form-data
```

Form-data:

| Field | Bắt buộc | Ví dụ |
|---|---:|---|
| file | Có | de-thi-ke-toan.pdf |
| question | Không | Giải chi tiết đề này |
| standard | Không | TT200 |
| category | Không | che_do_ke_toan |
| use_rag | Không | true |
| require_sources | Không | true |
| save_learning | Không | false |

Ví dụ curl:

```bash
curl -X POST http://localhost:8000/ai/v66/solve/upload-question-file \
  -F "file=@de-thi-ke-toan.pdf" \
  -F "question=Giải chi tiết đề này, định khoản và tính VAT" \
  -F "standard=TT200" \
  -F "use_rag=true"
```

Endpoint này sẽ:

1. Đọc file.
2. Trích text.
3. Ghép text file với câu hỏi người dùng.
4. Gọi `POST /ai/v64/long-exam-legal-solver`.
5. Trả lời bài giải.
6. Không đưa file vào RAG.

---

## 4. Một endpoint chung tự phân loại file

```http
POST /ai/v66/file-upload-router
Content-Type: multipart/form-data
```

Form-data chính:

| Field | Ý nghĩa |
|---|---|
| file | File upload |
| target | auto / rag / solve / temp |
| question | Câu hỏi nếu target là solve |
| title | Tên tài liệu nếu target là rag |
| category | Nhóm kiến thức RAG |
| document_type | thong_tu / nghi_dinh / de_thi / bai_tap / ... |
| tags | Tags phân cách bằng dấu phẩy |

### Khuyến nghị frontend

Không nên để `auto` cho tất cả. Nên cho người dùng/admin chọn rõ:

- `target=rag`: “Đưa vào kho tri thức AI”
- `target=solve`: “Chỉ dùng để hỏi/giải lần này”
- `target=temp`: “Chỉ đọc nội dung file”

Ví dụ upload vào RAG qua router:

```bash
curl -X POST http://localhost:8000/ai/v66/file-upload-router \
  -F "file=@Thong-tu-200.pdf" \
  -F "target=rag" \
  -F "title=Thông tư 200" \
  -F "category=che_do_ke_toan" \
  -F "document_type=thong_tu"
```

Ví dụ upload đề bài để giải:

```bash
curl -X POST http://localhost:8000/ai/v66/file-upload-router \
  -F "file=@de-thi.pdf" \
  -F "target=solve" \
  -F "question=Giải giúp tôi đề này, trình bày từng bước"
```

---

## 5. Frontend nên có 2 màn hình

### Màn hình 1: Quản lý tài liệu AI

Gọi:

```http
POST /ai/v66/rag/upload-file
```

Dùng cho admin/kế toán trưởng upload tài liệu nền.

### Màn hình 2: Hỏi AI / Giải đề

Gọi:

```http
POST /ai/v66/solve/upload-question-file
```

Dùng cho user upload đề bài/chứng từ/file câu hỏi.

---

## 6. Quy tắc quan trọng

- File RAG là kiến thức dùng lâu dài.
- File solve là dữ liệu đầu vào của một câu hỏi, không nên lưu vào RAG.
- Frontend không lưu file chính. Frontend chỉ gửi file lên backend.
- Backend chịu trách nhiệm đọc file, chunk, lưu vector, hoặc gọi solver.
- Với dữ liệu nhạy cảm như hóa đơn/hợp đồng thật, mặc định nên dùng `target=solve` hoặc `target=temp`, không tự động đưa vào RAG.

---

## 7. Các category RAG hiện có

- `thue_gtgt`
- `thue_tndn`
- `hoa_don_chung_tu`
- `tai_san_co_dinh`
- `cong_cu_dung_cu`
- `tien_luong_bhxh`
- `bao_cao_tai_chinh`
- `che_do_ke_toan`
- `general`

---

## 8. Các endpoint liên quan

```text
GET  /ai/v66/file-upload-router/status
POST /ai/v66/rag/upload-file
POST /ai/v66/solve/upload-question-file
POST /ai/v66/file-upload-router
POST /ai/v64/long-exam-legal-solver
POST /ai/v58/legal-knowledge/upload-text
POST /ai/v58/legal-search
```
