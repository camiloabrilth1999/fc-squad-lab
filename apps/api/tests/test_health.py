from fastapi.testclient import TestClient

from fcsl_api.main import app


def test_health_ok():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_cors_allows_web_origin():
    response = TestClient(app).get("/health", headers={"Origin": "http://localhost:3030"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3030"


def test_health_reports_db_down(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://fcsl:fcsl@localhost:5599/fcsl")
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "down"}
