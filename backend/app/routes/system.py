"""API routes: system."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI

from app import __version__
from app.core.config import SCHEMA_VERSION
from app.core.errors import AppError
from app.services.toolprobe import probe_tools
from app.store.db import Store

MODES = {
    "read_only_analysis": "AVAILABLE",
    "curated_execution": "PARTIAL",
    "pasted_execution": "PARTIAL",   # Stage 4 gate passed (restricted containers, admission
                                     # checked); stage 4 review audit confirms containment. GitHub-
                                     # imported and public-hosted execution stay BLOCKED.
}


def register(app: FastAPI, store: Store) -> None:
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
                          "containers (Stage 4), audited by stage 4 review.",
                          "pasted_execution=PARTIAL: same restricted containers, eligible "
                          "paste/upload targets only; GitHub-imported and public-hosted "
                          "execution remain BLOCKED (Stage 9 review)."]}
