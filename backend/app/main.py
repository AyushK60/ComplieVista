"""CompileVista API application factory. Routes live in app/routes/*; shared error
type and request-size cap in app/core/errors.py."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app import __version__
from app.adapters import evidence
from app.core.errors import AppError  # noqa: F401  (re-exported: tests and routes import it)
from app.routes import analyses, demos, executions, experiments, sources, system
from app.services.analyzer import AnalysisError
from app.services.archive import ArchiveError
from app.services.github_import import ImportError_ as GHImportError
from app.services.ingest import IngestError
from app.store.db import Store, StoreError


def create_app(store: Store | None = None) -> FastAPI:
    app = FastAPI(title="CompileVista API", version=__version__, docs_url="/api/docs")
    store = store or Store()
    app.state.store = store  # exposed for tests/diagnostics; never serialized

    @app.exception_handler(AppError)
    async def app_error(_req, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status,
                            content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(StoreError)
    async def store_error(_req, exc: StoreError) -> JSONResponse:
        status = 404 if exc.code in ("ARTIFACT_MISSING",) else 400
        return JSONResponse(status_code=status,
                            content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(IngestError)
    async def ingest_error(_req, exc: IngestError) -> JSONResponse:
        status = 413 if "TOO_LARGE" in exc.code else 400
        return JSONResponse(status_code=status,
                            content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(ArchiveError)
    async def archive_error(_req, exc: ArchiveError) -> JSONResponse:
        status = 413 if "TOO_LARGE" in exc.code or "CAP" in exc.code else 400
        return JSONResponse(status_code=status,
                            content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(GHImportError)
    async def gh_error(_req, exc: GHImportError) -> JSONResponse:
        return JSONResponse(status_code=exc.status,
                            content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(evidence.EvidenceError)
    async def evidence_error(_req, exc: evidence.EvidenceError) -> JSONResponse:
        status = 404 if exc.code in ("NOT_FOUND", "EVIDENCE_MISSING") else 400
        return JSONResponse(status_code=status,
                            content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(AnalysisError)
    async def analysis_error(_req, exc: AnalysisError) -> JSONResponse:
        return JSONResponse(status_code=exc.status,
                            content={"error": {"code": exc.code, "message": exc.message}})

    for module in (system, analyses, executions, experiments, demos, sources):
        module.register(app, store)

    return app


app = create_app()
