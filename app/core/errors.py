"""Common HTTP errors without reflecting request bodies or internal exceptions."""

import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    loc: list[str | int]
    type: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorBody
    request_id: str


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        self.code = code
        self.message = message
        self.status_code = status_code


def install_error_handlers(app: FastAPI) -> None:
    def response(request: Request, status: int, code: str, message: str,
                 details: list[ErrorDetail] | None = None, headers=None):
        request_id = getattr(request.state, "request_id", str(uuid4()))
        body = ErrorResponse(
            error=ErrorBody(code=code, message=message, details=details or []),
            request_id=request_id,
        )
        return JSONResponse(status_code=status, content=body.model_dump(),
                            headers={**(headers or {}), "X-Request-ID": request_id})

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = str(uuid4())
        result = await call_next(request)
        result.headers["X-Request-ID"] = request.state.request_id
        return result

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        details = [ErrorDetail(loc=list(item["loc"]), type=item["type"])
                   for item in exc.errors()]
        return response(request, 422, "VALIDATION_ERROR", "입력값을 확인해주세요.", details)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        codes = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 409: "CONFLICT",
                 422: "VALIDATION_ERROR"}
        return response(request, exc.status_code, codes.get(exc.status_code, "HTTP_ERROR"),
                        "요청을 처리할 수 없습니다.", headers=exc.headers)

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return response(request, exc.status_code, exc.code, exc.message)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logger.error("Unhandled error request_id=%s type=%s",
                     getattr(request.state, "request_id", "unknown"), type(exc).__name__)
        return response(request, 500, "INTERNAL_ERROR", "서버 오류가 발생했습니다.")
