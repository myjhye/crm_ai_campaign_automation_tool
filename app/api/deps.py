"""API 공통 의존성 위치.

요청별 DB 세션과 Clock을 제공한다.
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
