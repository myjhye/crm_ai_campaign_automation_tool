from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import Settings
from app.core.errors import ErrorResponse, install_error_handlers
from app.core.time import SystemClock
from app.db.session import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    database = Database(settings.database_url.get_secret_value()) if settings.database_url else None

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            yield
        finally:
            if database is not None:
                database.dispose()

    application = FastAPI(
        title=settings.app_name,
        description="CRM AI campaign automation backend API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.database = database
    application.state.clock = SystemClock()
    install_error_handlers(application)

    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )

    application.include_router(api_router, prefix="/api/v1", responses={
        status: {"model": ErrorResponse} for status in (404, 409, 422, 500, 503)
    })

    frontend = Path(__file__).resolve().parent.parent / "frontend"
    for folder in ("styles", "src"):
        application.mount(f"/static/{folder}", StaticFiles(directory=frontend / folder),
                          name=f"static_{folder}")

    @application.get("/", include_in_schema=False)
    def root():
        return FileResponse(frontend / "index.html", headers={"Cache-Control": "no-cache"})

    @application.get("/api/v1/info", tags=["info"])
    async def info() -> dict[str, str]:
        return {"name": settings.app_name, "docs": "/docs"}

    return application


app = create_app()
