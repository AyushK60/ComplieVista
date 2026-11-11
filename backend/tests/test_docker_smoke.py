"""Integration smoke: one curated deterministic run under the restrictive Docker
baseline, executed through the same code path as the feasibility probe. Skipped
cleanly when Docker is unavailable. This is feasibility evidence, NOT a sandbox
safety claim (ADR-0003; adversarial tests are an stage 4 gate).
"""
import importlib.util
import shutil
import sys
import uuid
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

from app.services import staging  # noqa: E402


def _load_feasibility():
    spec = importlib.util.spec_from_file_location("feasibility_m0", REPO / "sandbox" / "feasibility_m0.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")
def test_curated_python_container_smoke():
    feas = _load_feasibility()
    job_id = f"pytest-smoke-{uuid.uuid4().hex[:8]}"
    job = staging.snapshot_tree(REPO / "sandbox" / "fixtures", job_id)
    try:
        img = feas.ensure_image(feas.PY_IMAGE)
        assert img["repo_digest"], "pinned image identity must be recorded"
        r = feas.docker_run("pytest_smoke", feas.PY_IMAGE, img["repo_digest"],
                            job["staged_dir"], ["python3", "/work/py_curated.py"],
                            0, "total=28\n", timeout_s=60)
        assert r["pass"], f"smoke probe failed: {r}"
        assert r["image_repo_digest"] == img["repo_digest"]
    finally:
        staging.cleanup_job(job_id)
