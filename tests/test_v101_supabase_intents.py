import os

from services.rag_storage_v101 import SUPABASE_SCHEMA_SQL, supabase_config, supabase_is_active
from services.simple_intents_v101 import detect_simple_intent, list_simple_intents
from services.question_analyzer import detect_accounting_domain, detect_intent
from services.accounting_ai_enterprise import reset_enterprise_store
from services.rag_admin_ui_v100 import admin_rag_storage_status, search_documents, upload_admin_rag_document


def test_v101_supabase_status_defaults_to_local_without_env(monkeypatch):
    monkeypatch.delenv("RAG_STORAGE_MODE", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    cfg = supabase_config()
    assert cfg["active_backend"] == "local"
    assert supabase_is_active() is False
    assert "admin_rag_documents" in SUPABASE_SCHEMA_SQL
    assert admin_rag_storage_status()["schema_sql_available"] is True


def test_v101_admin_rag_still_works_with_local_fallback(monkeypatch):
    monkeypatch.delenv("RAG_STORAGE_MODE", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    reset_enterprise_store()
    result = upload_admin_rag_document(
        filename="vat_v101.txt",
        content="VAT đầu vào được khấu trừ khi có hóa đơn hợp lệ và đủ điều kiện theo quy định.".encode("utf-8"),
        workspace_id="v101_demo",
        source_type="tax_legal",
    )
    assert result["chunks_added"] >= 1
    hits = search_documents("khấu trừ VAT hóa đơn", workspace_id="v101_demo")["results"]
    assert hits


def test_v101_simple_intents_cover_admin_and_user_cases():
    rag = detect_simple_intent("up tài liệu RAG ở đâu")
    assert rag["intent"] == "admin_rag_upload"
    assert rag["requires_admin"] is True

    supa = detect_simple_intent("đã nối supabase chưa")
    assert supa["intent"] == "supabase_status"

    user_file = detect_simple_intent("người dùng up báo cáo OCR")
    assert user_file["intent"] in {"user_file_upload", "ocr_invoice", "report_analyze"}
    assert user_file["requires_admin"] is False

    entry = detect_simple_intent("mua laptop 25 triệu hạch toán sao")
    assert entry["intent"] == "accounting_entry"

    assert list_simple_intents()["count"] >= 30


def test_v101_question_analyzer_uses_simple_router():
    assert detect_intent("up tài liệu rag") == "admin_rag_upload"
    domain = detect_accounting_domain("xóa tài liệu RAG")
    assert domain["v101_simple_intent"]["intent"] == "admin_rag_delete"
