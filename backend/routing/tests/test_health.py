from rest_framework.test import APIClient


def test_health_endpoint():
    resp = APIClient().get("/api/health/")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}