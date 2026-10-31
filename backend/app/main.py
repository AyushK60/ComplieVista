"""M0 FastAPI control plane — health, capabilities, and the two genuine proof analyses.

Binds to loopback only (README §10). No execution endpoints exist yet; pasted-code
execution stays BLOCKED until the M4 security gate (ADR-0003).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app import __version__
from app.adapters import evidence
from app.services.toolprobe import probe_tools

MODES = {
    "read_only_analysis": "AVAILABLE",
    "curated_execution": "PARTIAL",   # Docker baseline proven feasible; no user-facing mode yet
    "pasted_execution": "BLOCKED",    # M4 security gate required (README §10)
}


def create_app() -> FastAPI:
    app = FastAPI(title="CompileVista API", version=__version__, docs_url="/api/docs")

    @app.exception_handler(evidence.EvidenceError)
    async def evidence_error(_req, exc: evidence.EvidenceError) -> JSONResponse:
        status = 404 if exc.code in ("NOT_FOUND", "EVIDENCE_MISSING") else 400
        return JSONResponse(status_code=status,
                            content={"error": {"code": exc.code, "message": exc.message}})

    @app.get("/api/v1/health")
    def health() -> dict:
        return {"status": "ok",
                "time_utc": datetime.now(timezone.utc).isoformat(),
                "python_version": probe_tools()["python"]["version"],
                "schema_version": "m0.v1",
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
    def stage(analysis_id: str, stage: str) -> dict[str, Any]:
        return evidence.get_stage_view(analysis_id, stage)

    return app


app = create_app()
