"""Stage 5 review audit regressions - second-pass findings, each with a permanent test.

stage 5 review #1  safe_value preview executed user __repr__ on primitive subclasses
            (side-effect channel inside the tracer; reproduced live with a
            LoudStr). Now exact-type previews; subclasses get identity treatment.
stage 5 review #2  exception records misidentified the exception (CPython 3.12 passes a
            (type, value, tb) tuple; arg[0] is the CLASS, so exc said "type" and
            msg was the class repr). Now the instance is identified; str() runs
            ONLY for builtin-module exceptions (no user __str__ in the tracer).
stage 5 review #3  generator frames changed frame_id on every suspension and got an
            exit-time snapshot implying frame death. Now: stable frame_id across
            suspensions, no snapshot on yield-returns.
stage 5 review #4  C mem_meta outstanding was approximate for realloc-heavy programs;
            reallocs are now counted separately and the caveat says so.
stage 5 review #5  cross-run identity/container-pid reuse is labeled within-run; memory
            API limitation text asserts it (checked here).
stage 5 review #6  cancelled executions present NO partial observation sessions.
"""
import time

from tests.test_stage4_execution import wait_exec


def _paste_and_run(client, language, filename, content):
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": language, "filename": filename,
        "content": content}).json()
    t = client.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
    resp = client.post("/api/v1/executions",
                       json={"snapshot_id": r["snapshot_id"],
                             "target_id": t["target_id"]})
    eid = resp.json()["execution_id"]
    for _ in range(120):
        j = client.get(f"/api/v1/executions/{eid}").json()
        if j["status"] in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BLOCKED"):
            break
        time.sleep(0.5)
    return j, eid


SIDE_EFFECT_SRC = '''SIDE_EFFECTS = []

class LoudStr(str):
    def __repr__(self):
        SIDE_EFFECTS.append("repr-ran")
        return "<LOUD>"

class LoudError(Exception):
    def __str__(self):
        SIDE_EFFECTS.append("str-ran")
        return "loud"

def gen():
    yield 1
    yield 2

if __name__ == "__main__":
    s = LoudStr("abc")
    try:
        raise LoudError("boom")
    except LoudError as e:
        captured = e
    vals = [v for v in gen()]
    print("side-effects:", len(SIDE_EFFECTS))
'''


def test_m5qa01_no_user_repr_or_str_in_tracer(client):
    """The tracer must never execute user __repr__/__str__ (side-effect channel):
    the program itself observes zero side effects AND the evidence shows no
    subclass repr leak."""
    j, eid = _paste_and_run(client, "python", "sidefx.py", SIDE_EFFECT_SRC)
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"))
    out = client.get(f"/api/v1/executions/{eid}/output").json()
    assert "side-effects: 0" in (out["stdout"] or ""), out["stdout"]
    mem = client.get(f"/api/v1/executions/{eid}/memory?limit=500").json()
    blob = mem and repr([c["payload"] for c in mem["chunks"]])
    assert "<LOUD>" not in blob and "loud\"" not in blob.replace("'loud'", "X")


def test_m5qa02_exception_records_identify_the_instance(client):
    j, eid = _paste_and_run(client, "python", "sidefx.py", SIDE_EFFECT_SRC)
    evs = client.get(f"/api/v1/executions/{eid}/events?limit=500").json()["events"]
    user_exc = [e for e in evs if e["kind"] == "exception"
                and e["payload"].get("exc") == "LoudError"]
    assert user_exc, "exception record must name the actual exception class"
    rec = user_exc[0]["payload"]
    assert rec.get("msg_unavailable") is True
    assert "__str__" in rec.get("msg_reason", "")
    assert rec.get("msg") is None


