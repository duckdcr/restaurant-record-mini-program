from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .auth import ApiError
from .config import Settings, get_settings
from .database import Base, make_engine, make_session_factory
from .routes.auth import router as auth_router
from .routes.dashboard import router as dashboard_router
from .routes.menus import router as menus_router
from .routes.recognitions import router as recognitions_router
from .routes.uploads import router as uploads_router
from .routes.samples import router as samples_router
from .routes.reports import router as reports_router


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    active_settings.ensure_directories()
    engine = make_engine(active_settings.database_url)
    SessionLocal = make_session_factory(engine)
    Base.metadata.create_all(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        engine.dispose()

    app = FastAPI(title="A2 安心留样 API", version="1.0.0", lifespan=lifespan)
    app.state.settings = active_settings
    app.state.engine = engine
    app.state.SessionLocal = SessionLocal
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )

    @app.exception_handler(ApiError)
    async def api_error_handler(_, exc: ApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
                "details": exc.details,
            },
        )

    @app.get("/health")
    def health():
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": "ready",
            "database_engine": engine.dialect.name,
        }

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(menus_router, prefix="/api/v1")
    app.include_router(uploads_router, prefix="/api/v1")
    app.include_router(recognitions_router, prefix="/api/v1")
    app.include_router(samples_router, prefix="/api/v1")
    app.include_router(reports_router, prefix="/api/v1")
    return app


app = create_app()
