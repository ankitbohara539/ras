from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_liveness_does_not_depend_on_external_services() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app": "CivicGrid API",
        "environment": "development",
    }
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-request-id"]


def test_api_root_is_descriptive() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["health"] == "/health/live"
