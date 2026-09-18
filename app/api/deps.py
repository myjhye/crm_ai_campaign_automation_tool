"""API 공통 의존성 위치.

DB 세션은 단계 1에서 추가한다.
"""

from fastapi import Request

from app.core.time import Clock
from app.core.errors import AppError


def get_clock(request: Request) -> Clock:
    return request.app.state.clock


def get_session(request: Request):
    database = request.app.state.database
    if database is None:
        raise AppError("DATABASE_UNAVAILABLE", "DB 연결 설정이 필요합니다.", 503)
    with database.sessions() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
