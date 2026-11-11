"""API routes: analyses."""
from __future__ import annotations

import json

from fastapi import FastAPI, Request

from app.core.config import ANALYSIS_POLICY_VERSION
from app.adapters import evidence
from app.core.errors import AppError, _capped_receive_call
from app.services.analyzer import create_analysis, get_runner
from app.store.db import Store


def register(app: FastAPI, store: Store) -> None:
    @app.get("/api/v1/analyses")
    def analyses() -> list[dict]:
        return evidence.list_analyses()

    @app.post("/api/v1/analyses")
    async def create_job(request: Request) -> dict:
        request._receive = _capped_receive_call(request, 1024 * 1024)  # noqa: SLF001
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
                "policy_version": ANALYSIS_POLICY_VERSION,
                "tool_fingerprint": job["tool_fingerprint"],
                "image_id": job["image_id"],
                "error_code": job["error_code"],
                "created_utc": job["created_utc"], "finished_utc": job["finished_utc"],
                "duration_ms": job["duration_ms"],
                "ready_for_controlled_execution": False,
                "note": "static analysis only; no runtime execution occurs (Stage 4 gate)",
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

    @app.get("/api/v1/analyses/{analysis_id}/stages/{stage}/graph")
    def stage_graph(analysis_id: str, stage: str) -> dict:
        """Stage 3-A typed graph view (schema m3.graph.v1) derived from stored stage items."""
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
