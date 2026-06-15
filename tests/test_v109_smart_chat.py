from services.accounting_ai_full import parse_money, solve_text_question
from services.rag_storage_v101 import answer_with_supabase_rag


def test_v109_greeting_has_identity_and_company():
    result = answer_with_supabase_rag("xin chào", save_memory=False)
    answer = result["answer"]
    assert "Finiip" in answer
    assert "CTCP IIP Việt Nam" in answer
    assert result["conversation_route"] == "greeting"


def test_v109_capabilities_cover_reports_calculation_and_files():
    result = answer_with_supabase_rag("bạn có thể làm gì", save_memory=False)
    answer = result["answer"].lower()
    assert "báo cáo" in answer
    assert "tính toán" in answer
    assert "pdf/word/excel" in answer
    assert result["conversation_route"] == "help"


def test_v109_account_lookup_keeps_source_out_of_answer_bubble():
    result = answer_with_supabase_rag("tài khoản 111 là gì", save_memory=False)
    assert "TK 111" in result["answer"]
    assert "knowledge_base/accounting_accounts.md" not in result["answer"]
    assert "Nguồn nội bộ:" not in result["answer"]
    assert result["source_presentation"] == "separate_cards"
    assert result["source_cards"]
    assert result["source_cards"][0]["title"] == "Hệ thống tài khoản kế toán Finiip"


def test_v109_followup_understands_product_chat_history_format():
    history = "user: Tài khoản 111 là gì?\nassistant: TK 111 là tiền mặt."
    result = answer_with_supabase_rag("còn 112 thì sao?", history=history, save_memory=False)
    assert result["followup_context_used"] is True
    assert result["followup_strategy"] == "account_followup"
    assert "Tài khoản 112" in result["resolved_question"]
    assert "TK 112" in result["answer"]


def test_v109_money_parser_does_not_treat_vat_percent_as_amount():
    assert parse_money("Tính VAT 10% của 100 triệu") == 100_000_000
    solved = solve_text_question("Tính VAT 10% của 100 triệu")
    assert "10.000.000 đồng" in solved["answer"]
    assert "110.000.000 đồng" in solved["answer"]
