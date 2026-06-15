from pathlib import Path

from services.accounting_ai_enterprise import (
    add_document,
    answer_with_enterprise_rag,
    create_journal_entry,
    create_or_update_workspace,
    create_review_item,
    database_schema_blueprint,
    enterprise_capabilities,
    export_journal_csv,
    frontend_api_contract,
    list_company_memory,
    list_review_queue,
    monthly_summary_report,
    parse_invoice_text,
    production_readiness_check,
    quality_dashboard,
    remember_company_fact,
    reset_enterprise_store,
    run_accounting_agent_pipeline,
    run_evaluation,
    search_documents,
    smart_followup_questions,
    tax_risk_check,
    update_review_item,
)


def setup_function():
    reset_enterprise_store()


def test_v86_document_rag_search_and_answer():
    create_or_update_workspace("demo", name="Demo Co")
    result = add_document(
        title="Quy trình VAT nội bộ",
        content="Điều 1. Hóa đơn đầu vào phải có VAT 10% và chứng từ thanh toán chuyển khoản nếu giá trị lớn.",
        workspace_id="demo",
        source_type="tax_legal",
    )
    assert result["chunks_added"] >= 1
    search = search_documents("VAT đầu vào chuyển khoản", workspace_id="demo")
    assert search["count"] >= 1
    answer = answer_with_enterprise_rag("VAT đầu vào cần gì?", workspace_id="demo")
    assert answer["enterprise_sources"]


def test_v87_parse_invoice_text():
    text = """
    HÓA ĐƠN GTGT
    Số hóa đơn: AA/24E-000123
    Ngày 10/06/2026
    Đơn vị bán hàng: Công ty ABC
    Mã số thuế: 0101234567
    Người mua: Công ty Demo
    Cộng tiền hàng: 10.000.000
    Thuế suất GTGT: 10%
    Tiền thuế GTGT: 1.000.000
    Tổng cộng tiền thanh toán: 11.000.000
    """
    parsed = parse_invoice_text(text)
    assert parsed["invoice_no"]
    assert parsed["seller_tax_code"] == "0101234567"
    assert parsed["total_payment"] == 11000000
    assert parsed["vat_rate"] == 0.10


def test_v88_journal_and_export_csv():
    create_or_update_workspace("demo")
    entry = create_journal_entry(
        description="Mua hàng hóa nhập kho chuyển khoản VAT 10%",
        amount=11_000_000,
        vat_rate=0.10,
        workspace_id="demo",
        has_invoice=True,
    )
    assert entry["entry_id"].startswith("je_")
    assert entry["journal_lines"]
    exported = export_journal_csv("demo")
    assert exported["ok"] is True
    assert Path(exported["path"]).exists()


def test_v89_review_queue_and_feedback():
    item = create_review_item("demo", "transaction", "Duyệt chi phí", {"amount": 1_000_000}, risk_level="medium")
    queue = list_review_queue("demo")
    assert queue["count"] == 1
    updated = update_review_item(item["review_id"], "corrected", reviewer_note="Sửa tài khoản", correction={"debit": "642"})
    assert updated["status"] == "corrected"


def test_v90_v91_risk_and_followup_questions():
    create_or_update_workspace("demo")
    tx = {"description": "Chi tiếp khách bằng tiền mặt không hóa đơn", "amount": 25_000_000, "has_invoice": False, "payment_method": "tiền mặt"}
    risk = tax_risk_check(tx, workspace_id="demo")
    assert risk["risk_level"] == "high"
    followups = smart_followup_questions({"description": "Mua máy tính có hóa đơn", "amount": 35_000_000}, workspace_id="demo")
    assert followups["count"] >= 2


def test_v92_agent_pipeline_creates_document_journal_review():
    create_or_update_workspace("demo")
    text = "Số hóa đơn: 0001\nNgày 10/06/2026\nMua hàng hóa nhập kho VAT 10%\nTổng cộng tiền thanh toán: 11.000.000"
    result = run_accounting_agent_pipeline(text, workspace_id="demo", filename="invoice.txt")
    assert result["document"]["document_id"].startswith("doc_")
    assert result["journal_entry"]["entry_id"].startswith("je_")
    assert result["steps"][-1]["step"] == "review_created"


def test_v93_v94_v97_v98_dashboard_reports_memory_evaluation():
    create_or_update_workspace("demo", name="Demo Co", policy={"asset_capitalization_threshold": 20_000_000})
    remember_company_fact("demo", "Máy tính từ 20 triệu trở lên phải review TSCĐ", category="asset_policy")
    assert list_company_memory("demo")["items"]
    create_journal_entry("Bán hàng chưa thu tiền VAT 10%", amount=22_000_000, vat_rate=0.10, workspace_id="demo", has_invoice=True)
    eval_run = run_evaluation(workspace_id="demo")
    assert eval_run["total"] >= 5
    dashboard = quality_dashboard("demo")
    assert "journal_entries" in dashboard
    report = monthly_summary_report("demo")
    assert "kpis" in report


def test_v95_v96_v99_contract_schema_readiness_capabilities():
    capabilities = enterprise_capabilities()
    assert "V86_RAG" in capabilities["modules"]
    schema = database_schema_blueprint()
    assert "accounting_documents" in schema["ddl"]
    contract = frontend_api_contract()
    assert any(e["path"] == "/ai/v86/rag/ask" for e in contract["endpoints"])
    readiness = production_readiness_check()
    assert readiness["total"] >= 5
