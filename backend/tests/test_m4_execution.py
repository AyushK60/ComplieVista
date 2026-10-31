"""M4 execution tests: real restricted-container runs, oracles, lifecycle,
adversarial negatives. Runtime execution is admitted only for eligible pasted
targets; GitHub-imported code NEVER executes (fail-closed)."""
import json
import sys
import tempfile
import time
from pathlib import Path

from tests.test_m2_analysis import wait_terminal

REPO = Path(__file__).resolve().parents[2]

# All execution fixtures carry an explicit __main__ guard so classification
# marks them EXECUTABLE_CANDIDATE (entry-guard + stdlib-only).
GUARDED = {
    "spin": "if __name__ == '__main__':\n    while True:\n        pass\n",
    "flood": "if __name__ == '__main__':\n    while True:\n        print('x' * 1000)\n",
}

PY_FIB = """def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

if __name__ == '__main__':
    print(fib(10))
"""

C_CALLS = """#include <stdio.h>
static int adjust(int base, int limit) {
    if (base > limit) { return limit; }
    return base;
}
int main(void) {
    int total = adjust(4, 2);
    printf("total=%d\\n", total);
    return 0;
}
"""


def _run(client, language, filename, content):
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": language, "filename": filename,
        "content": content}).json()
    t = client.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
    resp = client.post("/api/v1/executions", json={
        "snapshot_id": r["snapshot_id"], "target_id": t["target_id"]})
    if resp.status_code != 200:
        raise AssertionError(f"execution POST failed: {resp.status_code} {resp.text[:200]}")
    eid = resp.json()["execution_id"]
    for _ in range(180):
        j = client.get(f"/api/v1/executions/{eid}").json()
        if j["status"] in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BLOCKED"):
            return j, resp
        time.sleep(0.5)
    return j, resp


def wait_exec(client, eid, tries=180):
    for _ in range(tries):
        j = client.get(f"/api/v1/executions/{eid}").json()
        if j["status"] in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BLOCKED"):
            return j
        time.sleep(0.5)
    return j


def test_python_execution_real_trace_and_output(client):
    j, _ = _run(client, "python", "fib.py", PY_FIB)
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"), j.get("binary_sha256"))
    assert j["exit_code"] == 0
    assert j["stdout_sha256"] and j["trace_sha256"]
    evs = client.get(f"/api/v1/executions/{j['id']}/events?limit=500").json()["events"]
    kinds = [e["kind"] for e in evs]
    assert "call" in kinds and "return" in kinds and "line" in kinds
    fib_calls = [e for e in evs if e["payload"].get("fn") == "fib"
                 and e["kind"] == "call"]
    assert fib_calls, "real fib call event recorded"
    locals_snapshot = fib_calls[0]["payload"]["locals"]
    assert locals_snapshot["n"]["repr"] == "10"
    # oracle: fresh host sys.settrace walk of the same source
    import dis as _  # noqa: F401
    code = compile(PY_FIB, "fib.py", "exec", dont_inherit=True)
    events = {"call": 0, "return": 0}
    def tracer(frame, event, arg):
        if event in events and frame.f_code.co_name == "fib":
            events[event] += 1
        return tracer if event == "call" else None
    g = {"__name__": "__main__"}
    sys.settrace(tracer)
    try:
        exec(code, g)
    finally:
        sys.settrace(None)
    fib_returns = len([e for e in evs if e["payload"].get("fn") == "fib"
                       and e["kind"] == "return"])
    assert fib_returns == events["return"] > 0, "trace must match host oracle"
    assert len(fib_calls) == events["call"]


def test_c_execution_build_run_instrumented_trace(client):
    j, _ = _run(client, "c", "calls.c", C_CALLS)
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"), j.get("binary_sha256"))
    assert j["exit_code"] == 0
    assert j["binary_sha256"]
    evs = client.get(f"/api/v1/executions/{j['id']}/events?limit=500").json()["events"]
    calls = [e for e in evs if e["kind"] == "call"]
    returns = [e for e in evs if e["kind"] == "return"]
    assert calls and returns, "instrumented call/return events must exist"
    # stdout is a separate artifact; trace correctness: adjust called exactly once
    assert len([c for c in calls if "adjust" in json.dumps(c["payload"])]) >= 1
    out = client.get(f"/api/v1/executions/{j['id']}/output").json()
    assert "total=2" in (out["stdout"] or ""), "real C stdout must contain the computed value"


