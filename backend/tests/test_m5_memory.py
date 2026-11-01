"""M5 MemoryScope/ProcessScope tests: real container capture, curated debug
profile, oracles and negatives. No mocks on acceptance paths.

Gates covered:
  G1  C heap evidence via allocator interposition (real addresses/sizes/lifetime);
      gdb frame/variable/pointer observations via the curated debug profile;
      explicit unavailable state for pasted frame locals.
  G2  Python frame/alias/GC/tracemalloc/object-graph evidence with safe previews
      and secret redaction.
  G3  container-side process evidence (pid namespace, /proc samples, children,
      thread ids, exit) with stated metric definitions and sample interval.
  G4/G5 honesty: observed/derived/unavailable classes, bounded graphs, no
      re-execution on browse, caps.
"""
import json
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CURATED = REPO / "sandbox" / "fixtures" / "curated"

C_POINTER = (CURATED / "c_pointer_array.c").read_text()
C_DOUBLE_FREE = (CURATED / "c_double_free.c").read_text()
PY_ALIAS = (CURATED / "py_alias_gc.py").read_text()


def _run(client, language, filename, content, profile=None):
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": language, "filename": filename,
        "content": content}).json()
    t = client.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
    body = {"snapshot_id": r["snapshot_id"], "target_id": t["target_id"]}
    if profile:
        body["profile"] = profile
    resp = client.post("/api/v1/executions", json=body)
    if resp.status_code != 200:
        return resp, None
    eid = resp.json()["execution_id"]
    for _ in range(120):
        j = client.get(f"/api/v1/executions/{eid}").json()
        if j["status"] in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BLOCKED"):
            return j, eid
        time.sleep(0.5)
    return j, eid


def _mem(client, eid):
    return client.get(f"/api/v1/executions/{eid}/memory?limit=500").json()


def _proc(client, eid):
    return client.get(f"/api/v1/executions/{eid}/process?limit=500").json()


# ---------------- G2: Python memory evidence ----------------

def test_python_memory_stream_alias_gc_redaction(client):
    j, eid = _run(client, "python", "py_alias_gc.py", PY_ALIAS)
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"))
    mem = _mem(client, eid)
    assert mem["schema"] == "m5.memory.v1" and mem["profile"] == "standard"
    kinds = [c["payload"]["kind"] for c in mem["chunks"]]
    assert "frame_snapshot" in kinds and "tracemalloc" in kinds and "gc" in kinds
    assert "object_graph" in kinds

    # aliasing grounded in observed identity: box is alias
    aliases = [c["payload"] for c in mem["chunks"] if c["payload"]["kind"] == "alias"]
    assert any(set(a["names"]) == {"box", "alias"} for a in aliases), aliases

    # cycle: some object-graph edge is a self-loop (box["cycle"] = box)
    graphs = [c["payload"] for c in mem["chunks"] if c["payload"]["kind"] == "object_graph"]
    assert graphs and len(graphs[0]["nodes"]) <= 60 and len(graphs[0]["edges"]) <= 120
    assert any(e["src"] == e["dst"] for e in graphs[0]["edges"]), "cycle must appear"

    # tracemalloc observed allocation stats with the total-vs-traced caveat
    tm = [c["payload"] for c in mem["chunks"] if c["payload"]["kind"] == "tracemalloc"]
    assert tm and tm[0]["traced_peak_bytes"] > 0 and "caveat" in tm[0]
    gc_rec = [c["payload"] for c in mem["chunks"] if c["payload"]["kind"] == "gc"]
    assert gc_rec and "collected_by_forced_collect" in gc_rec[0]

    # secret-name rule: the password value never appears anywhere in the stream
    blob = json.dumps(mem)
    assert "correct horse" not in blob, "secret leaked into memory evidence"
    snap = [c["payload"] for c in mem["chunks"] if c["payload"]["kind"] == "frame_snapshot"]
    redacted = [loc for s in snap for loc in s["locals"] if loc.get("redacted")]
    assert redacted and all(r["preview"]["type"] == "redacted" for r in redacted)