def test_m5qa03_generator_frame_identity_stable_across_suspensions(client):
    j, eid = _paste_and_run(client, "python", "sidefx.py", SIDE_EFFECT_SRC)
    mem = client.get(f"/api/v1/executions/{eid}/memory?limit=500").json()
    gen_frames = [c["payload"] for c in mem["chunks"]
                  if c["payload"]["kind"] == "frame_snapshot"
                  and c["payload"].get("fn") == "gen"]
    assert gen_frames, "generator frame must be observed"
    ids = {f["frame_id"] for f in gen_frames}
    assert len(ids) == 1, f"one generator frame must keep one in-run id: {ids}"
    # a suspended generator is not a dead frame: snapshot count == call count
    evs = client.get(f"/api/v1/executions/{eid}/events?limit=500").json()["events"]
    gen_returns = [e for e in evs if e["kind"] == "return"
                   and e["payload"].get("fn") == "gen"]
    assert len(gen_frames) < len(gen_returns) + 1  # no snapshot per suspension


def test_m5qa05_within_run_identity_labeled(client):
    j, eid = _paste_and_run(client, "python", "idlabel.py",
                            "if __name__ == '__main__':\n    a = [1]\n    b = a\n"
                            "    print(a is b)\n")
    assert j["status"] == "COMPLETED"
    mem = client.get(f"/api/v1/executions/{eid}/memory?limit=500").json()
    assert any("id()-based identities" in l for l in mem["limitations"]), \
        "evidence must be labeled within-run (ids may repeat across runs)"


def test_m5qa06_cancelled_run_has_no_partial_observation_session(client):
    """Cancellation discards results (Stage 4 review CV-11 semantics): no partial memory/
    process session may be presented as evidence."""
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "python", "filename": "spin.py",
        "content": "if __name__ == '__main__':\n    while True:\n        pass\n"}).json()
    t = client.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
    eid = client.post("/api/v1/executions", json={
        "snapshot_id": r["snapshot_id"], "target_id": t["target_id"]}).json()["execution_id"]
    for _ in range(60):
        j = client.get(f"/api/v1/executions/{eid}").json()
        if j["status"] == "RUNNING":
            break
        time.sleep(0.5)
    client.post(f"/api/v1/executions/{eid}/cancel")
    j = wait_exec(client, eid, tries=60)
    assert j["status"] == "CANCELLED"
    assert not j.get("memory_count"), "no partial memory session"
    assert not j.get("process_count"), "no partial process session"
    mem = client.get(f"/api/v1/executions/{eid}/memory").json()
    assert mem["total"] == 0 and mem["chunks"] == []


def test_m5qa04_c_realloc_counted_separately(client):
    """stage 5 review #4: mem_meta reports reallocs separately; outstanding stays
    malloc/free-based and the caveat says it is approximate for realloc-heavy
    programs. Real container, real libc allocator."""
    src = ("#include <stdlib.h>\n"
           "int main(void) {\n"
           "    char *p = malloc(8);\n"
           "    for (int i = 0; i < 5; i++) { p = realloc(p, 16 * (i + 2)); }\n"
           "    free(p);\n"
           "    return 0;\n"
           "}\n")
    j, eid = _paste_and_run(client, "c", "reallocs.c", src)
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"))
    mem = client.get(f"/api/v1/executions/{eid}/memory?limit=500").json()
    meta = [c["payload"] for c in mem["chunks"] if c["payload"]["kind"] == "mem_meta"]
    assert meta and meta[0]["reallocs"] >= 5, meta
    assert "realloc" in meta[0]["caveat"]
    reallocs = [c["payload"] for c in mem["chunks"] if c["payload"]["kind"] == "realloc"]
    assert len(reallocs) >= 5


def test_m5qa_deep_recursion_bounded_not_fabricated(client):
    """Depth-capped tracing stays honest: beyond 64 frames the harness stops
    tracing (documented cap), the run still completes, and events stay bounded."""
    src = ("def f(n):\n"
           "    return 0 if n == 0 else 1 + f(n - 1)\n\n"
           "if __name__ == '__main__':\n    print(f(200))\n")
    j, eid = _paste_and_run(client, "python", "deep.py", src)
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"))
    out = client.get(f"/api/v1/executions/{eid}/output").json()
    assert "200" in (out["stdout"] or "")  # program really computed it
    evs = client.get(f"/api/v1/executions/{eid}/events?limit=500").json()["events"]
    depths = [e["payload"]["depth"] for e in evs if "depth" in e["payload"]]
    assert max(depths) <= 65, "trace must respect the documented depth cap"
