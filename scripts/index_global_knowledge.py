from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "knowledge_base"
OUT_FILE = ROOT / "data" / "rag_index.json"


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized
    end = normalized.find("\n---\n", 4)
    if end < 0:
        return {}, normalized
    block = normalized[4:end]
    body = normalized[end + 5 :]
    metadata: dict[str, Any] = {}
    current_list_key: str | None = None
    for line in block.splitlines():
        if re.match(r"^\s*-\s+", line) and current_list_key:
            value = re.sub(r"^\s*-\s+", "", line).strip().strip('"\'')
            metadata.setdefault(current_list_key, []).append(value)
            continue
        match = re.match(r"^([A-Za-z0-9_\-]+)\s*:\s*(.*)$", line)
        if not match:
            continue
        key, raw_value = match.group(1), match.group(2).strip()
        if not raw_value:
            metadata[key] = []
            current_list_key = key
        else:
            metadata[key] = raw_value.strip('"\'')
            current_list_key = None
    return metadata, body


def split_markdown_by_headings(text: str, max_chars: int = 1800) -> list[dict[str, str]]:
    """Split Markdown by any heading level and preserve heading context."""
    lines = text.splitlines()
    title = ""
    sections: list[tuple[str, list[str]]] = []
    current_heading = ""
    current_lines: list[str] = []

    for line in lines:
        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading_match:
            heading_text = heading_match.group(2).strip()
            if not title:
                title = heading_text
            if current_lines:
                sections.append((current_heading or title, current_lines))
            current_heading = heading_text
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading or title, current_lines))

    chunks: list[dict[str, str]] = []
    for heading, section_lines in sections:
        section_text = normalize_text("\n".join(section_lines))
        if not section_text:
            continue
        if len(section_text) <= max_chars:
            chunks.append({"title": title or heading, "heading": heading, "content": section_text})
            continue
        start = 0
        overlap = 180
        while start < len(section_text):
            part = section_text[start : start + max_chars].strip()
            if part:
                chunks.append({"title": title or heading, "heading": heading, "content": part})
            start += max_chars - overlap
    return chunks


def infer_source_type(relative_path: str, metadata: dict[str, Any]) -> str:
    explicit = str(metadata.get("source_type") or metadata.get("doc_type") or "").lower()
    if explicit in {"law", "legal", "circular", "decree", "tax_legal", "thong_tu"}:
        return "accounting_law"
    if "/legal/" in f"/{relative_path}":
        return "accounting_law"
    if "/policies/" in f"/{relative_path}":
        return "ai_policy"
    return "accounting_knowledge"


def index_files() -> list[dict[str, Any]]:
    if not KB_DIR.exists():
        raise FileNotFoundError(f"Không thấy thư mục knowledge base: {KB_DIR}")

    all_chunks: list[dict[str, Any]] = []
    md_files = sorted(KB_DIR.rglob("*.md"))

    for file_path in md_files:
        raw = file_path.read_text(encoding="utf-8", errors="ignore")
        metadata, body = parse_front_matter(raw)
        text = normalize_text(body)
        chunks = split_markdown_by_headings(text)
        relative_path = file_path.relative_to(ROOT).as_posix()
        source_type = infer_source_type(relative_path, metadata)

        for idx, chunk in enumerate(chunks, start=1):
            chunk_id = f"{relative_path}::chunk_{idx}"
            all_chunks.append(
                {
                    "id": chunk_id,
                    "file_name": file_path.name,
                    "path": relative_path,
                    "source_type": source_type,
                    "chunk_index": idx,
                    "title": str(metadata.get("title") or chunk["title"] or file_path.stem),
                    "heading": chunk["heading"],
                    "content": chunk["content"],
                    "metadata": metadata,
                    "status": metadata.get("status", "active"),
                    "effective_from": metadata.get("effective_from") or metadata.get("effective_date"),
                    "source_completeness": metadata.get("source_completeness", "full_internal_note"),
                }
            )

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    return all_chunks


if __name__ == "__main__":
    chunks = index_files()
    print(f"✅ Đã index {len(chunks)} chunks từ toàn bộ knowledge_base")
    print(f"📄 File index: {OUT_FILE}")
    for c in chunks[:8]:
        print(f"- {c['file_name']} | {c['heading']} | {len(c['content'])} ký tự")
