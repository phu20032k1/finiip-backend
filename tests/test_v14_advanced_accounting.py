import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_v14_inventory_fifo_and_weighted_average():
    fifo = client.post('/formulas/inventory/fifo', json={
        'beginning_layers': [
            {'quantity': 10, 'unit_cost': 100000, 'label': 'old'},
            {'quantity': 5, 'unit_cost': 120000, 'label': 'new'},
        ],
        'purchases': [{'quantity': 10, 'unit_cost': 150000, 'label': 'purchase_may'}],
        'sales_quantity': 12,
    })
    assert fifo.status_code == 200
    result = fifo.json()['result']
    assert result['cogs'] == 1240000
    assert result['ending_quantity'] == 13
    assert result['ending_inventory_value'] == 1860000

    avg = client.post('/formulas/inventory/weighted-average', json={
        'beginning_quantity': 10,
        'beginning_value': 1000000,
        'purchases': [{'quantity': 10, 'amount': 1500000}],
        'sales_quantity': 8,
    })
    assert avg.status_code == 200
    result = avg.json()['result']
    assert result['average_unit_cost'] == 125000
    assert result['cogs'] == 1000000
    assert result['ending_inventory_value'] == 1500000


def test_v14_payroll_aging_and_closing():
    payroll = client.post('/formulas/payroll/basic', json={
        'gross_salary': 10000000,
        'personal_income_tax': 500000,
    })
    assert payroll.status_code == 200
    result = payroll.json()['result']
    assert result['employee_deductions']['total'] == 1550000
    assert result['net_salary'] == 8450000
    assert result['employer_contributions']['total'] == 2150000

    aging = client.post('/formulas/accounts/aging', json={
        'as_of': '2026-05-27',
        'items': [
            {'name': 'Customer A', 'amount': 1000000, 'due_date': '2026-05-20'},
            {'name': 'Customer B', 'amount': 2000000, 'due_date': '2026-02-01'},
            {'name': 'Customer C', 'amount': 3000000, 'due_date': '2026-06-01'},
        ],
    })
    assert aging.status_code == 200
    buckets = aging.json()['result']['buckets']
    assert buckets['0_30'] == 1000000
    assert buckets['over_90'] == 2000000
    assert buckets['not_due'] == 3000000

    closing = client.post('/formulas/closing/period', json={
        'revenue': 100000000,
        'cogs': 45000000,
        'selling_expenses': 10000000,
        'admin_expenses': 15000000,
        'tax_expense': 6000000,
    })
    assert closing.status_code == 200
    result = closing.json()['result']
    assert result['net_profit'] == 24000000
    assert any(e['credit_account_code'] == '421' for e in result['entries'])


def test_v14_basic_financial_statements_and_catalog():
    response = client.post('/formulas/statements/basic', json={
        'cash': 20000000,
        'receivables': 10000000,
        'inventory': 15000000,
        'fixed_assets': 50000000,
        'accumulated_depreciation': 5000000,
        'payables': 10000000,
        'loans': 20000000,
        'owner_equity': 40000000,
        'revenue': 100000000,
        'cogs': 45000000,
        'operating_expenses': 25000000,
        'tax_expense': 6000000,
    })
    assert response.status_code == 200
    result = response.json()['result']
    assert result['income_statement']['net_profit'] == 24000000
    assert result['balance_sheet']['assets']['total_assets'] == 90000000
    assert result['balance_sheet']['liabilities_and_equity'] == 94000000
    assert result['balance_sheet']['balanced'] is False

    catalog = client.get('/formulas/catalog')
    assert catalog.status_code == 200
    assert catalog.json()['count'] >= 15
