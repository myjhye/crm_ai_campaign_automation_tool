from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    application = FastAPI(
        title=settings.app_name,
        description="CRM AI campaign automation backend API",
        version="0.1.0",
    )
    application.state.settings = settings

    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    application.include_router(api_router, prefix="/api/v1")

    @application.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        return {"name": settings.app_name, "docs": "/docs"}

    return application


app = create_app()
