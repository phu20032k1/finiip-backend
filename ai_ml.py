"""Finiip AI Level 3 - lightweight trainable classifier.

This module intentionally avoids heavy ML dependencies so the backend can run
with the current requirements. It implements a small Multinomial Naive Bayes
text classifier over Vietnamese-normalized transaction descriptions.
"""

from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

MODEL_VERSION = "level3-naive-bayes-v1"
DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(__file__), "ai_models", "transaction_classifier.json")

STOPWORDS = {
    "thang", "nam", "ngay", "cho", "cua", "va", "voi", "bang", "tu", "den", "da",
    "theo", "mot", "cac", "khoan", "tien", "thanh", "toan", "chi", "thu", "nhan",
    "phi", "tra", "mua", "ban", "hang", "hoa", "don", "chung", "tu",
}


def normalize_text(value: Optional[str]) -> str:
    value = (value or "").lower().strip()
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = value.replace("đ", "d")
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def tokenize(value: Optional[str]) -> List[str]:
    normalized = normalize_text(value)
    return [token for token in normalized.split() if len(token) >= 2 and token not in STOPWORDS]


def make_label(category: str, transaction_type: str, debit: str, credit: str) -> str:
    return "||".join([category.strip(), transaction_type.strip(), debit.strip(), credit.strip()])


def split_label(label: str) -> Dict[str, str]:
    parts = (label or "").split("||")
    while len(parts) < 4:
        parts.append("")
    return {
        "category": parts[0],
        "transaction_type": parts[1],
        "debit_account_code": parts[2],
        "credit_account_code": parts[3],
    }


def build_training_examples_from_corrections(corrections: Iterable[Any]) -> List[Dict[str, Any]]:
    examples: List[Dict[str, Any]] = []
    seen = set()
    for correction in corrections:
        description = getattr(correction, "original_description", None)
        category = getattr(correction, "user_category", None)
        transaction_type = getattr(correction, "user_type", None)
        debit = getattr(correction, "user_debit_account_code", None)
        credit = getattr(correction, "user_credit_account_code", None)
        amount = float(getattr(correction, "original_amount", 0) or 0)
        if not all([description, category, transaction_type, debit, credit]):
            continue
        key = (normalize_text(description), category, transaction_type, debit, credit)
        if key in seen:
            continue
        seen.add(key)
        examples.append({
            "description": description,
            "amount": amount,
            "category": category,
            "transaction_type": transaction_type,
            "debit_account_code": debit,
            "credit_account_code": credit,
        })
    return examples


def train_naive_bayes(examples: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if not examples:
        raise ValueError("Cần ít nhất 1 ví dụ đã gán nhãn để train model")

    label_doc_counts: Counter[str] = Counter()
    label_token_counts: Dict[str, Counter[str]] = defaultdict(Counter)
    label_total_tokens: Counter[str] = Counter()
    vocabulary = set()

    for example in examples:
        label = make_label(
            str(example["category"]),
            str(example["transaction_type"]),
            str(example["debit_account_code"]),
            str(example["credit_account_code"]),
        )
        tokens = tokenize(example.get("description"))
        # Amount buckets provide a small signal without overfitting exact money values.
        amount = float(example.get("amount") or 0)
        if amount >= 20_000_000:
            tokens.append("amount_high")
        elif amount >= 5_000_000:
            tokens.append("amount_medium")
        else:
            tokens.append("amount_low")
        if not tokens:
            tokens = ["unknown_text"]

        label_doc_counts[label] += 1
        label_token_counts[label].update(tokens)
        label_total_tokens[label] += len(tokens)
        vocabulary.update(tokens)

    return {
        "version": MODEL_VERSION,
        "trained_at": datetime.utcnow().isoformat() + "Z",
        "example_count": len(examples),
        "label_count": len(label_doc_counts),
        "labels": dict(label_doc_counts),
        "token_counts": {label: dict(counter) for label, counter in label_token_counts.items()},
        "total_tokens": dict(label_total_tokens),
        "vocabulary": sorted(vocabulary),
    }


def save_model(model: Dict[str, Any], path: str = DEFAULT_MODEL_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, indent=2)


def load_model(path: str = DEFAULT_MODEL_PATH) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def model_status(path: str = DEFAULT_MODEL_PATH) -> Dict[str, Any]:
    model = load_model(path)
    if not model:
        return {
            "trained": False,
            "model_path": path,
            "message": "Chưa có model. Hãy dạy AI bằng /ai/teach hoặc correction, rồi gọi /ai/ml/train.",
        }
    return {
        "trained": True,
        "model_path": path,
        "version": model.get("version"),
        "trained_at": model.get("trained_at"),
        "example_count": model.get("example_count", 0),
        "label_count": model.get("label_count", 0),
        "labels": model.get("labels", {}),
    }


def _softmax(log_scores: Dict[str, float]) -> Dict[str, float]:
    max_score = max(log_scores.values())
    exps = {label: math.exp(score - max_score) for label, score in log_scores.items()}
    total = sum(exps.values()) or 1.0
    return {label: value / total for label, value in exps.items()}


def predict_with_model(description: str, amount: float = 0, model: Optional[Dict[str, Any]] = None, path: str = DEFAULT_MODEL_PATH) -> Optional[Dict[str, Any]]:
    model = model or load_model(path)
    if not model:
        return None
    labels: Dict[str, int] = {k: int(v) for k, v in (model.get("labels") or {}).items()}
    if not labels:
        return None

    tokens = tokenize(description)
    amount = float(amount or 0)
    if amount >= 20_000_000:
        tokens.append("amount_high")
    elif amount >= 5_000_000:
        tokens.append("amount_medium")
    else:
        tokens.append("amount_low")
    if not tokens:
        tokens = ["unknown_text"]

    vocabulary = set(model.get("vocabulary") or [])
    vocab_size = max(1, len(vocabulary))
    total_docs = sum(labels.values()) or 1
    token_counts: Dict[str, Dict[str, int]] = model.get("token_counts") or {}
    total_tokens: Dict[str, int] = {k: int(v) for k, v in (model.get("total_tokens") or {}).items()}

    log_scores: Dict[str, float] = {}
    for label, doc_count in labels.items():
        prior = math.log((doc_count + 1) / (total_docs + len(labels)))
        denom = total_tokens.get(label, 0) + vocab_size
        score = prior
        counts = token_counts.get(label, {})
        for token in tokens:
            score += math.log((int(counts.get(token, 0)) + 1) / denom)
        log_scores[label] = score

    probabilities = _softmax(log_scores)
    ranked: List[Tuple[str, float]] = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
    best_label, confidence = ranked[0]
    parsed = split_label(best_label)
    alternatives = []
    for label, prob in ranked[1:4]:
        item = split_label(label)
        item["confidence"] = round(prob, 4)
        alternatives.append(item)

    return {
        **parsed,
        "debit_account": parsed["debit_account_code"],
        "credit_account": parsed["credit_account_code"],
        "amount": amount,
        "confidence": round(float(confidence), 4),
        "source": "ml_model",
        "model_version": model.get("version"),
        "trained_at": model.get("trained_at"),
        "tokens": tokens,
        "alternatives": alternatives,
        "warnings": ["Kết quả từ model học máy nhẹ - nên kiểm tra trước khi confirmed"],
        "journal_lines": [
            {"side": "debit", "account_code": parsed["debit_account_code"], "account_name": "Unknown", "amount": amount},
            {"side": "credit", "account_code": parsed["credit_account_code"], "account_name": "Unknown", "amount": amount},
        ],
    }
