"""API 공통 의존성 위치.

DB 세션은 단계 1에서 추가한다.
"""

from fastapi import Request

from app.core.time import Clock


def get_clock(request: Request) -> Clock:
    return request.app.state.clock
