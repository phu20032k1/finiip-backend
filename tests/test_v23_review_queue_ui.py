from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_v23_review_queue_ui_available():
    res = client.get('/v23/review-queue-ui')
    assert res.status_code == 200
    assert 'Finiip V23 - AI Review Queue' in res.text
    assert '/ai/v19/review-queue' in res.text


def test_v23_review_ui_status_contract():
    res = client.get('/ai/v23/review-ui/status')
    assert res.status_code == 200
    data = res.json()
    assert data['stage'] == 'V23 - Frontend AI Review Queue'
    assert data['ui_url'] == '/v23/review-queue-ui'
    assert 'review_pending' in data['counts']
