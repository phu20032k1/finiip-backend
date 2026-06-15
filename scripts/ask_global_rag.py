from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from legal_prompt import build_legal_rag_prompt
from services.question_analyzer import analyze_question
from services.accounting_solver import solve_calculation

INDEX_FILE = ROOT / "data" / "rag_index.json"

STOPWORDS = {
    "là", "và", "có", "của", "cho", "với", "theo", "được", "không", "nào", "như", "thế",
    "khi", "thì", "về", "tôi", "bạn", "mình", "này", "đó", "các", "một", "trong", "ra",
    "sao", "hỏi", "giúp", "phải", "cần", "nếu", "để", "từ", "vào", "hay", "hoặc", "doanh",
    "nghiệp", "nho", "nhỏ", "sieu", "siêu"
}


def strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def normalize_text(text: str) -> str:
    return strip_accents(text.lower())


def tokenize(text: str) -> list[str]:
    text = normalize_text(text)
    tokens = re.findall(r"[a-z0-9\.]+", text)
    return [t for t in tokens if len(t) >= 2 and t not in STOPWORDS]


def score(query: str, content: str) -> float:
    q_tokens = tokenize(query)
    c_tokens = tokenize(content)
    if not q_tokens or not c_tokens:
        return 0.0

    q_counter = Counter(q_tokens)
    c_counter = Counter(c_tokens)
    common = set(q_counter) & set(c_counter)

    overlap_score = sum(q_counter[t] * c_counter[t] for t in common)
    coverage = len(common) / max(len(set(q_tokens)), 1)
    length_penalty = 1 / math.sqrt(max(len(c_tokens), 1))

    return overlap_score * 0.15 + coverage * 3 + length_penalty


def load_index() -> list[dict]:
    if not INDEX_FILE.exists():
        raise FileNotFoundError(
            f"Chưa thấy {INDEX_FILE}. Hãy chạy trước: python scripts/index_global_knowledge.py"
        )
    return json.loads(INDEX_FILE.read_text(encoding="utf-8"))


def search_rag(question: str, top_k: int = 3) -> list[dict]:
    chunks = load_index()
    ranked = []

    for chunk in chunks:
        searchable = " ".join([
            chunk.get("content", ""),
            chunk.get("title", ""),
            chunk.get("heading", ""),
            chunk.get("file_name", ""),
        ])
        s = score(question, searchable)
        ranked.append((s, chunk))

    ranked.sort(key=lambda x: x[0], reverse=True)

    results = []
    for s, chunk in ranked[:top_k]:
        item = dict(chunk)
        item["score"] = round(s, 4)
        results.append(item)

    return results


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?。])\s+|(?<=;)\s+", text)

    expanded: list[str] = []
    for part in parts:
        if len(part) > 600:
            expanded.extend(re.split(r"\s+(?=\d+\.|[a-z]\))", part))
        else:
            expanded.append(part)

    return [p.strip() for p in expanded if len(p.strip()) >= 30]


def best_evidence_sentences(question: str, chunks: list[dict], limit: int = 2) -> list[str]:
    q_tokens = set(tokenize(question))
    candidates: list[tuple[float, str]] = []

    for chunk in chunks:
        for sentence in split_sentences(chunk.get("content", "")):
            s_tokens = set(tokenize(sentence))
            if not s_tokens:
                continue

            common = q_tokens & s_tokens
            s = len(common) * 2.0

            normalized = normalize_text(sentence)

            for kw in [
                "khong bat buoc",
                "bat buoc",
                "phai",
                "duoc",
                "khong duoc",
                "truong hop",
                "thoi han",
                "dieu",
            ]:
                if kw in normalized:
                    s += 1.5

            candidates.append((s, sentence))

    candidates.sort(key=lambda x: x[0], reverse=True)

    picked: list[str] = []
    seen = set()

    for s, sentence in candidates:
        key = normalize_text(sentence[:120])
        if s <= 0 or key in seen:
            continue

        picked.append(sentence)
        seen.add(key)

        if len(picked) >= limit:
            break

    return picked


