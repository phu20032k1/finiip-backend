from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.rag_storage_v101 import (  # noqa: E402
    add_uploaded_document_supabase,
    delete_document_supabase,
    list_documents_supabase,
    supabase_is_active,
)

KB_DIR = ROOT / "knowledge_base"
BUNDLE_VERSION = "v107_full_knowledge"


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
    list_key: str | None = None
    for line in block.splitlines():
        if re.match(r"^\s*-\s+", line) and list_key:
            metadata.setdefault(list_key, []).append(re.sub(r"^\s*-\s+", "", line).strip().strip('"\''))
            continue
        match = re.match(r"^([A-Za-z0-9_\-]+)\s*:\s*(.*)$", line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip()
        if value:
            metadata[key] = value.strip('"\'')
            list_key = None
        else:
            metadata[key] = []
            list_key = key
    return metadata, body


def infer_source_type(relative_path: str, metadata: dict[str, Any]) -> str:
    value = str(metadata.get("source_type") or metadata.get("doc_type") or "").lower()
    if value in {"law", "legal", "circular", "decree", "tax_legal", "thong_tu"} or "/legal/" in f"/{relative_path}":
        return "accounting_law"
    if "/policies/" in f"/{relative_path}":
        return "ai_policy"
    return "accounting_knowledge"


def main() -> int:
    parser = argparse.ArgumentParser(description="Đồng bộ Knowledge Pack V107 lên Supabase RAG")
    parser.add_argument("--workspace", default="default", help="Workspace cần đồng bộ")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ liệt kê, không thay đổi Supabase")
    args = parser.parse_args()

    files = sorted(KB_DIR.rglob("*.md"))
    if not files:
        print(f"Không tìm thấy file Markdown trong {KB_DIR}")
        return 1

    if args.dry_run:
        print(f"DRY RUN: sẽ đồng bộ {len(files)} file vào workspace={args.workspace}")
        for path in files:
            print("-", path.relative_to(ROOT).as_posix())
        return 0

    if not supabase_is_active():
        print("Supabase RAG chưa hoạt động. Hãy cấu hình SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY và RAG_STORAGE_MODE=supabase.")
        return 2

    existing = list_documents_supabase(workspace_id=args.workspace, include_deleted=True).get("items") or []
    by_path: dict[str, list[dict[str, Any]]] = {}
    for document in existing:
        metadata = document.get("metadata") or {}
        knowledge_path = str(metadata.get("knowledge_path") or "")
        if knowledge_path:
            by_path.setdefault(knowledge_path, []).append(document)

    uploaded = 0
    replaced = 0
    failed = 0
    for path in files:
        relative_path = path.relative_to(ROOT).as_posix()
        raw = path.read_text(encoding="utf-8", errors="ignore")
        front_matter, _ = parse_front_matter(raw)

        for old in by_path.get(relative_path, []):
            try:
                delete_document_supabase(str(old["document_id"]), hard_delete=True)
                replaced += 1
            except Exception as exc:
                print(f"⚠️ Không xóa được bản cũ {relative_path}: {exc}")

        title = str(front_matter.get("title") or path.stem.replace("_", " ").title())
        metadata = {
            "knowledge_path": relative_path,
            "bundled_version": BUNDLE_VERSION,
            "document_scope": "official_bundled_knowledge",
            "managed_by": "scripts/sync_knowledge_base_v107.py",
        }
        try:
            result = add_uploaded_document_supabase(
                filename=path.name,
                content=raw.encode("utf-8"),
                workspace_id=args.workspace,
                title=title,
                source_type=infer_source_type(relative_path, front_matter),
                metadata=metadata,
            )
            uploaded += 1
            print(f"✅ {relative_path}: {result.get('chunks_added', 0)} chunks")
        except Exception as exc:
            failed += 1
            print(f"❌ {relative_path}: {exc}")

    print(f"\nHoàn tất: uploaded={uploaded}, replaced={replaced}, failed={failed}, workspace={args.workspace}")
    return 0 if failed == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
