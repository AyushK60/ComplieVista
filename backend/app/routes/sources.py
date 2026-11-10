"""API routes: sources."""
from __future__ import annotations

import json

from fastapi import FastAPI, Request
from starlette.datastructures import UploadFile

from app.core.config import LIMITS, SCHEMA_VERSION
from app.core.errors import AppError, _capped_receive_call
from app.services.github_import import import_github
from app.services.ingest import ingest_files, ingest_paste
from app.store.db import Store


def register(app: FastAPI, store: Store) -> None:
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
            request._receive = _capped_receive_call(  # noqa: SLF001
                request, LIMITS["request_max_bytes"])
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
        # F05: streaming cap on the raw ASGI stream (chunked/missing
        # Content-Length cannot bypass it).
        request._receive = _capped_receive_call(  # noqa: SLF001
            request, LIMITS["paste_max_bytes"] + 4096)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
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
        # F05: the GitHub body is tiny JSON — bound it explicitly (chunked safe).
        request._receive = _capped_receive_call(  # noqa: SLF001
            request, 1024 * 1024)
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
            "SELECT t.*, s.origin AS snap_origin FROM compilation_targets t"
            " JOIN source_snapshots s ON t.snapshot_id = s.id WHERE s.project_id=?"
            " ORDER BY t.primary_file LIMIT ?", (project_id, LIMITS["api_max_response_items"]))
        out = []
        for r in rows:
            reasons = json.loads(r["reasons_json"])
            # M4QA-08: report admission honestly — a target is execution-ready exactly
            # when the M4 admission path would accept it (eligible class, non-GitHub
            # origin). Docker availability is checked again at submission time.
            ready = (r["status"] in ("EXECUTABLE_CANDIDATE", "COMPILATION_CANDIDATE")
                     and r["snap_origin"] != "github")
            out.append({"target_id": r["id"], "snapshot_id": r["snapshot_id"],
                        "kind": r["kind"], "primary_file": r["primary_file"],
                        "status": r["status"],
                        "ready_for_controlled_execution": ready,
                        "reasons": reasons,
                        "note": "statuses are detected candidates; verification requires "
                                "real toolchain checks (M2+); execution runs once in a "
                                "restricted container (M4) and is refused for "
                                "GitHub-imported origins"})
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
