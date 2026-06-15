"""Smoke test backend IIP without starting uvicorn.
Run: python scripts/test_iip_backend.py
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import main

client = TestClient(main.app)

checks = [
    ("GET", "/iip/status"),
    ("POST", "/iip/demo/seed"),
    ("GET", "/iip/chairman/morning-report"),
    ("GET", "/iip/risk/overdue-debts"),
    ("GET", "/iip/risk/credit-limit-violations"),
    ("GET", "/iip/risk/low-price-sales"),
    ("GET", "/iip/reconcile/4-way"),
    ("GET", "/iip/vas/progress"),
]

ok = True
for method, path in checks:
    response = client.request(method, path)
    passed = 200 <= response.status_code < 300
    ok = ok and passed
    print(f"{method:4} {path:45} -> {response.status_code} {'OK' if passed else 'FAIL'}")
    if not passed:
        print(response.text[:500])

raise SystemExit(0 if ok else 1)
