"""API routes: executions."""
from __future__ import annotations

import json

from fastapi import FastAPI, Request

from app.core.errors import AppError, _capped_receive_call
from app.store.db import Store


def register(app: FastAPI, store: Store) -> None:
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

    @app.get("/api/v1/executions/{execution_id}/replay.html")
    def execution_replay_export(execution_id: str):
        """Self-contained one-file replay of a recorded run (no backend needed to view)."""
        from fastapi.responses import Response
        from app.services.replay_export import build_replay_html
        page = build_replay_html(store, execution_id)
        if page is None:
            raise AppError("NOT_FOUND", "unknown execution id", 404)
        return Response(page, media_type="text/html; charset=utf-8", headers={
            "Content-Disposition": f'attachment; filename="compilevista-replay-{execution_id[:12]}.html"',
            "X-Content-Type-Options": "nosniff"})

    @app.post("/api/v1/executions/{execution_id}/cancel")
    def cancel_execution(execution_id: str) -> dict:
        from app.services.execution import ExecutionError, get_execution_runner
        try:
            result = get_execution_runner(store).cancel(execution_id)
        except ExecutionError as e:
            raise AppError(e.code, e.message, e.status)
        return {"execution_id": execution_id, "result": result}
