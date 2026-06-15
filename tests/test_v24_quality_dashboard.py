from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_v24_quality_dashboard_api_contract():
    res = client.get('/ai/v24/quality-dashboard')
    assert res.status_code == 200
    data = res.json()
    assert data['stage'] == 'V24 - Dashboard chất lượng AI kế toán'
    assert data['ui_url'] == '/v24/quality-dashboard-ui'
    assert 'summary' in data
    assert 'rates' in data
    assert 'status_counts' in data
    assert 'priority_counts' in data
    assert 'confidence_buckets' in data
    assert 'recommendations' in data
    assert 'quality_score' in data['summary']


def test_v24_quality_dashboard_ui_available():
    res = client.get('/v24/quality-dashboard-ui')
    assert res.status_code == 200
    assert 'Finiip V24 - AI Quality Dashboard' in res.text
    assert '/ai/v24/quality-dashboard' in res.text
