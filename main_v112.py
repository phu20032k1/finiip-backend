"""Finiip V112 application wrapper.

Keeps the existing main:app untouched and layers Accounting Suite routes on top.
"""
from main import app
from accounting_suite_v112 import router as accounting_suite_v112_router

app.include_router(accounting_suite_v112_router)
