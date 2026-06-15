"""Seed dữ liệu học mẫu và train model AI Level 3 cho Finiip.

Cách chạy từ thư mục `copy`:
    python scripts/seed_and_train_ai.py

Script này sẽ:
1) Tạo hệ thống tài khoản mặc định nếu chưa có
2) Nạp tất cả data/ai_training_examples*.json vào bảng ai_corrections
3) Train model Naive Bayes và lưu vào ai_models/transaction_classifier.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ai_ml import build_training_examples_from_corrections, save_model, train_naive_bayes  # noqa: E402
from database import Base, SessionLocal, engine  # noqa: E402
from models import AICorrection, Account  # noqa: E402
from seed_data import DEFAULT_ACCOUNTS  # noqa: E402

DATA_DIR = ROOT_DIR / "data"
DATASET_PATTERN = "ai_training_examples*.json"


def load_items(data_dir: Path = DATA_DIR) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for path in sorted(data_dir.glob(DATASET_PATTERN)):
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        for item in payload.get("items", []):
            item = dict(item)
            item.setdefault("source_file", path.name)
            items.append(item)
    return items


def ensure_default_accounts(db) -> Dict[str, int]:
    created = 0
    skipped = 0
    for item in DEFAULT_ACCOUNTS:
        exists = db.query(Account).filter(Account.code == item["code"]).first()
        if exists:
            skipped += 1
            continue
        db.add(Account(**item))
        created += 1
    db.commit()
    return {"created": created, "skipped": skipped}


def seed_training_examples(db, items: List[Dict[str, Any]]) -> Dict[str, int]:
    created = 0
    skipped = 0
    for item in items:
        description = item["description"].strip()
        debit = str(item["user_debit_account_code"]).strip()
        credit = str(item["user_credit_account_code"]).strip()
        category = item["user_category"].strip()
        user_type = item.get("user_type", "expense").strip()

        for code in (debit, credit):
            exists = db.query(Account).filter(Account.code == code).first()
            if not exists:
                raise RuntimeError(f"Tài khoản {code} chưa tồn tại. Kiểm tra DEFAULT_ACCOUNTS hoặc dataset.")

        exists = (
            db.query(AICorrection)
            .filter(AICorrection.original_description == description)
            .filter(AICorrection.user_category == category)
            .filter(AICorrection.user_debit_account_code == debit)
            .filter(AICorrection.user_credit_account_code == credit)
            .first()
        )
        if exists:
            skipped += 1
            continue

        db.add(
            AICorrection(
                transaction_id=None,
                original_description=description,
                original_amount=float(item.get("amount") or 1),
                ai_category=None,
                ai_type=None,
                ai_debit_account_code=None,
                ai_credit_account_code=None,
                ai_confidence=None,
                user_category=category,
                user_type=user_type,
                user_debit_account_code=debit,
                user_credit_account_code=credit,
                note=item.get("note") or "Seed training example",
            )
        )
        created += 1
    db.commit()
    return {"created": created, "skipped": skipped}


def main() -> None:
    # Đảm bảo bảng đã được tạo nếu bạn chạy script trên database trống.
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        items = load_items()
        account_result = ensure_default_accounts(db)
        seed_result = seed_training_examples(db, items)
        corrections = db.query(AICorrection).order_by(AICorrection.id.asc()).all()
        examples = build_training_examples_from_corrections(corrections)
        model = train_naive_bayes(examples)
        save_model(model)

        print("✅ Đã seed và train AI thành công")
        print(f"- Tài khoản: tạo mới {account_result['created']}, bỏ qua {account_result['skipped']}")
        print(f"- Dữ liệu học từ tất cả file JSON: thêm mới {seed_result['created']}, bỏ qua {seed_result['skipped']}")
        print(f"- Tổng ví dụ train: {model['example_count']}")
        print(f"- Số nhãn kế toán: {model['label_count']}")
        print("- Model: ai_models/transaction_classifier.json")
        print("\nThử chạy server rồi test:")
        print("  uvicorn main:app --reload")
        print("  POST /ai/ml/predict")
        print("  POST /ai/analyze")
    finally:
        db.close()


if __name__ == "__main__":
    main()
