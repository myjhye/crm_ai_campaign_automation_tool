from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_survives_missing_database():
    with TestClient(create_app(Settings(_env_file=None, database_url=None))) as client:
        assert client.get("/api/v1/health").status_code == 200
        result = client.get("/api/v1/ready")
        assert result.status_code == 503
        assert result.json()["error"]["code"] == "DATABASE_UNAVAILABLE"


def test_readiness_handles_database_connection_failure():
    settings = Settings(_env_file=None,
                        database_url="postgresql+psycopg://invalid:secret@127.0.0.1:1/unreachable")
    with TestClient(create_app(settings)) as client:
        result = client.get("/api/v1/ready")
        assert result.status_code == 503
        assert "secret" not in result.text
        assert client.get("/api/v1/health").status_code == 200
