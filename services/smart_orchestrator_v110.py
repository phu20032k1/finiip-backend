"""Finiip V110 request planning, long-context selection and answer synthesis."""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

VERSION = "v110_smart_orchestrator"

_STOPWORDS = {
    "va", "cua", "cho", "cac", "mot", "nhung", "duoc", "theo", "trong", "khi",
    "nay", "do", "voi", "hoac", "thi", "la", "co", "khong", "phai", "ve", "de",
    "tu", "den", "neu", "nhu", "can", "hoi", "giup", "toi", "to", "ban", "anh", "chi",
}


def normalize(text: Any) -> str:
    raw = str(text or "").lower()
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch)).replace("đ", "d")
    raw = re.sub(r"[^a-z0-9%._/\-\s]", " ", raw)
    return re.sub(r"\s+", " ", raw).strip()


def tokens(text: Any) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9]+", normalize(text)) if len(t) >= 2 and t not in _STOPWORDS]


def _dedupe(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        clean = re.sub(r"\s+", " ", str(item or "")).strip(" \n\t-•;:")
        key = normalize(clean)
        if len(clean) < 4 or not key or key in seen:
            continue
        seen.add(key)
        out.append(clean)
    return out


def split_long_request(question: str, max_tasks: int = 12) -> List[str]:
    """Split a long multi-part request without turning every sentence into a task."""
    text = str(question or "").strip()
    if not text:
        return []
    candidates: List[str] = []

    # Explicit numbered/bulleted requests are the strongest signal.
    marked = re.split(r"(?:^|\n)\s*(?:[-•*]|\d{1,2}[.)]|[a-zA-Z][.)])\s+", text)
    if len(marked) > 1:
        candidates.extend(marked)

    # Questions separated by question marks are usually independent asks.
    questions = re.findall(r"(?:^|(?<=[.!?;\n]))\s*([^?\n]{8,}\?)", text)
    if len(questions) > 1:
        candidates.extend(questions)

    # Lines with action verbs can be independent deliverables.
    action_terms = (
        "hãy ", "hay ", "giúp ", "giup ", "tính ", "tinh ", "phân tích ", "phan tich ",
        "lập ", "lap ", "kiểm tra ", "kiem tra ", "so sánh ", "so sanh ", "giải thích ",
        "giai thich ", "định khoản ", "dinh khoan ", "đề xuất ", "de xuat ", "xuất ", "xuat ",
    )
    action_lines = [line.strip() for line in text.splitlines() if line.strip().lower().startswith(action_terms)]
    if len(action_lines) > 1:
        candidates.extend(action_lines)

    tasks = _dedupe(candidates)
    if len(tasks) <= 1:
        # Conservative clause split for very long one-paragraph prompts.
        if len(text) >= 1200:
            clauses = re.split(r"\s*(?:;|\n{2,}|\.(?=\s+(?:Hãy|Giúp|Tính|Phân tích|Lập|Kiểm tra|So sánh|Giải thích)))\s*", text, flags=re.I)
            tasks = _dedupe(clauses)

    if not tasks:
        return [text]

    # Preserve the full request when splitting looks unreliable.
    coverage = sum(len(t) for t in tasks) / max(1, len(text))
    if len(tasks) <= 1 or coverage < 0.30:
        return [text]
    return tasks[:max_tasks]


def analyze_request(question: str) -> Dict[str, Any]:
    text = str(question or "")
    tasks = split_long_request(text)
    chars = len(text)
    words = len(text.split())
    numeric_count = len(re.findall(r"\d", text))
    file_terms = bool(re.search(r"\b(file|tệp|tep|pdf|word|excel|xlsx|docx|báo cáo|bao cao|xuất file|xuat file)\b", text, flags=re.I))
    calculation_terms = bool(re.search(r"\b(tính|tinh|bao nhiêu|bao nhieu|%|vat|lợi nhuận|loi nhuan|khấu hao|khau hao|hòa vốn|hoa von|lãi suất|lai suat)\b", text, flags=re.I))
    complexity_score = 0
    complexity_score += min(4, chars // 800)
    complexity_score += min(3, max(0, len(tasks) - 1))
    complexity_score += 1 if numeric_count >= 8 else 0
    complexity_score += 1 if file_terms else 0
    complexity_score += 1 if calculation_terms and numeric_count else 0
    is_complex = chars >= 1000 or len(tasks) >= 3 or complexity_score >= 4
    return {
        "version": VERSION,
        "char_count": chars,
        "word_count": words,
        "numeric_count": numeric_count,
        "task_count": len(tasks),
        "tasks": tasks,
        "contains_file_request": file_terms,
        "contains_calculation": calculation_terms and numeric_count > 0,
        "complexity_score": complexity_score,
        "is_complex": is_complex,
        "recommended_mode": "chief_accountant" if is_complex else "auto",
    }


def chunk_text(text: str, size: int = 1800, overlap: int = 220) -> List[Tuple[int, str]]:
    clean = re.sub(r"\r\n?", "\n", str(text or ""))
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
    if not clean:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", clean) if p.strip()]
    chunks: List[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= size:
            current = (current + "\n\n" + paragraph).strip()
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= size:
            current = paragraph
        else:
            start = 0
            while start < len(paragraph):
                chunks.append(paragraph[start:start + size].strip())
                start += max(1, size - overlap)
            current = ""
    if current:
        chunks.append(current)
    return list(enumerate(chunks))


def _chunk_score(query: str, chunk: str, index: int, total: int) -> float:
    q = tokens(query)
    c = tokens(chunk)
    if not c:
        return 0.0
    qset, cset = set(q), set(c)
    score = float(len(qset & cset)) * 2.0
    nq, nc = normalize(query), normalize(chunk)
    for phrase in re.findall(r"[a-z0-9]+(?:\s+[a-z0-9]+){1,4}", nq):
        if len(phrase) >= 8 and phrase in nc:
            score += 2.5
    if re.search(r"\d", query) and re.search(r"\d", chunk):
        score += 0.7
    # Always retain a little document framing.
    if index == 0:
        score += 1.2
    if total > 2 and index == total - 1:
        score += 0.3
    return score


def select_relevant_chunks(text: str, query: str, max_chars: int = 30000, max_chunks: int = 18) -> List[Dict[str, Any]]:
    chunks = chunk_text(text)
    if not chunks:
        return []
    total = len(chunks)
    q = normalize(query)
    summary_request = not q or any(term in q for term in ["tom tat", "toan bo", "doc file", "phan tich tong the", "bao cao tong hop"])
    ranked: List[Tuple[float, int, str]] = []
    for index, chunk in chunks:
        ranked.append((_chunk_score(query, chunk, index, total), index, chunk))
    ranked.sort(key=lambda row: (row[0], -row[1]), reverse=True)

    selected: List[Tuple[float, int, str]] = []
    if summary_request:
        sample_indices = sorted({0, min(1, total - 1), total // 3, total // 2, (2 * total) // 3, total - 1})
        by_index = {idx: chunk for idx, chunk in chunks}
        selected.extend((_chunk_score(query, by_index[idx], idx, total), idx, by_index[idx]) for idx in sample_indices if idx in by_index)
    selected.extend(ranked)

    output: List[Dict[str, Any]] = []
    used = 0
    seen = set()
    for score, index, chunk in selected:
        if index in seen:
            continue
        if output and used + len(chunk) > max_chars:
            continue
        seen.add(index)
        output.append({"chunk_index": index, "score": round(score, 3), "content": chunk})
        used += len(chunk)
        if len(output) >= max_chunks or used >= max_chars:
            break
    output.sort(key=lambda row: row["chunk_index"])
    return output


def build_attachment_context(
    question: str,
    files: Sequence[Dict[str, Any]],
    max_total_chars: Optional[int] = None,
) -> Dict[str, Any]:
    max_total = int(max_total_chars or os.getenv("FINIIP_ATTACHMENT_CONTEXT_CHARS", "60000"))
    per_file = max(6000, max_total // max(1, len(files)))
    blocks: List[str] = []
    manifest: List[Dict[str, Any]] = []
    used = 0
    for file_index, item in enumerate(files, 1):
        filename = str(item.get("filename") or item.get("file_name") or f"file_{file_index}")
        text = str(item.get("text") or item.get("extracted_text") or "")
        selected = select_relevant_chunks(text, question, max_chars=min(per_file, max_total - used), max_chunks=20)
        content_parts = [f"[TỆP {file_index}: {filename} | ĐOẠN {row['chunk_index'] + 1}]\n{row['content']}" for row in selected]
        content = "\n\n".join(content_parts)
        if not content:
            continue
        if used + len(content) > max_total:
            content = content[: max(0, max_total - used)]
        blocks.append(content)
        used += len(content)
        manifest.append({
            "file_index": file_index,
            "filename": filename,
            "text_length": len(text),
            "selected_chunks": [row["chunk_index"] for row in selected],
            "selected_characters": len(content),
        })
        if used >= max_total:
            break
    return {"context": "\n\n".join(blocks), "manifest": manifest, "context_characters": used}


def strip_source_markers(text: str) -> str:
    return re.sub(r"\[(\d+)\]", "", str(text or "")).strip()


def merge_citations(groups: Sequence[Sequence[Dict[str, Any]]], limit: int = 24) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen = set()
    for group in groups:
        for item in group or []:
            key = (
                str(item.get("document_id") or item.get("title") or item.get("document_title") or ""),
                str(item.get("chunk_id") or item.get("chunk_no") or ""),
                str(item.get("excerpt") or item.get("content") or "")[:160],
            )
            if key in seen:
                continue
            seen.add(key)
            row = dict(item)
            row["index"] = len(merged) + 1
            merged.append(row)
            if len(merged) >= limit:
                return merged
    return merged


def combine_subanswers(question: str, task_results: Sequence[Dict[str, Any]]) -> str:
    lines = ["Mình đã tách yêu cầu dài thành từng phần để tránh bỏ sót:", ""]
    for index, item in enumerate(task_results, 1):
        task = str(item.get("task") or f"Phần {index}").strip()
        answer = strip_source_markers(item.get("answer") or "Chưa có kết quả.")
        lines.extend([f"## {index}. {task}", "", answer, ""])
    lines.extend([
        "## Kết luận và việc cần kiểm tra",
        "",
        "- Đối chiếu lại số liệu đầu vào và các giả định đã dùng.",
        "- Với quy định pháp luật, thuế suất, thời hạn hoặc mức phạt, cần kiểm tra nguồn chính thức còn hiệu lực.",
        "- Với bút toán hoặc báo cáo, cần rà soát chứng từ và chính sách kế toán của doanh nghiệp trước khi ghi sổ.",
    ])
    return "\n".join(lines).strip()


def synthesize_subanswers_with_llm(
    *,
    question: str,
    history: str,
    task_results: Sequence[Dict[str, Any]],
    source_context: str = "",
) -> Optional[str]:
    if not os.getenv("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        max_tokens = int(os.getenv("FINIIP_LLM_MAX_OUTPUT_TOKENS", "4000"))
        task_text = "\n\n".join(
            f"PHẦN {index}: {item.get('task')}\nKẾT QUẢ ENGINE:\n{strip_source_markers(item.get('answer') or '')}"
            for index, item in enumerate(task_results, 1)
        )
        system = (
            "Bạn là Finiip, trợ lý AI thuộc CTCP IIP Việt Nam. Bạn xử lý yêu cầu cực dài theo vai trò kế toán trưởng, "
            "chuyên viên phân tích và trợ lý báo cáo. Không được bỏ sót phần việc. Trả lời bằng tiếng Việt, có tiêu đề, "
            "kết luận, công thức hoặc bảng diễn giải khi có số liệu, quy trình hành động và rủi ro. Không bịa quy định, "
            "thuế suất, thời hạn, mức phạt hay dữ kiện không có. Không liệt kê đường dẫn file nội bộ hoặc mục nguồn ở cuối."
        )
        user = (
            f"LỊCH SỬ LIÊN QUAN:\n{str(history or '')[-12000:]}\n\n"
            f"YÊU CẦU GỐC:\n{question}\n\n"
            f"CÁC PHẦN ĐÃ PHÂN TÍCH:\n{task_text}\n\n"
            f"NGUỒN/TỆP LIÊN QUAN (nếu có):\n{source_context[:16000] or '(không có)'}\n\n"
            "Hãy hợp nhất thành một câu trả lời hoàn chỉnh, nhất quán; giữ rõ từng phần việc và nêu giả định khi thiếu dữ liệu."
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.15,
            max_tokens=max_tokens,
        )
        text = str(response.choices[0].message.content or "").strip()
        return text or None
    except Exception:
        return None
