import base64

from fastapi.testclient import TestClient

from app.main import app


def header(password: str) -> dict:
    return {"Authorization": "Basic " + base64.b64encode(f"anyone:{password}".encode()).decode()}


def test_no_password_set_means_open_access(monkeypatch):
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    assert TestClient(app).get("/").status_code == 200


def test_password_is_required_when_set(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    client = TestClient(app)

    assert client.get("/").status_code == 401
    assert client.get("/", headers=header("wrong")).status_code == 401
    assert client.get("/", headers=header("s3cret")).status_code == 200
    assert client.get("/health").status_code == 200  # stays open for health checks


def test_garbage_authorization_header_is_rejected(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    assert TestClient(app).get("/", headers={"Authorization": "Basic !!!"}).status_code == 401
