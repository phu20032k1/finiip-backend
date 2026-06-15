from finiip_v25_v40 import _v64_detect_intent, _v64_split_question, _v64_solve_calculation


def test_v64_detects_hybrid_long_exam():
    q = "Công ty mua hàng hóa 100 triệu, VAT 10%, chưa thanh toán. Sau đó bán một nửa với giá 80 triệu, VAT 10%, khách chưa trả tiền. Theo thông tư hiện hành có được ghi nhận không?"
    assert _v64_detect_intent(q) == "hybrid_legal_exam"


def test_v64_splits_long_question():
    q = "Mua hàng 100 triệu VAT 10%. Bán một nửa giá 80 triệu VAT 10%. Hãy tính VAT và lợi nhuận."
    parts = _v64_split_question(q)
    assert len(parts) >= 2
    assert parts[0]["order"] == 1


def test_v64_solves_basic_exam_calculation():
    q = "Công ty mua hàng hóa 100 triệu, VAT 10%, chưa thanh toán. Sau đó bán một nửa với giá 80 triệu, VAT 10%, khách chưa trả tiền. Hãy định khoản, tính VAT phải nộp và lợi nhuận."
    result = _v64_solve_calculation(q)
    assert result["calculations"]["vat_input"] == 10_000_000
    assert result["calculations"]["vat_output"] == 8_000_000
    assert result["calculations"]["gross_profit"] == 30_000_000
