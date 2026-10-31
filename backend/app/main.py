"""M1 source-workspace API, layered on the M0 control plane.

M0 endpoints (/health, /capabilities, /analyses…) are unchanged. M1 adds bounded
source ingestion (paste/upload/zip), public GitHub import, project/snapshot/target
surfacing and limits disclosure. Every endpoint fails with typed structured errors
and never leaks absolute host paths. No endpoint executes user source.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile

from app import __version__
from app.adapters import evidence
from app.core.config import LIMITS, SCHEMA_VERSION
from app.services.archive import ArchiveError
from app.services.github_import import ImportError_ as GHImportError
from app.services.github_import import import_github
from app.services.ingest import IngestError, ingest_files, ingest_paste
from app.services.toolprobe import probe_tools
from app.store.db import Store, StoreError

MODES = {
    "read_only_analysis": "AVAILABLE",
    "curated_execution": "PARTIAL",
    "pasted_execution": "BLOCKED",   # M4 security gate governs; M1 adds NO execution
}


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def create_app(store: Store | None = None) -> FastAPI:
    app = FastAPI(title="CompileVista API", version=__version__, docs_url="/api/docs")
    store = store or Store()

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

    # ---------------- M0 endpoints (unchanged behavior) ----------------
    @app.get("/api/v1/health")
    def health() -> dict:
        return {"status": "ok",
                "time_utc": datetime.now(timezone.utc).isoformat(),
                "python_version": probe_tools()["python"]["version"],
                "schema_version": SCHEMA_VERSION,
                "api_version": __version__}

    @app.get("/api/v1/capabilities")
    def capabilities() -> dict:
        return {"tools": probe_tools(), "modes": MODES,
                "notes": ["Observed inside WSL Ubuntu 24.04 via direct tool probes at startup.",
                          "curated_execution=PARTIAL: restrictive Docker baseline proven in M0, "
                          "adversarial validation deferred to M4.",
                          "pasted_execution=BLOCKED until the M4 security gate passes."]}

    @app.get("/api/v1/analyses")
    def analyses() -> list[dict]:
        return evidence.list_analyses()

    @app.get("/api/v1/analyses/{analysis_id}")
    def analysis(analysis_id: str) -> dict:
        m = evidence.get_manifest(analysis_id)
        return {"id": m.analysis_id, "language": m.language.value,
                "schema_version": m.schema_version,
                "source_snapshot": m.source_snapshot.model_dump(),
                "tools": m.tools,
                "stages": [{"stage": s.stage, "availability": s.availability.value,
                            "observation_class": s.observation_class.value,
                            "counts": s.counts, "limitations": s.limitations}
                           for s in m.stages]}

    @app.get("/api/v1/analyses/{analysis_id}/stages/{stage}")
    def stage(analysis_id: str, stage: str) -> dict:
        return evidence.get_stage_view(analysis_id, stage)

    # ---------------- M1: limits ----------------
    @app.get("/api/v1/limits")
    def limits() -> dict:
        return {"limits": LIMITS, "schema_version": SCHEMA_VERSION}

    # ---------------- M1: ingestion ----------------
    @app.post("/api/v1/sources")
    async def post_sources(request: Request) -> dict:
        ctype = request.headers.get("content-type", "")
        if "multipart/form-data" in ctype:
            form = await request.form()
            uploads: list[tuple[str, bytes]] = []
            for key, value in form.items():
                if isinstance(value, UploadFile):
                    data = await value.read()
                    uploads.append((value.filename or "unnamed", data))
            if not uploads:
                raise AppError("EMPTY_UPLOAD", "multipart request contained no files")
            return ingest_files(store, uploads)
        try:
            body = json.loads((await request.body()).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise AppError("INVALID_BODY", "body must be JSON or multipart")
        if not isinstance(body, dict):
            raise AppError("INVALID_BODY", "JSON body must be an object")
        if body.get("kind") != "paste":
            raise AppError("INVALID_BODY", "JSON body requires kind='paste' (use multipart for files/zip)")
        content = body.get("content", "")
        if isinstance(content, str):
            content = content.encode("utf-8")
        return ingest_paste(store, body.get("language", ""), body.get("filename", "source"),
                            content)

    @app.post("/api/v1/imports/github")
    async def post_import_github(request: Request) -> dict:
        try:
            body = json.loads((await request.body()).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise AppError("INVALID_BODY", "body must be JSON")
        if not isinstance(body, dict) or not isinstance(body.get("url"), str):
            raise AppError("INVALID_BODY", "body must be {'url': ..., 'ref'?: ...}")
        return import_github(store, body["url"], body.get("ref"))

    # ---------------- M1: projects / snapshots / targets ----------------
    @app.get("/api/v1/projects")
    def list_projects() -> list[dict]:
        rows = store.query(
            "SELECT p.id, p.name, p.created_utc, s.id AS snapshot_id, s.origin,"
            " s.combined_sha256 FROM projects p JOIN source_snapshots s ON s.project_id=p.id"
            " ORDER BY p.created_utc DESC LIMIT ?", (LIMITS["api_max_response_items"],))
        return [{"id": r["id"], "name": r["name"], "created_utc": r["created_utc"],
                 "snapshot_id": r["snapshot_id"], "origin": r["origin"],
                 "combined_sha256": r["combined_sha256"]} for r in rows]

    def _project_snapshot(project_id: str, snapshot_id: str) -> None:
        row = store.query_one(
            "SELECT 1 FROM source_snapshots WHERE id=? AND project_id=?",
            (snapshot_id, project_id))
        if not row:
            raise AppError("NOT_FOUND", "unknown project/snapshot pair", 404)

    @app.get("/api/v1/projects/{project_id}")
    def get_project(project_id: str) -> dict:
        p = store.query_one("SELECT * FROM projects WHERE id=?", (project_id,))
        if not p:
            raise AppError("NOT_FOUND", f"unknown project {project_id!r}", 404)
        snaps = store.query("SELECT * FROM source_snapshots WHERE project_id=?", (project_id,))
        return {"id": p["id"], "name": p["name"], "created_utc": p["created_utc"],
                "snapshots": [{"id": s["id"], "origin": s["origin"],
                               "combined_sha256": s["combined_sha256"],
                               "created_utc": s["created_utc"]} for s in snaps]}

    @app.get("/api/v1/projects/{project_id}/targets")
    def list_targets(project_id: str) -> list[dict]:
        rows = store.query(
            "SELECT t.* FROM compilation_targets t JOIN source_snapshots s"
            " ON t.snapshot_id = s.id WHERE s.project_id=?"
            " ORDER BY t.primary_file LIMIT ?", (project_id, LIMITS["api_max_response_items"]))
        out = []
        for r in rows:
            reasons = json.loads(r["reasons_json"])
            out.append({"target_id": r["id"], "snapshot_id": r["snapshot_id"],
                        "kind": r["kind"], "primary_file": r["primary_file"],
                        "status": r["status"],
                        "ready_for_controlled_execution": False,
                        "reasons": reasons,
                        "note": "statuses are detected candidates; verification requires "
                                "real toolchain checks (M2+) and execution requires the "
                                "M4 security gate"})
        return out

    @app.get("/api/v1/projects/{project_id}/snapshots/{snapshot_id}")
    def get_snapshot(project_id: str, snapshot_id: str) -> dict:
        _project_snapshot(project_id, snapshot_id)
        s = store.query_one("SELECT * FROM source_snapshots WHERE id=?", (snapshot_id,))
        files = store.query(
            "SELECT * FROM source_files WHERE snapshot_id=? ORDER BY rel_path", (snapshot_id,))
        diags = store.query(
            "SELECT file_path, severity, code, detail FROM snapshot_diagnostics"
            " WHERE snapshot_id=? LIMIT ?", (snapshot_id, LIMITS["api_max_response_items"]))
        return {"id": s["id"], "origin": s["origin"], "combined_sha256": s["combined_sha256"],
                "created_utc": s["created_utc"],
                "files": [{"id": f["id"], "rel_path": f["rel_path"], "size": f["size"],
                           "encoding": f["encoding"], "language": f["language"],
                           "content_sha256": f["content_sha256"]} for f in files],
                "diagnostics": [dict(d) for d in diags]}

    @app.get("/api/v1/projects/{project_id}/snapshots/{snapshot_id}/files/{file_id}")
    def get_file(project_id: str, snapshot_id: str, file_id: str) -> dict:
        _project_snapshot(project_id, snapshot_id)
        f = store.query_one("SELECT * FROM source_files WHERE id=? AND snapshot_id=?",
                            (file_id, snapshot_id))
        if not f:
            raise AppError("NOT_FOUND", "unknown file in snapshot", 404)
        data = store.get_artifact(f["content_sha256"])
        text = data.decode("utf-8", "replace") if f["encoding"] != "binary" else None
        return {"id": f["id"], "rel_path": f["rel_path"], "size": f["size"],
                "encoding": f["encoding"], "language": f["language"],
                "content_sha256": f["content_sha256"],
                "text": text[:200_000] if text is not None else None,
                "text_truncated": text is not None and len(text) > 200_000}

    @app.get("/api/v1/imports/{import_id}")
    def get_import(import_id: str) -> dict:
        r = store.query_one("SELECT * FROM imports WHERE id=?", (import_id,))
        if not r:
            raise AppError("NOT_FOUND", "unknown import id", 404)
        return {k: r[k] for k in r.keys()}

    return app


app = create_app()