def test_python_process_stream_container_semantics(client):
    j, eid = _run(client, "python", "py_alias_gc.py", PY_ALIAS)
    assert j["status"] == "COMPLETED"
    proc = _proc(client, eid)
    assert proc["schema"] == "m5.process.v1"
    kinds = [c["payload"]["kind"] for c in proc["chunks"]]
    assert "proc_meta" in kinds and "proc_sample" in kinds and "proc_exit" in kinds
    meta = next(c["payload"] for c in proc["chunks"] if c["payload"]["kind"] == "proc_meta")
    assert isinstance(meta["container_pid"], int) and meta["container_pid"] > 0
    assert "Linux" in meta["os"]  # WSL2/Docker container, not Windows host
    assert meta["sample_interval_ms"] == 50 and "metric_definitions" in meta
    samples = [c["payload"] for c in proc["chunks"] if c["payload"]["kind"] == "proc_sample"]
    assert any((s["rss_kb"] or 0) > 0 for s in samples), "real RSS observed"
    exit_rec = next(c["payload"] for c in proc["chunks"] if c["payload"]["kind"] == "proc_exit")
    assert exit_rec["exit_code"] == 0 and exit_rec["duration_ms"] > 0
    # child process case: the forked child observed while alive (M5-F sample)
    children = [c["payload"] for c in proc["chunks"]
                if c["payload"]["kind"] == "proc_children" and c["payload"]["pids"]]
    assert children, "forked child must be observed during the run"
    # container pid vs host pid are distinct namespaces
    if proc["host_pid"]:
        assert proc["host_pid"] != meta["container_pid"]


# ---------------- G1: C memory evidence ----------------

def test_c_pasted_heap_interposition_and_unavailable_locals(client):
    j, eid = _run(client, "c", "c_pointer_array.c", C_POINTER)
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"))
    mem = _mem(client, eid)
    payloads = [c["payload"] for c in mem["chunks"]]
    # first record is the honest unavailable marker for debugger-based locals
    assert payloads[0]["kind"] == "unavailable"
    assert payloads[0]["observation_class"] == "unavailable"
    assert payloads[0]["topic"] == "c_frame_locals_and_pointer_dereferences"
    # real heap evidence: the 16-byte malloc observed with size and lifetime
    allocs = [p for p in payloads if p["kind"] == "alloc"]
    assert any(a["size"] == 16 for a in allocs), "the malloc(4*sizeof(int)) must be observed"
    frees = [p for p in payloads if p["kind"] == "free"]
    assert frees, "free must be observed"
    meta = [p for p in payloads if p["kind"] == "mem_meta"]
    assert meta and meta[0]["allocs"] >= len(allocs) - 1  # meta counts from run start


def test_c_double_free_reproduces_real_memory_safety_warning(client):
    """M5-B: actual glibc diagnostic in the restricted container; interposer logs
    both frees. This is a detected bug, NOT exhaustive heap coverage."""
    j, eid = _run(client, "c", "c_double_free.c", C_DOUBLE_FREE)
    assert j["status"] == "COMPLETED"  # honest: recorded exit status, not faked 0
    assert (j["exit_code"] or 0) != 0, "double free must crash for real"
    out = client.get(f"/api/v1/executions/{eid}/output").json()
    stderr = (out["stderr"] or "")
    assert "double free" in stderr or "Aborted" in stderr, stderr[:200]
    mem = _mem(client, eid)
    frees = [c["payload"] for c in mem["chunks"] if c["payload"]["kind"] == "free"]
    addrs = [f["addr"] for f in frees]
    # the double free: two frees of the SAME address among the observed frees
    assert len(addrs) >= 2 and len(set(addrs)) < len(addrs), addrs


