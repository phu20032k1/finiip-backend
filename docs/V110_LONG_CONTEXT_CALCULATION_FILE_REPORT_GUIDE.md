# Finiip V110 - Câu hỏi dài, tính toán, đọc file và xuất báo cáo

## 1. Mục tiêu bản nâng cấp

V110 nâng phần backend chatbot theo bốn lớp:

1. **Hiểu yêu cầu dài**: nhận tối đa 100.000 ký tự, nhận diện nhiều đầu việc, giải từng phần rồi hợp nhất.
2. **Tính toán có kiểm soát**: dùng engine công thức an toàn trước khi dùng mô hình ngôn ngữ.
3. **Hiểu file lớn**: đọc PDF, Word, Excel, dữ liệu văn bản và ảnh; chọn đoạn liên quan thay vì chỉ cắt phần đầu.
4. **Tạo file đầu ra**: lập báo cáo và xuất DOCX, XLSX, PDF, CSV, JSON, TXT hoặc Markdown.

V110 không tuyên bố biết “mọi kiến thức” theo nghĩa tuyệt đối. Các quy định pháp luật, thuế suất, thời hạn, mức phạt và biểu mẫu có thể thay đổi vẫn phải có nguồn chính thức đang hiệu lực. Khi cấu hình `OPENAI_API_KEY`, hệ thống có thêm khả năng diễn giải và tổng hợp kiến thức tổng quát; khi không có khóa, RAG và engine xác định vẫn hoạt động.

## 2. Các file đã nâng

### File backend chính

- `chat_api_v1.py`
- `services/rag_storage_v101.py`
- `services/rag_v66_v67.py`
- `services/accounting_ai_full.py`
- `services/accounting_ai_enterprise.py`
- `services/file_report_v68_v72.py`

### Module mới

- `services/advanced_calculation_v110.py`
- `services/smart_orchestrator_v110.py`

### Kho kiến thức mới

- `knowledge_base/global/accounting/accounting_operations_complete_v110.md`
- `knowledge_base/global/finance/financial_analysis_and_planning_v110.md`
- `knowledge_base/global/business/business_management_internal_control_v110.md`
- `knowledge_base/global/technology/data_excel_reporting_v110.md`
- `knowledge_base/global/legal/contract_review_business_v110.md`
- `knowledge_base/policies/long_question_file_report_policy_v110.md`
- `knowledge_base/CHANGELOG_V110.md`

### Cấu hình và kiểm thử

- `.env.example`
- `render.yaml`
- `requirements.txt`
- `Dockerfile`
- `README.md`
- `tests/test_v110_intelligence.py`
- `MANIFEST_V110.txt`

## 3. Xử lý câu hỏi dài

`services/smart_orchestrator_v110.py` thực hiện:

- đo độ dài, số lượng số liệu, yêu cầu file và yêu cầu tính toán;
- nhận diện danh sách đánh số, bullet, nhiều câu hỏi và nhiều hành động;
- chia tối đa 12 đầu việc, giữ bối cảnh chung;
- chạy từng phần qua RAG/engine;
- gộp citation và tạo câu trả lời cuối cùng;
- nếu có OpenAI, tổng hợp lại bằng một lần gọi LLM để tránh câu trả lời rời rạc.

Giới hạn mặc định:

```env
FINIIP_CHAT_CONTEXT_CHARS=20000
FINIIP_CHAT_MESSAGE_CONTEXT_CHARS=5000
FINIIP_LLM_HISTORY_CHARS=20000
FINIIP_LLM_MAX_OUTPUT_TOKENS=4000
```

API nhận tối đa 100.000 ký tự cho mỗi tin nhắn. Điều này không có nghĩa toàn bộ 100.000 ký tự luôn được gửi nguyên vẹn vào mô hình; hệ thống sẽ lập kế hoạch và chọn phần liên quan để tránh vượt context.

## 4. Engine tính toán V110

`services/advanced_calculation_v110.py` hỗ trợ:

