from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_reports_both_dependencies() -> None:
    response = client.get("/api/health")
    body = response.json()

    assert response.status_code == 200
    assert body["status"] in {"ok", "degraded"}
    assert set(body) == {
        "status",
        "app",
        "environment",
        "supabase_configured",
        "database_connected",
    }


def test_protected_route_rejects_anonymous() -> None:
    assert client.get("/api/users/me").status_code == 401


def test_protected_route_rejects_bad_token() -> None:
    response = client.get(
        "/api/users/me", headers={"Authorization": "Bearer not-a-token"}
    )
    assert response.status_code == 401
