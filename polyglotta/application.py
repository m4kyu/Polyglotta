from contextlib import asynccontextmanager
from pathlib import Path
import os
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import database
from .security import current_account
from .routes import auth, activities, cards, languages, statistics, youtube


def create_app(database_path: Path | None = None) -> FastAPI:
    path = Path(database_path) if database_path is not None else database.database_path()

    @asynccontextmanager
    async def lifespan(app):
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = database.make_engine(path)
        try:
            database.migrate(engine)
            app.state.engine = engine
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="Polyglotta", lifespan=lifespan)
    origin = os.environ.get("POLYGLOTTA_ORIGIN", "http://127.0.0.1:8000")
    parts = urlsplit(origin)
    if (parts.scheme != "https" and origin != "http://127.0.0.1:8000") or (
            not parts.hostname or parts.username or parts.password or parts.path or parts.query or parts.fragment):
        raise ValueError("Configure POLYGLOTTA_ORIGIN as the public HTTPS origin without a trailing slash.")

    @app.middleware("http")
    async def private_api(request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("origin") != origin:
            response = JSONResponse({"detail": "Invalid request origin."}, status_code=403)
        else:
            response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        # Authentication validation must never echo the submitted body or password.
        if request.url.path.startswith("/api/auth/") or request.url.path == "/api/account":
            return JSONResponse({"detail": "Invalid account details."}, status_code=422)
        from fastapi.exception_handlers import request_validation_exception_handler
        return await request_validation_exception_handler(request, error)

    app.include_router(auth.router)
    for router in (languages.router, activities.router, cards.router, statistics.router):
        app.include_router(router, prefix="/api/languages")

    app.include_router(youtube.router, dependencies=[Depends(current_account)])

    static = database.ROOT / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/")
    def index():
        return FileResponse(static / "index.html")

    return app