- biểu thức số học an toàn;
- phần trăm của một số tiền;
- tỷ lệ tăng/giảm;
- VAT đã gồm/chưa gồm thuế;
- giá vốn hàng bán theo tồn đầu kỳ, mua trong kỳ và tồn cuối kỳ;
- khấu hao đường thẳng và phân bổ chi phí trả trước;
- lợi nhuận gộp, lợi nhuận trước thuế và biên lợi nhuận;
- điểm hòa vốn;
- lãi đơn, lãi kép và giá trị tương lai;
- khoản trả góp đều theo công thức PMT;
- NPV và IRR cho chuỗi dòng tiền theo kỳ;
- current ratio, quick ratio, ROA và ROE.

Mỗi kết quả có:

```json
{
  "recognized": true,
  "answer": "...",
  "formula": "...",
  "inputs": {},
  "result": {},
  "steps": [],
  "checks": [],
  "needs_human_review": true
}
```

Endpoint kiểm thử trực tiếp:

```http
POST /api/v1/chat/calculate
Content-Type: application/json

{
  "question": "Tính điểm hòa vốn: chi phí cố định 500 triệu, giá bán 200 nghìn, biến phí 120 nghìn"
}
```

Engine dùng AST whitelist, không chạy `eval` tùy ý và có kiểm tra chia cho 0/lũy thừa quá lớn.

## 5. Đọc file

### Định dạng đọc

- PDF có lớp text.
- PDF scan qua PyMuPDF + Tesseract OCR.
- DOCX, gồm đoạn văn và bảng.
- XLSX/XLSM, gồm tên sheet, dữ liệu, địa chỉ ô có công thức.
- CSV, JSON, TXT, MD, HTML/XML.
- PNG, JPG, JPEG, WEBP, TIFF qua OCR.

Cấu hình:

```env
FINIIP_ATTACHMENT_CONTEXT_CHARS=60000
FINIIP_ATTACHMENT_STORE_CHARS=1000000
FINIIP_OCR_LANG=vie+eng
FINIIP_OCR_MAX_PAGES=80
FINIIP_XLSX_MAX_ROWS_PER_SHEET=20000
FINIIP_XLSX_MAX_COLS=200
```

Với file dài, hệ thống chia đoạn và xếp hạng theo câu hỏi. Khi người dùng yêu cầu tóm tắt toàn bộ, hệ thống lấy mẫu phần đầu, giữa, cuối và các đoạn có độ liên quan cao.

## 6. Tạo và trả file

Người dùng có thể đính kèm file rồi hỏi tự nhiên, ví dụ:

- “Đọc các file này và xuất báo cáo Word chi tiết.”
- “Phân tích công nợ rồi tạo file Excel.”
- “Rà soát hợp đồng và trả tôi bản PDF.”

Backend nhận diện định dạng từ câu hỏi và trả:

```json
{
  "generated_file": {
    "job_id": "fr_...",
    "status": "done",
    "filename": "bao-cao-....docx",
    "download_url": "/api/v1/chat/generated-files/fr_...",
    "output_format": "docx",
    "analysis_mode": "deterministic_file_report"
  }
}
```

Frontend nên hiển thị nút **Tải báo cáo** khi `generated_file.status == "done"` và `download_url` tồn tại.

Các định dạng xuất:

- DOCX: tiêu đề, heading, đoạn văn, bảng Markdown, footer.
- XLSX: sheet tổng quan, danh sách file, điểm chính và nội dung báo cáo; có filter, freeze pane, định dạng cột.
- PDF: Unicode tiếng Việt bằng DejaVu/Liberation khi có; có fallback PDF tối thiểu.
- CSV, JSON, TXT, MD.

V110 cũng sửa lỗi trùng `job_id` khi cùng một nguồn được xuất nhiều định dạng trong cùng một giây.

## 7. Nguồn hiển thị đẹp

Nội dung trả lời không chèn chuỗi như:

```text
knowledge_base/accounting_accounts.md
```

Nguồn nằm riêng trong:

```json
{
  "source_cards": [
    {
      "title": "Sổ tay nghiệp vụ kế toán toàn diện",
      "badge": "Tài liệu RAG",
      "location": "Kho kiến thức Finiip",
      "excerpt": "..."
    }
  ],
  "source_presentation": "separate_cards"
}
```

