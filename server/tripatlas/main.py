"""Application factory. Run with:  uvicorn tripatlas.main:app --host 0.0.0.0 --port 8097"""

from __future__ import annotations

import logging
import mimetypes
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import auth, avatars, imports, photos, setup, trackers, trips, users
from .config import get_config
from .db.session import migrate
from .integrations.immich import ImmichError
from .integrations.traccar import TraccarError
from .services.jobs import jobs

# Not in every system's MIME table; browsers only accept the manifest with the right type.
mimetypes.add_type("application/manifest+json", ".webmanifest")


@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate()
    jobs.start()
    yield
    jobs.stop()


def create_app(start_jobs: bool = True) -> FastAPI:
    cfg = get_config()
    logging.basicConfig(level=cfg.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # httpx logs every request at INFO — one line per thumbnail drowns everything else
    logging.getLogger("httpx").setLevel(logging.WARNING)
    app = FastAPI(
        title="TripAtlas",
        version=__version__,
        lifespan=lifespan if start_jobs else None,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )

    # The photo layer sends tens of thousands of markers; gzip halves that JSON (2.4 MB → 1.1 MB for 42,000 photos).
    app.add_middleware(GZipMiddleware, minimum_size=2048)

    for r in (setup.router, auth.router, users.router, trackers.router, trips.router, photos.router, imports.router,
              avatars.router):
        app.include_router(r)

    @app.get("/api/health", tags=["meta"])
    def health():
        return {"ok": True, "version": __version__}

    @app.exception_handler(ImmichError)
    async def immich_error(_: Request, e: ImmichError):
        return JSONResponse({"detail": str(e)}, status_code=502)

    @app.exception_handler(TraccarError)
    async def traccar_error(_: Request, e: TraccarError):
        return JSONResponse({"detail": str(e)}, status_code=502)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    web = cfg.web_dir
    if web and (web / "index.html").exists():
        app.mount("/_app", StaticFiles(directory=web / "_app"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            # Static files of the build, otherwise the single-page app (client-side routing).
            if path.startswith("api/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            f = (web / path).resolve()
            if path and f.is_file() and web.resolve() in f.parents:
                return FileResponse(f)
            return FileResponse(web / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
