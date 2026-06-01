from fastapi.testclient import TestClient
from ml_api.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "MLOps API Version 2 is running..."


def test_health_live():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_health_ready():
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_predict():
    response = client.post(
        "/predict",
        json={"features": [1.0, 2.0, 3.0]},
    )
    assert response.status_code == 200
    body = response.json()
    assert "prediction" in body
    assert "model_version" in body
