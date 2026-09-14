from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_api_contract_and_documentation():
    settings = Settings(_env_file=None, app_name="Test CRM API", cors_origins=[])
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert client.get("/").json() == {"name": "Test CRM API", "docs": "/docs"}
        schema = client.get("/openapi.json").json()
        assert schema["info"]["title"] == "Test CRM API"
        assert "/api/v1/health" in schema["paths"]
        assert client.get("/docs").status_code == 200
        assert client.get("/missing").status_code == 404


def test_cors_allows_only_configured_origin():
    settings = Settings(_env_file=None, cors_origins=["http://localhost:3000"])
    with TestClient(create_app(settings)) as client:
        allowed = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
        denied = client.get(
            "/api/v1/health", headers={"Origin": "https://unconfigured.example"}
        )
        assert "access-control-allow-origin" not in denied.headers
