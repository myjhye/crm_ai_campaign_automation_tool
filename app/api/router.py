from fastapi import APIRouter

from app.api.routes import health
from app.api.routes import jobs, readiness

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(readiness.router)
api_router.include_router(jobs.router)
