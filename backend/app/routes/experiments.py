"""API routes: experiments."""
from __future__ import annotations

import json

from fastapi import FastAPI, Request

from app.core.errors import AppError, _capped_receive_call
from app.store.db import Store


def register(app: FastAPI, store: Store) -> None:
    # ---------------- stage 6: experiments (OptimizationLab / benchmarks / pairs) ----
    @app.get("/api/v1/pairs")
    def list_pairs() -> dict:
        """Stage 6-C pair specs: matched-input C/Python fixtures with independently
        verified expected outputs; sources included so the UI can run a real
        paired comparison end-to-end."""
        from pathlib import Path
        from app.services.curated import _REPO_ROOT  # repo root (verified in stage 5)
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
        # how many experiments are still ahead of this one on the single worker (queued or running,
        # created earlier); lets the UI say "2 ahead of you" instead of a silent wait
        ahead = 0
        if job["status"] == "QUEUED":
            ahead = store.query_one(
                "SELECT COUNT(*) AS n FROM experiments WHERE status IN ('QUEUED','RUNNING')"
                " AND created_utc < ? AND id != ?", (job["created_utc"], experiment_id))["n"]
        return {"id": job["id"], "kind": job["kind"], "status": job["status"],
                "queue_ahead": ahead,
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

    @app.get("/api/v1/experiments/{experiment_id}/linemap")
    def experiment_linemap_route(experiment_id: str) -> dict:
        """Source<->IR<->asm line links per level (+ O0 vs O2), from real -g output."""
        from app.services.linemap import experiment_linemap
        res = experiment_linemap(store, experiment_id)
        if res is None:
            raise AppError("NOT_FOUND", "no optimization experiment with source for this id", 404)
        return res

    @app.post("/api/v1/experiments/{experiment_id}/cancel")
    def cancel_experiment(experiment_id: str) -> dict:
        from app.services.experiments import (ExperimentError,
                                              get_experiment_runner)
        try:
            result = get_experiment_runner(store).cancel(experiment_id)
        except ExperimentError as e:
            raise AppError(e.code, e.message, e.status)
        return {"experiment_id": experiment_id, "result": result}
