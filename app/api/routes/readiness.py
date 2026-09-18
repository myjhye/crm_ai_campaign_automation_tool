from fastapi import APIRouter, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import AppError

router = APIRouter(tags=["health"])


@router.get("/ready")
def readiness(request: Request) -> dict[str, str]:
    database = request.app.state.database
    if database is None:
        raise AppError("DATABASE_UNAVAILABLE", "DB 연결 설정이 필요합니다.", 503)
    try:
        with database.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise AppError("DATABASE_UNAVAILABLE", "DB에 연결할 수 없습니다.", 503) from None
    return {"status": "ok", "database": "ok"}