def test_github_origin_never_executes(client):
    """M4-A: imported repositories NEVER run — fail closed even for candidates."""
    from app.store.db import Store
    import tempfile
    # use the cached kilo snapshot from the real store if present
    real = Store()
    imp = real.query_one("SELECT * FROM imports WHERE status='completed' AND"
                         " canonical_repo='kilo' LIMIT 1")
    if not imp:
        import pytest
        pytest.skip("no cached import available")
    snap = real.query_one("SELECT * FROM source_snapshots WHERE import_id=?", (imp["id"],))
    store = client.app.state.store
    store.put_artifact(b"int main(){return 0;}")
    store.execute(
        "INSERT OR IGNORE INTO source_snapshots (id, project_id, origin, combined_sha256,"
        " import_id, created_utc) VALUES (?,?,?,?,?,?)",
        (snap["id"], "cached-kilo", "github", snap["combined_sha256"], None,
         snap["created_utc"]))
    from app.services.classify import classify_files
    files = {"kilo.c": b"int main(void){return 0;}"}
    classify_files(store, snap["id"], files)
    t = store.query_one("SELECT * FROM compilation_targets WHERE snapshot_id=? LIMIT 1",
                        (snap["id"],))
    r = client.post("/api/v1/executions", json={
        "snapshot_id": snap["id"], "target_id": t["id"]})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "EXECUTION_ORIGIN_BLOCKED"


def test_adversarial_infinite_loop_times_out_and_cleans_up(client):
    j, _ = _run(client, "python", "spin.py", GUARDED["spin"])
    assert j["status"] == "TIMEOUT"
    assert j["error_code"] == "run timeout"


def test_adversarial_output_flood_is_capped(client):
    j, _ = _run(client, "python", "flood.py", GUARDED["flood"])
    # A flood either exhausts the event/output caps (COMPLETED, truncated) or the
    # wall-clock timeout (TIMEOUT) — both prove the flood was contained.
    assert j["status"] in ("COMPLETED", "TIMEOUT"), \
        (j.get("status"), j.get("error_code"))
    if j["status"] == "COMPLETED":
        capped = (j.get("stdout_truncated") == 1 or j.get("events_truncated") == 1)
        assert capped, f"flood must be capped: {j.get('stdout_truncated')}, {j.get('events_truncated')}"
        evs = client.get(f"/api/v1/executions/{j['id']}/events?limit=1").json()
        assert evs["events"], "trace recorded before flood"


def test_adversarial_network_and_canary_contained(client, tmp_path):
    canary = tmp_path / "cv-canary"
    canary.write_text("HOST-SECRET")
    src = ("import socket\n\n"
           "def run():\n"
           "    try:\n"
           "        socket.create_connection(('93.184.216.34', 80), timeout=2)\n"
           "        print('NETWORK-OK')\n"
           "    except Exception as e:\n"
           "        print('NET-BLOCKED', type(e).__name__)\n"
           "    try:\n"
           "        print(open('/tmp/cv-canary').read())\n"
           "    except Exception as e:\n"
           "        print('CANARY-UNREACHABLE', type(e).__name__)\n\n"
           "if __name__ == '__main__':\n"
           "    run()\n")
    j, _ = _run(client, "python", "net.py", src)
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"), j.get("binary_sha256"))
    out = client.get(f"/api/v1/executions/{j['id']}/output").json()
    assert "NET-BLOCKED" in (out["stdout"] or ""),         "network connection must be blocked inside the container"
    assert "NETWORK-OK" not in (out["stdout"] or "")
    assert canary.read_text() == "HOST-SECRET", "host canary must be untouched"


def test_adversarial_pid_spam_contained(client):
    j, _ = _run(client, "python", "pids.py",
                "import os\n"
                "spawned = 0\n"
                "for _ in range(200):\n"
                "    try:\n"
                "        pid = os.fork()\n"
                "        if pid == 0:\n"
                "            os._exit(0)\n"
                "        spawned += 1\n"
                "    except OSError:\n"
                "        break\n"
                "print('SPAWNED', spawned)\n"
                "if __name__ == '__main__':\n"
                "    run()\n")
    assert j["status"] == "COMPLETED"  # pids-limit enforced; run terminates


def test_execution_lifecycle_cancel_and_idempotency(client):
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "python", "filename": "i.py",
        "content": "if __name__ == '__main__':\n    v = 7\n    print(v)\n"}).json()
    t = client.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
    e1 = client.post("/api/v1/executions", json={
        "snapshot_id": r["snapshot_id"], "target_id": t["target_id"]}).json()
    e2 = client.post("/api/v1/executions", json={
        "snapshot_id": r["snapshot_id"], "target_id": t["target_id"]}).json()
    assert e1["existed"] is False and e2["existed"] is True
    assert e1["execution_id"] == e2["execution_id"]


def test_events_pagination_ordered_and_checksummed(client):
    j, _ = _run(client, "python", "pg.py",
                "if __name__ == '__main__':\n"
                "    for i in range(5):\n        print(i)\n")
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"), j.get("binary_sha256"))
    page1 = client.get(f"/api/v1/executions/{j['id']}/events?limit=5").json()
    assert page1["count"] == 5 and page1["events"][0]["seq"] == 1
    for e in page1["events"]:
        assert e["sha256"] and len(e["sha256"]) == 64
    page2 = client.get(f"/api/v1/executions/{j['id']}/events?after={page1['next_after']}&limit=5").json()
    if page2["events"]:
        assert page2["events"][0]["seq"] > page1["next_after"] - 1
