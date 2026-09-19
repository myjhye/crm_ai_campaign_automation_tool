from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_api_contract_and_documentation():
    settings = Settings(_env_file=None, app_name="Test CRM API", cors_origins=[])
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        root = client.get("/")
        assert root.status_code == 200
        assert "text/html" in root.headers["content-type"]
        assert 'lang="ko"' in root.text and 'type="module"' in root.text
        assert client.get("/api/v1/info").json() == {"name": "Test CRM API", "docs": "/docs"}
        schema = client.get("/openapi.json").json()
        assert schema["info"]["title"] == "Test CRM API"
        assert "/api/v1/health" in schema["paths"]
        assert client.get("/docs").status_code == 200
        assert client.get("/missing").status_code == 404


def test_frontend_assets_and_missing_files():
    with TestClient(create_app(Settings(_env_file=None, database_url=None))) as client:
        for asset, mime in [("styles/tokens.css", "text/css"), ("styles/layout.css", "text/css"),
                            ("styles/components.css", "text/css"), ("src/app/main.js", "javascript"),
                            ("src/api/client.js", "javascript"), ("src/features/data/index.js", "javascript")]:
            response = client.get(f"/static/{asset}")
            assert response.status_code == 200
            assert mime in response.headers["content-type"]
        assert client.get("/static/missing.js").status_code == 404
        assert client.get("/static/%2e%2e/.env").status_code == 404
        assert client.get("/static/package.json").status_code == 404


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
