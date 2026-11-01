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
    "pasted_execution": "PARTIAL",   # M4 gate passed (restricted containers, admission
                                     # checked); M4QA audit confirms containment. GitHub-
                                     # imported and public-hosted execution stay BLOCKED.
}


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status



def _capped_receive_call(request: Request, cap: int):
    """F05: returns an async receive() bounded by `cap` total body bytes.
    Handles missing/misleading Content-Length and chunked uploads: the cap is
    enforced on the raw ASGI stream BEFORE any parsing, for every body type."""
    total = {"n": 0}
    original_receive = request._receive  # capture BEFORE any reassignment

    async def receive():
        msg = await original_receive()
        if msg.get("type") == "http.request":
            total["n"] += len(msg.get("body", b""))
            if total["n"] > cap:
                raise AppError("PAYLOAD_TOO_LARGE",
                               f"request exceeds {cap} bytes", 413)
        return msg

    return receive


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
                          "curated_execution=PARTIAL: single-file C/Python in restricted "
                          "containers (M4), audited by M4QA.",
                          "pasted_execution=PARTIAL: same restricted containers, eligible "
                          "paste/upload targets only; GitHub-imported and public-hosted "
                          "execution remain BLOCKED (M9 review)."]}

    @app.get("/api/v1/analyses")
    def analyses() -> list[dict]:
        return evidence.list_analyses()

    @app.post("/api/v1/analyses")
    async def create_job(request: Request) -> dict:
        request._receive = _capped_receive_call(request, 1024 * 1024)  # noqa: SLF001 (M4QA-04)
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
                "provenance": {
                    "source_combined_sha256": job["source_combined_sha256"],
                    "raw_artifact_sha256": rec["raw_artifact"],
                    "stderr_artifact_sha256": rec["stderr_artifact"],
                    "invocation": json.loads(rec["invocation_json"])
                    if rec["invocation_json"] else {},
                },
                "invocation": json.loads(rec["invocation_json"]) if rec["invocation_json"]
                else {"argv_tail": ["<unavailable>"], "note": "legacy stage record"}}

    @app.post("/api/v1/analyses/{analysis_id}/cancel")
    def cancel_analysis(analysis_id: str) -> dict:
        return {"analysis_id": analysis_id, "result": get_runner(store).cancel(analysis_id)}

    @app.post("/api/v1/executions")
    async def create_execution(request: Request) -> dict:
        from app.services.execution import ExecutionError, create_execution, get_execution_runner
        request._receive = _capped_receive_call(request, 1024 * 1024)  # noqa: SLF001 (M4QA-04)
        try:
            body = json.loads((await request.body()).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise AppError("INVALID_BODY", "body must be JSON")
        if not isinstance(body, dict) or not body.get("snapshot_id") or not body.get("target_id"):
            raise AppError("INVALID_BODY", "body requires snapshot_id and target_id")
        try:
            return create_execution(store, body["snapshot_id"], body["target_id"],
                                    body.get("profile", "standard"))
        except ExecutionError as e:
            raise AppError(e.code, e.message, e.status)

    @app.get("/api/v1/executions/{execution_id}/memory")
    def execution_memory(execution_id: str, after: int = 0, limit: int = 200) -> dict:
        """M5 MemoryScope chunk (schema m5.memory.v1): per-record payloads with
        observation classes, checksummed and paginated. Browsing never re-runs."""
        limit = max(1, min(limit, 500))
        job = store.query_one("SELECT status, language, profile, memory_count,"
                              " memory_sha256 FROM executions WHERE id=?", (execution_id,))
        if not job:
            raise AppError("NOT_FOUND", "unknown execution id", 404)
        rows = store.query(
            "SELECT seq, payload_json, sha256 FROM execution_observations"
            " WHERE execution_id=? AND kind='memory' AND seq>? ORDER BY seq LIMIT ?",
            (execution_id, after, limit))
        chunks = [{"seq": r["seq"], "payload": json.loads(r["payload_json"]),
                   "sha256": r["sha256"]} for r in rows]
        kinds = sorted({c["payload"].get("kind", "?") for c in chunks})
        return {"execution_id": execution_id, "status": job["status"],
                "schema": "m5.memory.v1", "language": job["language"],
                "profile": job["profile"] or "standard",
                "total": job["memory_count"] or 0,
                "artifact_sha256": job["memory_sha256"],
                "chunks": chunks, "count": len(chunks), "kinds": kinds,
                "next_after": chunks[-1]["seq"] if chunks else after,
                "limitations": [
                    "Python references are id()-based identities within this run, "
                    "not C pointers.",
                    "C addresses are as observed in this run; ASLR makes them "
                    "unstable across runs.",
                    "Allocator interposition observes allocations that flowed "
                    "through libc malloc; it does not imply exhaustive heap "
                    "coverage."]}

    @app.get("/api/v1/executions/{execution_id}/process")
    def execution_process(execution_id: str, after: int = 0, limit: int = 200) -> dict:
        """M5 ProcessScope chunk (schema m5.process.v1): container-side pid
        namespace, /proc samples, children, exit; checksummed and paginated."""
        limit = max(1, min(limit, 500))
        job = store.query_one("SELECT status, language, profile, process_count,"
                              " process_sha256, host_pid, exit_code, duration_ms"
                              " FROM executions WHERE id=?", (execution_id,))
        if not job:
            raise AppError("NOT_FOUND", "unknown execution id", 404)
        rows = store.query(
            "SELECT seq, payload_json, sha256 FROM execution_observations"
            " WHERE execution_id=? AND kind='process' AND seq>? ORDER BY seq LIMIT ?",
            (execution_id, after, limit))
        chunks = [{"seq": r["seq"], "payload": json.loads(r["payload_json"]),
                   "sha256": r["sha256"]} for r in rows]
        return {"execution_id": execution_id, "status": job["status"],
                "schema": "m5.process.v1", "language": job["language"],
                "profile": job["profile"] or "standard",
                "total": job["process_count"] or 0,
                "artifact_sha256": job["process_sha256"],
                "host_pid": job["host_pid"],
                "exit_code": job["exit_code"], "duration_ms": job["duration_ms"],
                "chunks": chunks, "count": len(chunks),
                "next_after": chunks[-1]["seq"] if chunks else after,
                "limitations": [
                    "PID values are container pid-namespace ids unless a host_pid "
                    "is present; they are not Windows host pids.",
                    "RSS/VM/thread data are periodic /proc samples at the stated "
                    "interval, not continuous measurements.",
                    "Syscall-level tracing (strace/ptrace) is UNSUPPORTED by "
                    "policy in the restricted profile (ADR-0007/0008)."]}

    @app.get("/api/v1/executions/{execution_id}")
    def execution_detail(execution_id: str) -> dict:
        from app.services.execution import ExecutionError, get_execution_runner
        job = store.query_one("SELECT * FROM executions WHERE id=?", (execution_id,))
        if not job:
            raise AppError("NOT_FOUND", "unknown execution id", 404)
        return {k: job[k] for k in job.keys() if k != "fingerprint"} | {
            "ready_for_controlled_execution": False,
            "note": "recorded replay - does not rewind the running process; "
                    "execution ran once in a restricted container"}

    @app.get("/api/v1/executions/{execution_id}/output")
    def execution_output(execution_id: str) -> dict:
        job = store.query_one("SELECT * FROM executions WHERE id=?", (execution_id,))
        if not job:
            raise AppError("NOT_FOUND", "unknown execution id", 404)
        out = {"execution_id": execution_id, "exit_code": job["exit_code"],
               "stdout": None, "stderr": None, "truncated": False}
        for key, col in (("stdout", "stdout_sha256"), ("stderr", "stderr_sha256")):
            sha = job[col]
            if sha:
                data = store.get_artifact(sha)
                out[key] = data[:60_000].decode("utf-8", "replace")
                if len(data) > 60_000:
                    out["truncated"] = True
        return out

    @app.get("/api/v1/executions/{execution_id}/events")
    def execution_events(execution_id: str, after: int = 0, limit: int = 200) -> dict:
        limit = max(1, min(limit, 500))
        job = store.query_one("SELECT status FROM executions WHERE id=?", (execution_id,))
        if not job:
            raise AppError("NOT_FOUND", "unknown execution id", 404)
        rows = store.query(
            "SELECT seq, kind, payload_json, sha256 FROM execution_events"
            " WHERE execution_id=? AND seq>? ORDER BY seq LIMIT ?",
            (execution_id, after, limit))
        events = [{"seq": r["seq"], "kind": r["kind"],
                   "payload": json.loads(r["payload_json"]), "sha256": r["sha256"]}
                  for r in rows]
        return {"execution_id": execution_id, "status": job["status"],
                "events": events, "count": len(events),
                "next_after": events[-1]["seq"] if events else after}

    @app.post("/api/v1/executions/{execution_id}/cancel")
    def cancel_execution(execution_id: str) -> dict:
        from app.services.execution import ExecutionError, get_execution_runner
        try:
            result = get_execution_runner(store).cancel(execution_id)
        except ExecutionError as e:
            raise AppError(e.code, e.message, e.status)
        return {"execution_id": execution_id, "result": result}

    # ---------------- M6: experiments (OptimizationLab / benchmarks / pairs) ----
    @app.get("/api/v1/pairs")
    def list_pairs() -> dict:
        """M6-C pair specs: matched-input C/Python fixtures with independently
        verified expected outputs; sources included so the UI can run a real
        paired comparison end-to-end."""
        from pathlib import Path
        from app.services.curated import _REPO_ROOT  # repo root (verified in M5)
        base = _REPO_ROOT / "sandbox" / "fixtures" / "pairs"
        manifest = json.loads((base / "manifest.json").read_text("utf-8"))
        for pair in manifest.get("pairs", []):
            for key, fname in (("c_source", pair.get("c_file")),
                               ("py_source", pair.get("py_file"))):
                f = base / fname if fname else None
                pair[key] = f.read_text("utf-8") if f and f.is_file() else None
        return manifest

    @app.post("/api/v1/experiments")
    async def create_experiment_endpoint(request: Request) -> dict:
        from app.services.experiments import (ExperimentError, create_experiment,
                                              get_experiment_runner)
        request._receive = _capped_receive_call(request, 1024 * 1024)  # noqa: SLF001
        try:
            body = json.loads((await request.body()).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise AppError("INVALID_BODY", "body must be JSON")
        if not isinstance(body, dict) or not body.get("kind"):
            raise AppError("INVALID_BODY", "body requires kind")
        if body["kind"] not in ("opt", "bench", "compare"):
            raise AppError("INVALID_KIND", f"unknown experiment kind {body['kind']!r}")
        if body["kind"] != "compare" and (
                not body.get("snapshot_id") or not body.get("target_id")):
            raise AppError("INVALID_BODY",
                           "opt/bench experiments require snapshot_id and target_id")
        try:
            return create_experiment(store, body["kind"], body.get("snapshot_id"),
                                     body.get("target_id"),
                                     body.get("config") or {})
        except Exception as e:
            from app.services.experiments import ExperimentError
            if isinstance(e, ExperimentError):
                raise AppError(e.code, e.message, e.status)
            raise

    @app.get("/api/v1/experiments/{experiment_id}")
    def experiment_detail(experiment_id: str) -> dict:
        job = store.query_one("SELECT * FROM experiments WHERE id=?", (experiment_id,))
        if not job:
            raise AppError("NOT_FOUND", "unknown experiment id", 404)
        stages = store.query(
            "SELECT stage, availability, result_json, artifact_sha256, duration_ms"
            " FROM experiment_stages WHERE experiment_id=? ORDER BY stage",
            (experiment_id,))
        return {"id": job["id"], "kind": job["kind"], "status": job["status"],
                "config": json.loads(job["config_json"]),
                "source_combined_sha256": job["source_combined_sha256"],
                "error_code": job["error_code"],
                "result_sha256": job["result_sha256"],
                "created_utc": job["created_utc"], "finished_utc": job["finished_utc"],
                "duration_ms": job["duration_ms"],
                "stages": [{"stage": s["stage"], "availability": s["availability"],
                            "result": json.loads(s["result_json"]),
                            "artifact_sha256": s["artifact_sha256"],
                            "duration_ms": s["duration_ms"]} for s in stages]}

    @app.get("/api/v1/experiments/{experiment_id}/artifacts/{stage}/{kind}")
    def experiment_artifact(experiment_id: str, stage: str, kind: str) -> dict:
        """Bounded text artifact excerpt (ir/asm/symbols) with provenance."""
        rec = store.query_one(
            "SELECT result_json FROM experiment_stages WHERE experiment_id=? AND stage=?",
            (experiment_id, stage))
        if not rec:
            raise AppError("NOT_FOUND", "unknown experiment/stage", 404)
        result = json.loads(rec["result_json"])
        art = result.get(kind)
        if not art or not isinstance(art, dict) or "sha256" not in art:
            raise AppError("NOT_FOUND", f"artifact {kind!r} unavailable for {stage}",
                           404)
        data = store.get_artifact(art["sha256"])
        return {"experiment_id": experiment_id, "stage": stage, "kind": kind,
                "sha256": art["sha256"], "bytes": art["bytes"],
                "truncated": art.get("truncated", False),
                "excerpt": data[:24_000].decode("utf-8", "replace"),
                "excerpt_truncated": len(data) > 24_000}

    @app.post("/api/v1/experiments/{experiment_id}/cancel")
    def cancel_experiment(experiment_id: str) -> dict:
        from app.services.experiments import (ExperimentError,
                                              get_experiment_runner)
        try:
            result = get_experiment_runner(store).cancel(experiment_id)
        except ExperimentError as e:
            raise AppError(e.code, e.message, e.status)
        return {"experiment_id": experiment_id, "result": result}

    # ---------------- M7: demo library + Error Microscope ----------------
    @app.get("/api/v1/demos")
    def list_demos() -> dict:
        from app.services.demos import load_manifest
        return load_manifest()

    @app.post("/api/v1/demos/{demo_id}/run")
    def run_demo_endpoint(demo_id: str) -> dict:
        from app.services.demos import DemoError, run_demo
        try:
            return run_demo(store, demo_id)
        except DemoError as e:
            raise AppError(e.code, e.message, e.status)

    @app.post("/api/v1/demos/{demo_id}/analyze")
    def analyze_demo_endpoint(demo_id: str) -> dict:
        from app.services.demos import DemoError, analyze_demo
        try:
            return analyze_demo(store, demo_id)
        except DemoError as e:
            raise AppError(e.code, e.message, e.status)

    @app.post("/api/v1/demos/{demo_id}/optimize")
    def optimize_demo_endpoint(demo_id: str) -> dict:
        from app.services.demos import DemoError, optimize_demo
        try:
            return optimize_demo(store, demo_id)
        except DemoError as e:
            raise AppError(e.code, e.message, e.status)

    @app.get("/api/v1/demos/{demo_id}/report")
    def demo_report_endpoint(demo_id: str) -> dict:
        from app.services.demos import DemoError, demo_report
        try:
            return demo_report(store, demo_id)
        except DemoError as e:
            raise AppError(e.code, e.message, e.status)

    @app.get("/api/v1/demos/errors")
    def list_error_fixtures() -> dict:
        from app.services.demos import ERROR_MANIFEST
        return {"fixtures": ERROR_MANIFEST}

    @app.post("/api/v1/demos/errors/{fixture_id}/run")
    def run_error_fixture_endpoint(fixture_id: str) -> dict:
        from app.services.demos import DemoError, run_error_fixture
        try:
            return run_error_fixture(store, fixture_id)
        except DemoError as e:
            raise AppError(e.code, e.message, e.status)

    @app.get("/api/v1/analyses/{analysis_id}/stages/{stage}/graph")
    def stage_graph(analysis_id: str, stage: str) -> dict:
        """M3-A typed graph view (schema m3.graph.v1) derived from stored stage items."""
        from app.services.graphs import GraphError, build_graph
        try:
            return build_graph(store, analysis_id, stage)
        except GraphError as e:
            raise AppError(e.code, e.message, e.status)

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

    return app


app = create_app()
