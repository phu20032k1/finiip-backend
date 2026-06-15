from pathlib import Path

from services.rag_storage_v101 import answer_with_supabase_rag


def ask(question: str) -> dict:
    return answer_with_supabase_rag(question, save_memory=False)


def test_account_641_is_exact_and_natural():
    result = ask("Tài khoản 641 được sử dụng trong trường hợp nào?")
    answer = result["answer"]
    assert "Chi phí bán hàng" in answer
    assert "quảng cáo" in answer
    assert "642" not in answer


def test_unpaid_purchase_journal():
    answer = ask("Doanh nghiệp mua hàng hóa chưa thanh toán thì hạch toán như thế nào?")["answer"]
    assert "Nợ TK 156" in answer
    assert "Nợ TK 1331" in answer
    assert "Có TK 331" in answer


def test_current_vat_non_cash_threshold():
    answer = ask("VAT đầu vào được khấu trừ khi đáp ứng điều kiện nào?")["answer"]
    assert "5.000.000" in answer
    assert "không dùng tiền mặt" in answer
    assert "20.000.000" not in answer


def test_current_tndn_cash_risk():
    answer = ask("Chi phí 8 triệu thanh toán bằng tiền mặt có được trừ khi tính thuế TNDN không?")["answer"]
    assert "5.000.000" in answer
    assert "rủi ro" in answer.lower()
    assert "không dùng tiền mặt" in answer


def test_circular_58_future_effective_date_guard():
    result = ask("Hiện nay doanh nghiệp siêu nhỏ đã áp dụng Thông tư 58/2026/TT-BTC chưa?")
    answer = result["answer"]
    assert "01/07/2026" in answer
    assert "chưa có hiệu lực" in answer
    assert result["answer_mode"] == "legal_effective_date_guarded"


def test_laptop_18m_is_not_fixed_asset_by_value_threshold():
    answer = ask("Laptop 18 triệu dùng cho bộ phận quản lý có phải tài sản cố định không, hạch toán thế nào?")["answer"]
    assert "chưa đạt ngưỡng 30 triệu" in answer
    assert "153 hoặc 242" in answer
    assert "Nợ 642" in answer
    assert "Có 242" in answer


def test_no_hallucinated_penalty():
    result = ask("Theo tài liệu, mức phạt chính xác khi doanh nghiệp thiếu hóa đơn là bao nhiêu?")
    assert "Không tìm thấy" in result["answer"]
    assert result["confidence"].startswith("low")


def test_bundled_index_covers_whole_knowledge_base():
    root = Path(__file__).resolve().parents[1]
    index_file = root / "data" / "rag_index.json"
    assert index_file.exists()
    text = index_file.read_text(encoding="utf-8")
    assert "vat_hoa_don.md" in text
    assert "thong_tu_58_2026_dnsn.md" in text
    assert "luong_bao_hiem_tncn.md" in text
    assert "khoa_so_bao_cao.md" in text
