"""Stage 2 security/robustness tests: restricted invocation, timeouts, cancellation,
dedupe, docker-missing honesty, resource caps, and DB migration from m1.v1."""
import json
import subprocess

import pytest

from app.core import config as cfg
from app.services import analyzer
from app.services.analyzer import build_run_argv, docker_available, tool_fingerprint
from app.store.db import Store


def test_run_argv_is_allowlisted_and_socket_free(tmp_path):
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir(); out.mkdir()
    argv = build_run_argv("cv-x", src, out, "worker_c.py", "demo.c")
    assert argv[0] == "docker" and "run" in argv[:3]
    joined = " ".join(argv)
    assert "--network none" in joined and "--cap-drop ALL" in joined
    assert "--security-opt no-new-privileges" in joined and "--read-only" in joined
    assert "docker.sock" not in joined and "--privileged" not in joined
    assert "-v" in argv and f"{src}:/work:ro" in argv and f"{out}:/out" in argv
    assert any("worker_c.py" in a for a in argv) and any(
        a == "demo.c" for a in argv)
    assert "sh" not in argv[:8] and "-c" not in argv  # argv array, no shell composition


def test_tool_fingerprint_is_stable_and_nonempty():
    fp1, fp2 = tool_fingerprint(), tool_fingerprint()
    assert fp1 == fp2 and len(fp1) == 32


def test_analysis_requires_known_snapshot_and_target(client):
    r = client.post("/api/v1/analyses", json={"snapshot_id": "nope", "target_id": "nope"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_analysis_idempotent_on_same_input(client):
    src = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "python", "filename": "i.py", "content": "x = 1\n"}).json()
    t = client.get(f"/api/v1/projects/{src['project_id']}/targets").json()[0]
    j1 = client.post("/api/v1/analyses", json={
        "snapshot_id": src["snapshot_id"], "target_id": t["target_id"]}).json()
    j2 = client.post("/api/v1/analyses", json={
        "snapshot_id": src["snapshot_id"], "target_id": t["target_id"]}).json()
    assert j1["existed"] is False and j2["existed"] is True
    assert j1["analysis_id"] == j2["analysis_id"]


def test_cancel_queued_analysis(client, store, monkeypatch):
    # Prevent every runner from picking the job up: patch the class method.
    monkeypatch.setattr(analyzer._JobRunner, "enqueue", lambda self, aid: None)
    src = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "python", "filename": "c.py", "content": "y = 2\n"}).json()
    t = client.get(f"/api/v1/projects/{src['project_id']}/targets").json()[0]
    job = client.post("/api/v1/analyses", json={
        "snapshot_id": src["snapshot_id"], "target_id": t["target_id"]}).json()
    r = client.post(f"/api/v1/analyses/{job['analysis_id']}/cancel").json()
    assert r["result"] == "CANCELLED"
    assert client.get(f"/api/v1/analyses/{job['analysis_id']}").json()["status"] == "CANCELLED"


def test_timeout_path_cleans_up_and_records(client, store, monkeypatch):
    """Deterministic mechanism test: force the container run to time out and verify
    orchestrator-enforced cleanup + honest TIMEOUT status."""
    real_run = subprocess.run

    def fake_run(argv, capture_output, timeout):
        if argv and argv[0] == "docker" and "run" in argv[:4]:
            raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)
        return real_run(argv, capture_output=capture_output, timeout=timeout)

    monkeypatch.setattr(analyzer.subprocess, "run", fake_run)
    src = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "python", "filename": "t.py", "content": "z = 3\n"}).json()
    t = client.get(f"/api/v1/projects/{src['project_id']}/targets").json()[0]
    job = client.post("/api/v1/analyses", json={
        "snapshot_id": src["snapshot_id"], "target_id": t["target_id"]}).json()
    aid = job["analysis_id"]
    for _ in range(60):
        status = client.get(f"/api/v1/analyses/{aid}").json()["status"]
        if status in ("TIMEOUT", "FAILED", "CANCELLED"):
            break
        import time; time.sleep(0.3)
    assert status == "TIMEOUT"
    # no stage rows fabricated
    assert client.get(f"/api/v1/analyses/{aid}/stages/py_tokens").status_code == 404


def test_docker_missing_is_blocked_not_failed(client, store, monkeypatch):
    monkeypatch.setattr(analyzer, "docker_available", lambda: False)
    src = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "python", "filename": "d.py", "content": "w = 4\n"}).json()
    t = client.get(f"/api/v1/projects/{src['project_id']}/targets").json()[0]
    job = client.post("/api/v1/analyses", json={
        "snapshot_id": src["snapshot_id"], "target_id": t["target_id"]}).json()
    aid = job["analysis_id"]
    for _ in range(60):
        body = client.get(f"/api/v1/analyses/{aid}").json()
        if body["status"] == "BLOCKED":
            break
        import time; time.sleep(0.2)
    assert body["status"] == "BLOCKED" and body["error_code"] == "DOCKER_UNAVAILABLE"


def test_oversized_analysis_source_rejected(client):
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "c", "filename": "huge.c", "content": "x" * 600_000})
    assert r.status_code == 413


def test_job_dir_cleaned_after_run(client):
    from app.services.staging import jobs_root
    src = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "python", "filename": "cl.py", "content": "q = 9\n"}).json()
    t = client.get(f"/api/v1/projects/{src['project_id']}/targets").json()[0]
    job = client.post("/api/v1/analyses", json={
        "snapshot_id": src["snapshot_id"], "target_id": t["target_id"]}).json()
    aid = job["analysis_id"]
    for _ in range(90):
        if client.get(f"/api/v1/analyses/{aid}").json()["status"] in ("COMPLETED", "FAILED",
                                                                     "TIMEOUT", "BLOCKED"):
            break
        import time; time.sleep(0.3)
    leftovers = [p.name for p in jobs_root().glob(f"analysis-{aid[:12]}*")]
    assert leftovers == [], "disposable job directories must be cleaned"


def test_db_migrates_from_m1_v1(tmp_path):
    """A store written by stage 1 (schema tagged m1.v1) must upgrade additively to m2.v1."""
    data = tmp_path / "d"
    s1 = Store(data_dir=data)
    s1.execute("UPDATE meta SET value='m1.v1' WHERE key='schema_version'")
    s1.close()
    s2 = Store(data_dir=data)  # must not raise SCHEMA_MISMATCH
    from app.core.config import SCHEMA_VERSION
    assert s2.query_one("SELECT value FROM meta WHERE key='schema_version'")["value"] == SCHEMA_VERSION  # additive upgrade reaches the current version
    s2.query("SELECT * FROM analyses")  # m2 tables exist
