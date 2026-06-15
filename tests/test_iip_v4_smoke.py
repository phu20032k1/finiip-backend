"""Smoke tests for IIP Steel Backend V4.
Run after installing requirements: pytest tests/test_iip_v4_smoke.py
"""
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_v4_status():
    r = client.get('/iip/v4/status')
    assert r.status_code == 200
    assert r.json()['version'] == 'v4'


def test_seed_v4_and_roadmap():
    r = client.post('/iip/demo/seed-v4')
    assert r.status_code == 200
    r = client.get('/iip/v4/roadmap/completion-score')
    assert r.status_code == 200
    assert r.json()['backend_logic_score'] >= 90


def test_login_admin_after_seed():
    client.post('/iip/demo/seed-v4')
    r = client.post('/iip/v3/auth/login', json={'username': 'admin', 'password': 'admin123'})
    assert r.status_code == 200
    assert 'access_token' in r.json()