Frontend nên thu gọn nguồn trong nút “Nguồn” hoặc “Tài liệu tham chiếu”, không nối nguồn vào bubble trả lời.

## 8. Endpoint mới

```http
GET  /api/v1/chat/status
GET  /api/v1/chat/capabilities
POST /api/v1/chat/calculate
POST /api/v1/chat/analyze-request
GET  /api/v1/chat/generated-files/{job_id}
```

`GET /api/v1/chat/capabilities` cho frontend biết giới hạn câu hỏi, định dạng file, chức năng OCR, tính toán và trạng thái LLM.

## 9. Cài đặt local

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

Mở:

```text
http://127.0.0.1:8000/docs
```

Kiểm tra:

```text
GET /api/v1/health
GET /api/v1/chat/status
GET /api/v1/chat/capabilities
```

## 10. Cấu hình Render

Các biến quan trọng:

```env
OPENAI_API_KEY=...
OPENAI_CHAT_MODEL=gpt-4o-mini
FINIIP_LLM_MODE=auto
FINIIP_CHAT_CONTEXT_CHARS=20000
FINIIP_LLM_MAX_OUTPUT_TOKENS=4000
FINIIP_ATTACHMENT_CONTEXT_CHARS=60000
FINIIP_FILE_REPORT_CONTEXT_CHARS=70000
DATABASE_URL=...
```

Dockerfile đã cài:

- Tesseract tiếng Việt và tiếng Anh.
- DejaVu fonts cho PDF tiếng Việt.
- PyMuPDF và ReportLab qua `requirements.txt`.

Sau khi chép file và push GitHub, chọn **Manual Deploy → Deploy latest commit** trên Render.

## 11. Test

Chạy test V109 + V110 + engine kế toán/file:

```bash
PYTHONPATH=. pytest -q \
  tests/test_v109_smart_chat.py \
  tests/test_v110_intelligence.py \
  tests/test_v85_accounting_ai_full.py \
  tests/test_v86_v99_accounting_enterprise.py \
  tests/test_v64_long_exam_legal_solver_offline.py
```

Kết quả tại thời điểm đóng gói: **34 passed**.

Riêng `tests/test_v110_intelligence.py`: **10 passed**. Test gồm VAT, số học, hòa vốn, khoản vay, chia câu hỏi dài, tìm đoạn cuối file, kho kiến thức mới, đọc DOCX/XLSX và xuất DOCX/XLSX/PDF.

Toàn bộ thư mục `tests/` hiện có 6 lỗi legacy đã tồn tại ở V109, chủ yếu là test UI cũ trong dự án backend-only và contract cũ; chúng không phát sinh từ V110.

## 12. Lưu ý vận hành

- Không dùng kết quả AI để tự động ghi sổ/kê khai/duyệt mà không có người có trách nhiệm kiểm tra.
- File scan mờ có thể OCR sai; cần đối chiếu ảnh gốc.
- File quá lớn vẫn cần giới hạn theo tài nguyên Render.
- Kiến thức pháp lý mới nhất cần được nạp từ nguồn chính thức và quản trị hiệu lực.
- OpenAI key giúp tổng hợp tự nhiên hơn nhưng không thay thế dữ liệu doanh nghiệp hoặc nguồn luật chính thức.


## 11. Kiểm thử

Kết quả xác minh trước khi đóng gói:

- `tests/test_v110_intelligence.py`: **12 passed**.
- Bộ liên quan V109 + V110 + kế toán/file/pháp lý: **36 passed**.
- Toàn bộ thư mục `tests/`: **96 passed, 6 failed**. Sáu lỗi còn lại là kiểm thử legacy đã tồn tại ở V109, chủ yếu đòi các trang UI cũ trong bản backend-only hoặc contract API cũ; không phát sinh từ V110.

Lệnh khuyến nghị:

```bash
PYTHONPATH=. pytest -q tests/test_v110_intelligence.py
```
