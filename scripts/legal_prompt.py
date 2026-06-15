from __future__ import annotations


def build_legal_rag_prompt(user_question: str, chunks: list[dict]) -> str:
    """Build prompt for legal/accounting RAG answer."""
    context_lines = []
    for i, chunk in enumerate(chunks, start=1):
        context_lines.append(
            f"[Nguồn {i}]\n"
            f"File: {chunk.get('file_name')}\n"
            f"Đường dẫn: {chunk.get('path')}\n"
            f"Tiêu đề: {chunk.get('title')}\n"
            f"Nội dung:\n{chunk.get('content')}\n"
        )

    context = "\n---\n".join(context_lines) if context_lines else "Không tìm thấy tài liệu liên quan."

    return f"""
Bạn là trợ lý tra cứu luật, thông tư và nghiệp vụ kế toán - thuế.

Câu hỏi người dùng:
{user_question}

Tài liệu RAG tìm được:
{context}

Nguyên tắc bắt buộc:
1. Chỉ kết luận khi tài liệu RAG có căn cứ rõ ràng.
2. Không tự bịa số thông tư, điều, khoản, ngày hiệu lực nếu tài liệu không có.
3. Nếu tài liệu không đủ, nói rõ: "Chưa đủ căn cứ để kết luận".
4. Nếu tài liệu có tên văn bản, điều, khoản hoặc nguồn thì phải nêu ra.
5. Diễn giải bằng tiếng Việt dễ hiểu.
6. Áp dụng vào tình huống cụ thể của người dùng.
7. Nêu rủi ro và thông tin còn thiếu.

Format bắt buộc:
## 1. Kết luận ngắn
## 2. Căn cứ từ tài liệu RAG
## 3. Diễn giải dễ hiểu
## 4. Áp dụng vào tình huống
## 5. Rủi ro/lưu ý
## 6. Thông tin còn thiếu
## 7. Kết luận cuối
""".strip()
