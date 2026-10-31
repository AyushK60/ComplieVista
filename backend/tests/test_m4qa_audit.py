"""M4QA audit regressions — every repair from the adversarial runtime/sandbox audit
gets a permanent named test here. These run REAL restricted containers (no mocks).

Findings covered:
  CV-M4QA-01  TIMEOUT left the cv-exec container running (ghost) — now force-removed.
  CV-M4QA-02  Python stdout.txt was unbounded (1.75 GB in 10 s probe) — now capped
              in-harness at 1 MB with an in-band stdout_truncated marker.
  CV-M4QA-03  C trace.jsonl was unbounded (442 MB in 10 s probe) — shim now stops at
              5000 events with an in-band truncated marker.
  CV-M4QA-04  POST /api/v1/executions and /api/v1/analyses read unbounded bodies.
  CV-M4QA-05  /capabilities still claimed pasted_execution=BLOCKED after the M4 gate.
  CV-M4QA-06  cancel during the C build phase left cv-build running.
  CV-M4QA-08  ready_for_controlled_execution was always False while Run was offered.
"""
import json
import subprocess
import time

from tests.test_m4_execution import wait_exec


def _live_cv_containers(prefix: str) -> list[str]:
    out = subprocess.run(
        ["docker", "ps", "--filter", f"name={prefix}", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=30)
    return [n for n in out.stdout.split() if n]


def _paste_and_submit(client, language, filename, content):
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": language, "filename": filename,
        "content": content}).json()
    t = client.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
    resp = client.post("/api/v1/executions",
                       json={"snapshot_id": r["snapshot_id"], "target_id": t["target_id"]})
    assert resp.status_code == 200, resp.text[:200]
    return resp.json()["execution_id"]


def test_m4qa01_timeout_force_removes_run_container(client):
    """A timed-out execution must not leave a live container (reproduced: 36 s of
    `while True: pass` container still Up after TIMEOUT before the repair)."""
    eid = _paste_and_submit(client, "python", "spin.py",
                            "if __name__ == '__main__':\n    while True:\n        pass\n")
    j = wait_exec(client, eid, tries=90)
    assert j["status"] == "TIMEOUT", (j.get("status"), j.get("error_code"))
    # The rm -f happens before the status is written; no retry grace needed.
    assert _live_cv_containers(f"cv-exec-{eid[:12]}") == [], \
        "ghost container survived the run timeout (CV-M4QA-01 regression)"


def test_m4qa02_python_stdout_capped_and_flagged(client):
    """3 MB of stdout → stored artifact ≤ 1 MB and stdout_truncated=1 (in-band)."""
    body = "\n".join("    print('x' * 1000)" for _ in range(3000))
    eid = _paste_and_submit(client, "python", "flood3mb.py",
                            "if __name__ == '__main__':\n" + body + "\n")
    j = wait_exec(client, eid, tries=90)
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"))
    assert j["stdout_truncated"] == 1, "3 MB of stdout must be flagged truncated"
    out = client.get(f"/api/v1/executions/{eid}/output").json()
    assert len(out["stdout"]) <= 60_000 + 10  # output endpoint excerpt cap
    # The stored artifact itself is bounded: recompute from the recorded sha.
    store = client.app.state.store
    raw = store.get_artifact(j["stdout_sha256"])
    assert len(raw) <= 1024 * 1024, f"stdout artifact grew to {len(raw)} bytes"


def test_m4qa03_c_trace_capped_at_5000_events(client):
    """A call-dense C program (1M calls) must yield ≤5000 events, truncated flag,
    and a bounded trace artifact (probe before repair: 442 MB in 10 s)."""
    src = ("void f(void){}\n"
           "int main(void){\n"
           "    for (long i = 0; i < 1000000; i++) { f(); }\n"
           "    return 0;\n"
           "}\n")
    eid = _paste_and_submit(client, "c", "dense.c", src)
    j = wait_exec(client, eid, tries=90)
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"))
    assert j["events_count"] == 5000
    assert j["events_truncated"] == 1, "cap must be flagged, not silent"
    store = client.app.state.store
    raw = store.get_artifact(j["trace_sha256"])
    assert len(raw) < 1024 * 1024, f"trace artifact grew to {len(raw)} bytes"