def detect_short_conclusion(question: str, evidence_text: str) -> str:
    q = normalize_text(question)
    e = normalize_text(evidence_text)

    if "ke toan truong" in q and "khong bat buoc phai bo tri ke toan truong" in e:
        return "Không bắt buộc."

    if ("bao cao tai chinh" in q or "bctc" in q) and "khong bat buoc phai lap bao cao tai chinh" in e:
        return "Không bắt buộc trong trường hợp nộp thuế TNDN theo tỷ lệ % trên doanh thu, trừ khi pháp luật khác yêu cầu."

    if ("bao cao tai chinh" in q or "bctc" in q) and "phai lap bao cao tai chinh" in e:
        return "Có thể phải lập báo cáo tài chính, tùy phương pháp tính thuế TNDN."

    if "ho kinh doanh" in q and "duoc lua chon ap dung thong tu nay" in e:
        return "Có thể lựa chọn áp dụng nếu có nhu cầu."

    if "khong bat buoc" in e:
        return "Không bắt buộc theo căn cứ tìm được."

    if "phai" in e:
        return "Có nghĩa vụ thực hiện theo căn cứ tìm được."

    if "duoc" in e:
        return "Được thực hiện theo căn cứ tìm được."

    return "Đã tìm thấy căn cứ liên quan trong kho RAG."


def source_label(chunk: dict) -> str:
    title = chunk.get("title") or chunk.get("file_name") or "Tài liệu RAG"
    heading = chunk.get("heading")

    if heading:
        return f"{title}, {heading}"

    return title


def make_short_answer(question: str, chunks: list[dict]) -> str:
    if not chunks or chunks[0].get("score", 0) <= 0:
        return "Chưa đủ căn cứ để kết luận vì không tìm thấy tài liệu liên quan trong kho RAG."

    top = chunks[0]
    combined = "\n".join(c.get("content", "") for c in chunks[:3])
    evidence = best_evidence_sentences(question, chunks[:3], limit=2)
    conclusion = detect_short_conclusion(question, "\n".join(evidence) or combined)

    lines = [
        f"Kết luận: {conclusion}",
        "",
        f"Căn cứ: {source_label(top)}.",
    ]

    if evidence:
        lines.append("")
        lines.append("Diễn giải: " + " ".join(evidence))
    else:
        preview = re.sub(r"\s+", " ", top.get("content", "")).strip()[:450]
        lines.append("")
        lines.append("Diễn giải: " + preview + ("..." if len(preview) >= 450 else ""))

    return "\n".join(lines).strip()


def print_debug(chunks: list[dict], prompt: str) -> None:
    print("\n==================== TOP CHUNKS ====================")

    for i, c in enumerate(chunks, start=1):
        print(f"\n[{i}] score={c['score']} | {c.get('file_name')} | {c.get('heading')}")
        content = c.get("content", "")
        print(content[:500].replace("\n", " ") + ("..." if len(content) > 500 else ""))

    print("\n==================== PROMPT GỬI CHO AI ====================")
    print(prompt)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hỏi thử Global RAG. Mặc định trả lời ngắn; dùng --debug để xem chunks và prompt."
    )

    parser.add_argument("question", nargs="+", help="Câu hỏi cần tra cứu")
    parser.add_argument("--top-k", type=int, default=3, help="Số chunk lấy từ RAG, mặc định 3")
    parser.add_argument("--debug", action="store_true", help="In TOP CHUNKS và PROMPT dài để debug")

    args = parser.parse_args()

    question = " ".join(args.question).strip()
    
    analysis = analyze_question(question)

    if analysis["intent"] == "calculation":
        print(solve_calculation(question))
        return

    if analysis["intent"] == "long_question":
        print("Mình tách câu hỏi dài thành các ý sau:\n")

        for i, sub in enumerate(analysis["sub_questions"], start=1):
            print(f"{i}. {sub['question']}")

        print("\nKết quả xử lý từng ý:\n")

        for i, sub in enumerate(analysis["sub_questions"], start=1):
            sub_q = sub["question"]
            sub_intent = sub["intent"]

            print(f"## Ý {i}: {sub_q}")

            if sub_intent == "calculation":
                print(solve_calculation(sub_q))
            else:
                chunks = search_rag(sub_q, top_k=args.top_k)
                print(make_short_answer(sub_q, chunks))

            print()

        return
    
    chunks = search_rag(question, top_k=args.top_k)

    print(make_short_answer(question, chunks))

    if args.debug:
        prompt = build_legal_rag_prompt(question, chunks)
        print_debug(chunks, prompt)


if __name__ == "__main__":
    main()
    