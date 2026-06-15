from services.accounting_ai_enterprise import reset_enterprise_store, search_documents
from services.rag_admin_ui_v100 import (
    admin_rag_stats,
    delete_admin_rag_document,
    get_admin_rag_document,
    list_admin_rag_documents,
    reindex_admin_rag_document,
    render_admin_rag_page,
    upload_admin_rag_document,
    validate_admin_rag_upload,
)


def test_v100_admin_upload_list_search_delete_cycle():
    reset_enterprise_store()
    result = upload_admin_rag_document(
        filename="quy_trinh_thanh_toan.md",
        content="# Quy trình thanh toán\n\nChi phí tiếp khách cần hóa đơn hợp lệ và chứng từ thanh toán theo chính sách.".encode("utf-8"),
        workspace_id="demo_company",
        title="Quy trình thanh toán nội bộ",
        source_type="internal_process",
        note="Tài liệu chuẩn do admin nạp",
    )
    doc_id = result["document"]["document_id"]
    assert result["chunks_added"] >= 1
    docs = list_admin_rag_documents(workspace_id="demo_company")["items"]
    assert len(docs) == 1
    assert docs[0]["document_scope"] == "global_knowledge"
    hits = search_documents("chi phí tiếp khách hóa đơn", workspace_id="demo_company")["results"]
    assert hits
    detail = get_admin_rag_document(doc_id)
    assert detail["chunk_count"] >= 1
    deleted = delete_admin_rag_document(doc_id)
    assert deleted["chunks_removed"] >= 1
    assert search_documents("chi phí tiếp khách hóa đơn", workspace_id="demo_company")["results"] == []


def test_v100_reindex_keeps_document_active():
    reset_enterprise_store()
    result = upload_admin_rag_document(
        filename="vat.txt",
        content="VAT GTGT 10% áp dụng cho hàng hóa dịch vụ thông thường.".encode("utf-8"),
        workspace_id="default",
        source_type="tax_legal",
    )
    doc_id = result["document"]["document_id"]
    reindexed = reindex_admin_rag_document(doc_id)
    assert reindexed["ok"] is True
    assert reindexed["chunks_added"] >= 1
    stats = admin_rag_stats("default")
    assert stats["documents"] == 1
    assert stats["chunks"] >= 1


def test_v100_rejects_unsupported_admin_upload_extension():
    try:
        validate_admin_rag_upload("malware.exe", b"abc")
    except ValueError as exc:
        assert "chưa được phép" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_v100_render_page_contains_core_controls():
    reset_enterprise_store()
    html = render_admin_rag_page(admin_key="dev", workspace_id="default")
    assert "Finiip Admin RAG UI" in html
    assert "Upload & Index" in html
    assert "Hỏi thử RAG" in html
    assert "Danh sách tài liệu RAG" in html
