import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_v13_formula_catalog_and_vat():
    catalog = client.get('/formulas/catalog')
    assert catalog.status_code == 200
    assert catalog.json()['count'] >= 8

    response = client.post('/formulas/vat', json={
        'subtotal': 2000000,
        'vat_rate': 10,
    })
    assert response.status_code == 200
    result = response.json()['result']
    assert result['vat_amount'] == 200000
    assert result['total'] == 2200000
    assert result['balanced'] is True


def test_v13_depreciation_and_prepaid_allocation():
    dep = client.post('/formulas/depreciation', json={
        'cost': 36000000,
        'salvage_value': 0,
        'useful_life_months': 36,
        'months_used': 6,
    })
    assert dep.status_code == 200
    assert dep.json()['result']['monthly_depreciation'] == 1000000
    assert dep.json()['result']['accumulated_depreciation'] == 6000000

    prepaid = client.post('/formulas/prepaid-allocation', json={
        'total_amount': 12000000,
        'allocation_months': 12,
        'months_allocated': 3,
    })
    assert prepaid.status_code == 200
    assert prepaid.json()['result']['monthly_allocation'] == 1000000
    assert prepaid.json()['result']['remaining_amount'] == 9000000


def test_v13_profit_tax_ratios_and_balance():
    net = client.post('/formulas/profit/net', json={
        'revenue': 100000000,
        'cogs': 45000000,
        'operating_expenses': 25000000,
        'tax_expense': 6000000,
    })
    assert net.status_code == 200
    assert net.json()['result']['net_profit'] == 24000000

    cit = client.post('/formulas/tax/cit', json={
        'profit_before_tax': 30000000,
        'tax_rate': 20,
    })
    assert cit.status_code == 200
    assert cit.json()['result']['tax_expense'] == 6000000

    balance = client.post('/formulas/journal/check-balance', json={
        'lines': [
            {'side': 'debit', 'account_code': '642', 'amount': 2000000},
            {'side': 'debit', 'account_code': '1331', 'amount': 200000},
            {'side': 'credit', 'account_code': '112', 'amount': 2200000},
        ]
    })
    assert balance.status_code == 200
    assert balance.json()['result']['balanced'] is True

    ratios = client.post('/formulas/ratios', json={
        'current_assets': 50000000,
        'current_liabilities': 25000000,
        'total_assets': 100000000,
        'total_liabilities': 40000000,
        'equity': 60000000,
        'revenue': 100000000,
        'net_profit': 20000000,
    })
    assert ratios.status_code == 200
    assert ratios.json()['result']['current_ratio'] == 2
    assert ratios.json()['result']['net_margin'] == 0.2
