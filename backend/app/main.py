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
from app.core.config import ANALYZER_IMAGE, LIMITS, SCHEMA_VERSION
from app.services.analyzer import AnalysisError, create_analysis, get_runner
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

    @app.post("/api/v1/analyses")
    async def create_job(request: Request) -> dict:
        try:
            body = json.loads((await request.body()).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise AppError("INVALID_BODY", "body must be JSON")
        if not isinstance(body, dict) or not body.get("snapshot_id") or not body.get("target_id"):
            raise AppError("INVALID_BODY", "body requires snapshot_id and target_id")
        return create_analysis(store, body["snapshot_id"], body["target_id"])

    @app.get("/api/v1/analyses/{analysis_id}")
    def analysis(analysis_id: str) -> dict:
        if analysis_id in ("m0-c", "m0-python"):
            m = evidence.get_manifest(analysis_id)
            return {"id": m.analysis_id, "language": m.language.value,
                    "schema_version": m.schema_version,
                    "source_snapshot": m.source_snapshot.model_dump(),
                    "tools": m.tools,
                    "stages": [{"stage": s.stage, "availability": s.availability.value,
                                "observation_class": s.observation_class.value,
                                "counts": s.counts, "limitations": s.limitations}
                               for s in m.stages]}
        job = store.query_one("SELECT * FROM analyses WHERE id=?", (analysis_id,))
        if not job:
            raise AppError("NOT_FOUND", "unknown analysis id", 404)
        stages = store.query(
            "SELECT stage, availability, observation_class, exit_code, counts_json,"
            " duration_ms, truncated FROM analysis_stages WHERE analysis_id=?"
            " ORDER BY rowid", (analysis_id,))
        return {"id": job["id"], "status": job["status"], "language": job["language"],
                "primary_file": job["primary_file"],
                "source_combined_sha256": job["source_combined_sha256"],
                "policy_version": "m2.analyzer.v1",
                "tool_fingerprint": job["tool_fingerprint"],
                "image_id": job["image_id"],
                "error_code": job["error_code"],
                "created_utc": job["created_utc"], "finished_utc": job["finished_utc"],
                "duration_ms": job["duration_ms"],
                "ready_for_controlled_execution": False,
                "note": "static analysis only; no runtime execution occurs (M4 gate)",
                "stages": [{"stage": s["stage"], "availability": s["availability"],
                            "observation_class": s["observation_class"],
                            "exit_code": s["exit_code"],
                            "counts": json.loads(s["counts_json"] or "{}"),
                            "truncated": bool(s["truncated"]),
                            "duration_ms": s["duration_ms"]} for s in stages]}

    @app.get("/api/v1/analyses/{analysis_id}/stages/{stage}")
    def stage(analysis_id: str, stage: str) -> dict:
        if analysis_id in ("m0-c", "m0-python"):
            return evidence.get_stage_view(analysis_id, stage)
        job = store.query_one("SELECT * FROM analyses WHERE id=?", (analysis_id,))
        if not job:
            raise AppError("NOT_FOUND", "unknown analysis id", 404)
        rec = store.query_one("SELECT * FROM analysis_stages WHERE analysis_id=? AND stage=?",
                              (analysis_id, stage))
        if not rec:
            raise AppError("NOT_FOUND",
                           f"stage {stage!r} not present for this analysis "
                           f"(status={job['status']})", 404)
        return {"analysis_id": analysis_id, "stage": rec["stage"],
                "status": job["status"], "language": job["language"],
                "availability": rec["availability"],
                "observation_class": rec["observation_class"],
                "exit_code": rec["exit_code"],
                "counts": json.loads(rec["counts_json"] or "{}"),
                "items": json.loads(rec["items_json"] or "[]"),
                "limitations": json.loads(rec["limitations_json"] or "[]"),
                "raw_artifact_sha256": rec["raw_artifact"],
                "stderr_artifact_sha256": rec["stderr_artifact"],
                "truncated": bool(rec["truncated"]),
                "duration_ms": rec["duration_ms"],
                "invocation": json.loads(rec["invocation_json"]) if rec["invocation_json"]
                else {"argv_tail": ["<unavailable>"], "note": "legacy stage record"}}

    @app.post("/api/v1/analyses/{analysis_id}/cancel")
    def cancel_analysis(analysis_id: str) -> dict:
        return {"analysis_id": analysis_id, "result": get_runner(store).cancel(analysis_id)}

    @app.get("/api/v1/analyses/{analysis_id}/stages/{stage}/raw")
    def stage_raw(analysis_id: str, stage: str) -> dict:
        """Bounded raw tool output for the raw/normalized toggle (≤ 24 KB excerpt)."""
        rec = store.query_one("SELECT * FROM analysis_stages WHERE analysis_id=? AND stage=?",
                              (analysis_id, stage))
        if not rec:
            raise AppError("NOT_FOUND", "unknown analysis/stage", 404)
        out: dict = {"analysis_id": analysis_id, "stage": stage, "excerpt": None,
                     "truncated": False}
        for key in ("raw_artifact", "stderr_artifact"):
            sha = rec[key]
            if sha and out["excerpt"] is None:
                data = store.get_artifact(sha)
                out["artifact_sha256"] = sha
                out["excerpt"] = data[:24_000].decode("utf-8", "replace")
                out["truncated"] = len(data) > 24_000
                out["bytes"] = len(data)
        return out

    # ---------------- M1: limits ----------------
    @app.get("/api/v1/limits")
    def limits() -> dict:
        return {"limits": LIMITS, "schema_version": SCHEMA_VERSION}

    # ---------------- M1: ingestion ----------------
    @app.post("/api/v1/sources")
    async def post_sources(request: Request) -> dict:
        # CV-10: reject oversized requests BEFORE reading the body into memory.
        try:
            content_length = int(request.headers.get("content-length", "0") or "0")
        except ValueError:
            content_length = 0
        if content_length > LIMITS["request_max_bytes"]:
            raise AppError("PAYLOAD_TOO_LARGE",
                           f"request exceeds {LIMITS['request_max_bytes']} bytes", 413)
        ctype = request.headers.get("content-type", "")
        if "multipart/form-data" in ctype:
            form = await request.form()
            uploads: list[tuple[str, bytes]] = []
            for key, value in form.items():
                if isinstance(value, UploadFile):
                    name = value.filename or "unnamed"
                    # Stream-bounded read: never read more than the per-part cap + 1.
                    is_zip = name.lower().endswith(".zip")
                    part_cap = (LIMITS["zip_max_compressed_bytes"] if is_zip
                                else LIMITS["file_max_bytes"])
                    data = await value.read(part_cap + 1)
                    if len(data) > part_cap:
                        raise AppError("PAYLOAD_TOO_LARGE",
                                       f"{name} exceeds {part_cap} bytes", 413)
                    uploads.append((name, data))
            if not uploads:
                raise AppError("EMPTY_UPLOAD", "multipart request contained no files")
            return ingest_files(store, uploads)
        if content_length > LIMITS["paste_max_bytes"] + 4096:
            raise AppError("PAYLOAD_TOO_LARGE",
                           f"paste exceeds {LIMITS['paste_max_bytes']} bytes", 413)
        # Streaming cap: chunked/missing Content-Length must not bypass the limit.
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > LIMITS["paste_max_bytes"] + 4096:
                raise AppError("PAYLOAD_TOO_LARGE",
                               f"paste exceeds {LIMITS['paste_max_bytes']} bytes", 413)
        try:
            body_json = json.loads(bytes(body).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise AppError("INVALID_BODY", "body must be JSON or multipart")
        if not isinstance(body_json, dict):
            raise AppError("INVALID_BODY", "JSON body must be an object")
        if body_json.get("kind") != "paste":
            raise AppError("INVALID_BODY", "JSON body requires kind='paste' (use multipart for files/zip)")
        content = body_json.get("content", "")
        if isinstance(content, str):
            content = content.encode("utf-8")
        return ingest_paste(store, body_json.get("language", ""), body_json.get("filename", "source"),
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
