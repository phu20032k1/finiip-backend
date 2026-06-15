from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from services.advanced_calculation_v110 import solve_advanced_text_question
from services.smart_orchestrator_v110 import analyze_request, build_attachment_context, split_long_request
from services.rag_storage_v101 import answer_with_supabase_rag
from services.rag_v66_v67 import read_upload_bytes
import services.file_report_v68_v72 as file_report


def test_v110_vat_and_arithmetic_are_auditable():
    vat = solve_advanced_text_question("Tính VAT 10% của 100 triệu")
    assert vat and vat["recognized"] is True
    assert vat["result"]["vat_amount"] == 10_000_000
    assert vat["result"]["gross_amount"] == 110_000_000
    assert vat["formula"]
    assert vat["steps"]

    arithmetic = solve_advanced_text_question("Tính 1.250.000 + 350.000 * 2")
    assert arithmetic and arithmetic["result"]["value"] == 1_950_000


def test_v110_break_even_and_loan_payment():
    break_even = solve_advanced_text_question(
        "Tính điểm hòa vốn: chi phí cố định 500 triệu, giá bán 200 nghìn, biến phí 120 nghìn"
    )
    assert break_even and break_even["result"]["break_even_units"] == 6250
    assert break_even["result"]["break_even_revenue"] == 1_250_000_000

    loan = solve_advanced_text_question(
        "Tính khoản vay 1 tỷ, lãi suất 12% trong 24 tháng trả góp đều"
    )
    assert loan and 47_000_000 < loan["result"]["monthly_payment"] < 48_000_000
    assert loan["result"]["total_interest"] > 0



def test_v110_depreciation_allocation_and_cogs():
    depreciation = solve_advanced_text_question(
        "Tính khấu hao đường thẳng nguyên giá 120 triệu, giá trị còn lại 0, thời gian 60 tháng"
    )
    assert depreciation and depreciation["result"]["monthly_depreciation"] == 2_000_000
    assert depreciation["result"]["annual_depreciation"] == 24_000_000

    allocation = solve_advanced_text_question(
        "Phân bổ chi phí trả trước giá trị 24 triệu trong 12 tháng"
    )
    assert allocation and allocation["result"]["monthly_allocation"] == 2_000_000

    cogs = solve_advanced_text_question(
        "Tính giá vốn: tồn đầu kỳ 200 triệu, mua trong kỳ 500 triệu, tồn cuối kỳ 150 triệu"
    )
    assert cogs and cogs["result"]["cogs"] == 550_000_000


def test_v110_interest_npv_and_irr():
    compound = solve_advanced_text_question(
        "Tính lãi kép tiền gửi 100 triệu, lãi suất 8% trong 2 năm"
    )
    assert compound and compound["result"]["future_value"] == 116_640_000

    npv = solve_advanced_text_question(
        "Tính NPV vốn đầu tư ban đầu 1 tỷ, dòng tiền 300 triệu, 400 triệu, 500 triệu, tỷ lệ chiết khấu 10%"
    )
    assert npv and -21_100_000 < npv["result"]["npv"] < -21_000_000

    irr = solve_advanced_text_question(
        "Tính IRR vốn đầu tư ban đầu 1 tỷ, dòng tiền 400 triệu, 400 triệu, 400 triệu"
    )
    assert irr and 0.097 < irr["result"]["irr"] < 0.098

def test_v110_long_request_is_split_without_dropping_tasks():
    question = """
    1. Hãy phân tích doanh thu và lợi nhuận.
    2. Tính VAT 10% của 250 triệu.
    3. Lập checklist chứng từ cần kiểm tra.
    4. Xuất báo cáo Word và nêu các rủi ro.
    """
    tasks = split_long_request(question)
    analysis = analyze_request(question)
    assert len(tasks) >= 4
    assert analysis["task_count"] >= 4
    assert analysis["contains_calculation"] is True
    assert analysis["contains_file_request"] is True
    assert analysis["is_complex"] is True


def test_v110_attachment_selection_finds_relevant_text_near_end():
    filler = "\n\n".join(f"Đoạn dữ liệu thông thường số {i}." for i in range(160))
    relevant = (
        "CÔNG NỢ QUÁ HẠN: Khách hàng A còn nợ 480.000.000 đồng, quá hạn 95 ngày. "
        "Cần đối chiếu xác nhận công nợ và đánh giá khả năng thu hồi."
    )
    selected = build_attachment_context(
        "Hãy phân tích công nợ quá hạn và rủi ro thu hồi",
        [{"filename": "bao_cao_dai.txt", "extracted_text": filler + "\n\n" + relevant}],
        max_total_chars=8000,
    )
    assert "480.000.000" in selected["context"]
    assert selected["manifest"][0]["selected_chunks"]


