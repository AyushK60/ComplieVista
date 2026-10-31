"""Loads M0 evidence manifests and serves bounded typed views (ADR-0002)."""
from __future__ import annotations

import json
from pathlib import Path

from app.contracts.models import AnalysisManifest

REPO = Path(__file__).resolve().parents[3]
EVIDENCE = REPO / "evidence" / "m0"

MAX_ITEMS = 500          # per-stage item cap in API responses
MAX_TEXT_EXCERPT = 6000  # raw text excerpt cap (bytes)


class EvidenceError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def list_analyses() -> list[dict]:
    out = []
    for mpath in sorted(EVIDENCE.glob("*/manifest.json")):
        data = json.loads(mpath.read_text())
        # Only analysis manifests (with a language pipeline) are exposed here;
        # other evidence records (e.g. the Docker feasibility report) are skipped.
        if "language" not in data or "stages" not in data:
            continue
        m = AnalysisManifest.model_validate(data)
        out.append({
            "id": m.analysis_id,
            "language": m.language.value,
            "schema_version": m.schema_version,
            "source_combined_sha256": m.source_snapshot.combined_sha256,
            "stage_count": len(m.stages),
            "stages": [s.stage for s in m.stages],
        })
    if not out:
        raise EvidenceError("EVIDENCE_MISSING", "no M0 manifests found; run toolchain proofs")
    return out


def get_manifest(analysis_id: str) -> AnalysisManifest:
    if analysis_id not in ("m0-c", "m0-python"):
        raise EvidenceError("NOT_FOUND", f"unknown analysis id: {analysis_id!r}")
    sub = "c" if analysis_id == "m0-c" else "python"
    mpath = EVIDENCE / sub / "manifest.json"
    if not mpath.is_file():
        raise EvidenceError("EVIDENCE_MISSING", f"manifest missing for {analysis_id}")
    return AnalysisManifest.model_validate_json(mpath.read_text())


def _load_json_artifact(repo_rel_path: str) -> list | dict | None:
    p = REPO / repo_rel_path
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def _text_excerpt(rel_path: str) -> dict:
    p = REPO / rel_path
    if not p.is_file():
        return {"excerpt": None, "truncated": False}
    data = p.read_bytes()
    return {"excerpt": data[:MAX_TEXT_EXCERPT].decode("utf-8", "replace"),
            "truncated": len(data) > MAX_TEXT_EXCERPT}


def get_stage_view(analysis_id: str, stage: str) -> dict:
    m = get_manifest(analysis_id)
    rec = m.stage(stage)
    if rec is None:
        raise EvidenceError("NOT_FOUND", f"unknown stage {stage!r} for {analysis_id}")
    sub = "c" if analysis_id == "m0-c" else "python"
    view: dict = {
        "analysis_id": analysis_id,
        "stage": rec.stage,
        "availability": rec.availability.value,
        "observation_class": rec.observation_class.value,
        "counts": rec.counts,
        "limitations": rec.limitations,
        "invocation": rec.invocation.model_dump(),
        "artifact": rec.artifacts[0].model_dump() if rec.artifacts else None,
    }
    normalized = [a for a in rec.artifacts if a.path.endswith(".json")]
    if normalized:
        data = _load_json_artifact(normalized[0].path)
        if isinstance(data, list):
            view["items"] = data[:MAX_ITEMS]
            view["truncated"] = len(data) > MAX_ITEMS
            view["items_total"] = len(data)
        elif isinstance(data, dict):
            view["summary"] = data
            view["truncated"] = False
    else:
        raw = [a for a in rec.artifacts if not a.path.endswith(".json")]
        if raw:
            view.update(_text_excerpt(raw[0].path))
    return view
