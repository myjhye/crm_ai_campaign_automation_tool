from fastapi import APIRouter

from app.api.routes import health
from app.api.routes import jobs, readiness
from app.api.routes import audit, datasets, imports

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(readiness.router)
api_router.include_router(jobs.router)
api_router.include_router(datasets.router)
api_router.include_router(audit.router)

api_router.include_router(imports.router)

from app.api.routes import analytics
api_router.include_router(analytics.router)
from app.api.routes import segments
api_router.include_router(segments.router)
from app.api.routes import ai
api_router.include_router(ai.router)
from app.api.routes import campaigns
api_router.include_router(campaigns.router)