def test_v110_new_knowledge_pack_answers_excel_workflow(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = answer_with_supabase_rag(
        "cách xử lý dữ liệu Excel và đối chiếu hai nguồn",
        save_memory=False,
        allow_llm=False,
    )
    answer = result["answer"].lower()
    assert "làm sạch dữ liệu" in answer or "đối chiếu hai nguồn" in answer
    assert result["source_cards"]
    assert any("excel" in card["title"].lower() for card in result["source_cards"])
    assert "knowledge_base/" not in result["answer"]


def test_v110_xlsx_reader_preserves_sheet_cells_and_formulas():
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "DoanhThu"
    sheet["A1"] = "Doanh thu"
    sheet["B1"] = 1_000_000
    sheet["B2"] = "=B1*10%"
    buffer = BytesIO()
    workbook.save(buffer)

    text = read_upload_bytes("bao_cao.xlsx", buffer.getvalue())
    assert "DoanhThu" in text
    assert "Doanh thu" in text
    assert "=B1*10%" in text


def test_v110_docx_reader_reads_tables():
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_paragraph("Báo cáo công nợ")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Khách hàng"
    table.cell(0, 1).text = "Số dư"
    table.cell(1, 0).text = "Công ty A"
    table.cell(1, 1).text = "125.000.000"
    buffer = BytesIO()
    document.save(buffer)

    text = read_upload_bytes("cong_no.docx", buffer.getvalue())
    assert "Báo cáo công nợ" in text
    assert "Công ty A" in text
    assert "125.000.000" in text


def test_v110_report_exports_docx_xlsx_pdf_and_unique_jobs(tmp_path, monkeypatch):
    root = tmp_path / "jobs"
    monkeypatch.setattr(file_report, "FILE_REPORT_ROOT", root)
    monkeypatch.setattr(file_report, "HISTORY_FILE", root / "history.json")
    root.mkdir(parents=True, exist_ok=True)

    source = file_report.FileReportInput(
        "bao_cao.txt",
        (
            "Doanh thu: 1.200.000.000\n"
            "Giá vốn: 750.000.000\n"
            "Chi phí bán hàng: 100.000.000\n"
            "Công nợ quá hạn: 80.000.000\n"
        ).encode("utf-8"),
    )
    jobs = []
    for output_format in ("docx", "xlsx", "pdf"):
        job = file_report.create_and_run_sync(
            files=[source],
            instruction="Lập báo cáo chi tiết, nêu số liệu và rủi ro",
            question="Phân tích tài chính và công nợ",
            task_type="financial_report",
            output_format=output_format,
            workspace_id="test-workspace",
            user_id="test-user",
            title="Báo cáo V110",
        )
        jobs.append(job)
        assert job["status"] == "done"
        resolved = file_report.resolve_job_output(job["job_id"])
        assert Path(resolved["path"]).exists()
        assert Path(resolved["path"]).stat().st_size > 500
        assert str(resolved["filename"]).endswith(f".{output_format}")

    assert len({job["job_id"] for job in jobs}) == 3


def test_v110_chat_capabilities_expose_new_features(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from chat_api_v1 import chat_capabilities, chat_status

    status = chat_status()
    capabilities = chat_capabilities()
    assert status["version"] == "1.10.0"
    assert status["limits"]["message_chars"] == 100000
    assert capabilities["long_question"]["multi_task_planning"] is True
    assert "xlsx" in capabilities["files"]["export"]
    assert "break_even" in capabilities["calculation"]["supported"]


def test_v110_chat_can_export_answer_without_attachment(tmp_path, monkeypatch):
    root = tmp_path / "chat-jobs"
    monkeypatch.setattr(file_report, "FILE_REPORT_ROOT", root)
    monkeypatch.setattr(file_report, "HISTORY_FILE", root / "history.json")
    root.mkdir(parents=True, exist_ok=True)

    from chat_api_v1 import _infer_export_request, _maybe_create_attachment_report

    assert _infer_export_request("Bạn có thể làm báo cáo không?") is None
    result = _maybe_create_attachment_report(
        "Hãy xuất cho tôi báo cáo Word về doanh thu tháng này",
        [],
        {"workspace_id": "ws", "user_id": "user"},
        answer="Doanh thu tháng này là 1.200.000.000 đồng. Cần kiểm tra công nợ quá hạn.",
    )
    assert result and result["status"] == "done"
    assert result["output_format"] == "docx"
    assert result["download_url"].startswith("/api/v1/chat/generated-files/")
