"""Offline smoke test for Finiip AI V4 helpers.
Run after starting the API if you want endpoint tests through /docs or curl.
This script only checks that sample CSV exists and documents expected API payloads.
"""
from pathlib import Path
import csv

sample = Path("data/sample_bank_statement_v4.csv")
assert sample.exists(), "Missing data/sample_bank_statement_v4.csv"
with sample.open("r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
assert len(rows) >= 5, "Sample bank statement should include at least 5 rows"
assert any("Facebook" in r.get("nội dung", "") for r in rows), "Missing Facebook demo row"
print("OK - AI V4 sample file is ready.")
print("Next: run uvicorn main:app --reload and test POST /ai/v4/import-preview in /docs")
