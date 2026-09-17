from typing import Annotated
from uuid import UUID

from fastapi import Query
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import AppError
from app.main import create_app
from app.schemas.common import Pagination, ReportingPeriod


def test_error_contract_and_request_ids():
    app = create_app(Settings(_env_file=None))

    @app.get("/test/page")
    def page(query: Annotated[Pagination, Query()]):
        return query

    @app.post("/test/period")
    def period(body: ReportingPeriod):
        return body

    @app.get("/test/conflict")
    def conflict():
        raise AppError("VERSION_CONFLICT", "다시 불러와주세요.")

    @app.get("/test/failure")
    def failure():
        raise RuntimeError("private-secret")

    with TestClient(app, raise_server_exceptions=False) as client:
        for path, status, code in [
            ("/missing", 404, "NOT_FOUND"),
            ("/test/page?page_size=101", 422, "VALIDATION_ERROR"),
            ("/test/conflict", 409, "VERSION_CONFLICT"),
            ("/test/failure", 500, "INTERNAL_ERROR"),
        ]:
            result = client.get(path)
            assert result.status_code == status
            body = result.json()
            assert body["error"]["code"] == code
            assert str(UUID(body["request_id"])) == result.headers["x-request-id"]
            assert "private-secret" not in result.text
        invalid = client.post("/test/period", json={"from": "secret-input", "to": "bad"})
        assert invalid.status_code == 422
        assert "secret-input" not in invalid.text
        assert invalid.json()["error"]["details"][0]["loc"] == ["body", "from"]
        malformed = client.post("/test/period", content="{", headers={"Content-Type": "application/json"})
        assert malformed.status_code == 422
        assert client.post("/api/v1/health").json()["error"]["code"] == "METHOD_NOT_ALLOWED"
        first = client.get("/api/v1/health")
        second = client.get("/api/v1/health")
        assert first.headers["x-request-id"] != second.headers["x-request-id"]
        schema = client.get("/openapi.json").json()
        assert schema["paths"]["/api/v1/health"]["get"]["responses"]["422"]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorResponse")