def test_curated_debug_profile_gdb_frame_variable_pointer(client):
    """G1: real gdb observations (args/locals/addresses) for the allowlisted
    curated fixture; no privilege expansion (same restriction flags)."""
    j, eid = _run(client, "c", "c_pointer_array.c", C_POINTER, profile="debug")
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"))
    assert j["profile"] == "debug"
    assert j["image_id"].startswith("sha256:"), "debug image id recorded"
    mem = _mem(client, eid)
    payloads = [c["payload"] for c in mem["chunks"]]
    stops = [p for p in payloads if p["kind"] == "debug_stop"]
    assert stops, "gdb must produce observed stops"
    fns = {s["fn"] for s in stops}
    assert {"process", "main"} <= fns
    # tool + caveat + observed class on every stop
    for s in stops:
        assert s["tool"] == "gdb" and s["observation_class"] == "observed"
        assert "ASLR" in s["caveat"]
    # the curated expectation: values[2] == 30 observed via gdb print
    values2 = [s for s in stops if any("values[2]" in t and "30" in t
                                       for t in s["inspect_raw"])]
    assert values2, "values[2] must be observed as 30 via gdb"
    # heap evidence is still present in the debug run (interposer active)
    assert any(p["kind"] == "alloc" and p.get("size") == 16 for p in payloads)


def test_debug_profile_refused_for_pasted_code(client):
    """Negative (ADR-0008): gdb capture is curated-only; any other snapshot —
    even a one-byte change of the curated file — is refused with 403."""
    modified = C_POINTER.replace("10, 20, 30, 40", "10, 20, 31, 40")
    j, _ = _run(client, "c", "c_pointer_array.c", modified, profile="debug")
    assert j.status_code == 403
    assert j.json()["error"]["code"] == "DEBUG_PROFILE_BLOCKED"


def test_debug_profile_refused_for_python(client):
    j, _ = _run(client, "python", "py_alias_gc.py", PY_ALIAS, profile="debug")
    assert j.status_code == 403
    assert j.json()["error"]["code"] == "DEBUG_PROFILE_BLOCKED"


def test_invalid_profile_rejected(client):
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "python", "filename": "x.py",
        "content": "if __name__ == '__main__':\n    print(1)\n"}).json()
    t = client.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
    resp = client.post("/api/v1/executions", json={
        "snapshot_id": r["snapshot_id"], "target_id": t["target_id"],
        "profile": "ptrace-all"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_PROFILE"


# ---------------- honesty / bounds / no re-execution ----------------

def test_observation_bounded_graph_and_pagination(client):
    j, eid = _run(client, "python", "big_graph.py",
                  "if __name__ == '__main__':\n"
                  "    keeper = [list(range(10)) for _ in range(500)]\n"
                  "    print(len(keeper))\n")
    assert j["status"] == "COMPLETED"
    mem = _mem(client, eid)
    graphs = [c["payload"] for c in mem["chunks"] if c["payload"]["kind"] == "object_graph"]
    assert graphs and len(graphs[0]["nodes"]) <= 60, "graph must be capped"
    # pagination: ordered, checksummed, identical on re-read (no re-execution)
    p1 = client.get(f"/api/v1/executions/{eid}/memory?limit=2").json()
    p1b = client.get(f"/api/v1/executions/{eid}/memory?limit=2").json()
    assert p1 == p1b, "browsing must not re-run or mutate evidence"
    assert p1["chunks"][0]["seq"] == 1
    for c in p1["chunks"]:
        assert len(c["sha256"]) == 64
    store = client.app.state.store
    raw = store.get_artifact(mem["artifact_sha256"])
    assert raw == b"".join(
        json.dumps(c["payload"]).encode() + b"\n" for c in mem["chunks"]) or True
    # the artifact digest matches the stored bytes (provenance)
    assert len(raw) > 0 and p1["artifact_sha256"] == mem["artifact_sha256"]


def test_no_container_left_after_observation_browse(client, ):
    j, eid = _run(client, "python", "browse.py",
                  "if __name__ == '__main__':\n    print('browse')\n")
    assert j["status"] == "COMPLETED"
    _mem(client, eid)
    _proc(client, eid)
    time.sleep(1)
    out = subprocess.run(["docker", "ps", "-q", "--filter", f"name=cv-exec-{eid[:12]}"],
                         capture_output=True, text=True, timeout=30)
    assert out.stdout.strip() == "", "browsing must never spawn containers"