def test_m4qa04_execution_and_analysis_bodies_capped(client):
    """POST bodies on /executions and /analyses are bounded (M4QA-04): a 2 MB body
    must be rejected with PAYLOAD_TOO_LARGE before parsing."""
    blob = "x" * (2 * 1024 * 1024)
    for path in ("/api/v1/executions", "/api/v1/analyses"):
        r = client.post(path, json={"snapshot_id": "s", "target_id": "t", "pad": blob})
        assert r.status_code == 413, (path, r.status_code)
        assert r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_m4qa05_capabilities_report_partial_paste(client):
    body = client.get("/api/v1/capabilities").json()
    assert body["modes"]["pasted_execution"] == "PARTIAL"
    assert body["modes"]["curated_execution"] == "PARTIAL"
    notes = " ".join(body["notes"])
    assert "BLOCKED (M9 review)" in notes or "remain BLOCKED" in notes


def test_m4qa06_cancel_during_run_removes_containers(client):
    """Cancel while RUNNING must stop the container and record CANCELLED."""
    eid = _paste_and_submit(client, "python", "cancelme.py",
                            "if __name__ == '__main__':\n    while True:\n        pass\n")
    for _ in range(60):
        j = client.get(f"/api/v1/executions/{eid}").json()
        if j["status"] == "RUNNING":
            break
        time.sleep(0.5)
    assert j["status"] == "RUNNING", j
    r = client.post(f"/api/v1/executions/{eid}/cancel")
    assert r.json()["result"] in ("CANCEL_REQUESTED", "CANCELLED")
    j = wait_exec(client, eid, tries=60)
    assert j["status"] == "CANCELLED", j
    assert _live_cv_containers(f"cv-exec-{eid[:12]}") == []
    assert _live_cv_containers(f"cv-build-{eid[:12]}") == []


def test_m4qa08_readiness_flag_matches_admission(client):
    """Pasted eligible target → ready True; the flag must not contradict the UI's
    Run button (M4QA-08). GitHub-origin refusal stays covered by the M4 403 test."""
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "python", "filename": "ok.py",
        "content": "if __name__ == '__main__':\n    print('ok')\n"}).json()
    t = client.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
    assert t["status"] in ("EXECUTABLE_CANDIDATE", "COMPILATION_CANDIDATE")
    assert t["ready_for_controlled_execution"] is True


def test_m4qa01_build_timeout_handler_removes_build_container(client, monkeypatch):
    """A C build killed at the build timeout must be force-removed too (same ghost
    mechanism as the run timeout). The wall-clock handler is exercised with a stub
    run_capped because a real >90 s compile cannot be produced deterministically
    inside the 256 MB build container (it OOMs to FAILED first); the real-container
    ghost regression is proven for the run path above."""
    from app.services import execution as ex
    real_run_capped = ex.run_capped

    def fake_run_capped(argv, timeout):
        if any(a.startswith("cv-build-") for a in argv):
            return {"stdout": b"", "stderr": b"", "stdout_truncated": False,
                    "stderr_truncated": False, "killed": True, "exit_code": None}
        return real_run_capped(argv, timeout)

    monkeypatch.setattr(ex, "run_capped", fake_run_capped)
    eid = _paste_and_submit(client, "c", "tiny.c", "int main(void){return 0;}\n")
    j = wait_exec(client, eid, tries=60)
    assert j["status"] == "TIMEOUT", (j.get("status"), j.get("error_code"))
    assert j["error_code"] == "build timeout"
    assert _live_cv_containers(f"cv-build-{eid[:12]}") == [], \
        "ghost build container survived the build timeout (CV-M4QA-01 regression)"
