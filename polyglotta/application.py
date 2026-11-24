from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import database
from .routes import activities, cards, languages, statistics, youtube


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
    for router in (languages.router, activities.router, cards.router, statistics.router):
        app.include_router(router, prefix="/api/languages")

    app.include_router(youtube.router)

    static = database.ROOT / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/")
    def index():
        return FileResponse(static / "index.html")

    return app
