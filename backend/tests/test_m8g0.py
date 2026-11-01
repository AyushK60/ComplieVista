"""M8-G0 technical integrity regressions — F-M7-01..05, real containers where
the property is real (docker), deterministic fakes only where the property is
the orchestrator's own logic (argv assembly, tag mutation, stream parsing).

F-M7-01  Python trace channel: framed protected pipe, no writable /out mount,
         count/last-meta validation, honest trust labels, tamper fixtures.
F-M7-02  Immutable image identity: resolved IDs in the actual docker argv,
         recorded provenance == launched image, fail-closed on tag mutation.
F-M7-03  Benchmark correctness: checksums cover stdout + return + exception/exit.
F-M7-04  Trace previews never call user-defined __len__/__repr__.
(F-M7-05 Demo Library error recovery is covered by e2e/m8g0_journeys.py.)
"""
import base64
import json
import shutil
import subprocess
import time

import pytest

from app.services import analyzer as analyzer_svc
from app.services import execution as ex
from tests.test_m4_execution import wait_exec


def _docker_ready() -> bool:
    return shutil.which("docker") is not None and analyzer_svc.docker_available()


# Tolerant guard: classification needs a __main__ guard, but the bench worker
# exec's the module itself (a raising main() must not abort module exec before
# the measured repeats).
PY_GUARD = ("if __name__ == '__main__':\n"
            "    try:\n"
            "        main()\n"
            "    except Exception:\n"
            "        pass\n")


def _paste(client, language, filename, content):
    """Paste + first target. Python pastes get the __main__ guard the
    classifier needs (all fixtures define main(); bench repeats then call
    main() directly, exactly like the real bench worker)."""
    if language == "python" and "__main__" not in content:
        content += "\n" + PY_GUARD
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": language, "filename": filename,
        "content": content}).json()
    t = client.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
    return r["snapshot_id"], t["target_id"]


def _submit_run(client, snap, tgt, profile="standard"):
    resp = client.post("/api/v1/executions", json={
        "snapshot_id": snap, "target_id": tgt, "profile": profile})
    assert resp.status_code == 200, resp.text[:200]
    return resp.json()["execution_id"]


def _live_image_id(tag: str) -> str:
    out = subprocess.run(["docker", "image", "inspect", "-f", "{{.Id}}", tag],
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


FAKE_ID_A = "sha256:" + "a" * 64
FAKE_ID_B = "sha256:" + "b" * 64


def _frame_stream() -> bytes:
    """A minimal VALID harness frame stream (what py_trace_harness emits)."""
    frames = [
        {"c": "t", "j": {"kind": "call", "fn": "main", "line": 2, "depth": 2,
                          "locals": {}}},
        {"c": "t", "j": {"kind": "line", "fn": "main", "line": 3, "depth": 2}},
        {"c": "t", "j": {"kind": "return", "fn": "main", "line": 4, "depth": 2,
                          "arg": {"type": "int", "repr": "7"}}},
        {"c": "t", "j": {"kind": "exit", "exit_code": 0, "duration_ms": 5}},
        {"c": "m", "j": {"kind": "tracemalloc", "traced_current_bytes": 0,
                          "traced_peak_bytes": 0, "top": []}},
        {"c": "p", "j": {"kind": "proc_meta", "os": "Linux"}},
        {"c": "out", "j": {"b64": base64.b64encode(b"hi\n").decode()}},
        {"c": "meta", "j": {"kind": "meta", "python": "3.12.3", "events": 4,
                             "truncated": False, "stdout_truncated": False,
                             "max_events": 5000, "memory_records": 1,
                             "memory_truncated": False,
                             "trace_disabled_by_target": False}},
    ]
    return ("\n".join(json.dumps(f, separators=(",", ":")) for f in frames)
            + "\n").encode()


# ---------------- F-M7-02: argv pinning + tag mutation (deterministic) --------

def test_f_m7_02_python_argv_uses_resolved_id_not_tag(client, monkeypatch):
    """Inspect the ACTUAL docker argv handed to run_capped for a python run:
    image position must be the resolved sha256 ID, never the mutable tag, and
    the python trace run must have NO writable /out mount (F-M7-01)."""
    monkeypatch.setattr(analyzer_svc, "docker_status", lambda: (True, None))
    monkeypatch.setattr(analyzer_svc, "docker_available", lambda: True)
    monkeypatch.setattr(ex, "resolve_image_id", lambda tag: FAKE_ID_A)
    captured: list[tuple[list[str], int]] = []

    def fake_run_capped(argv, timeout, stdout_cap=ex.STDOUT_CAP):
        captured.append((list(argv), stdout_cap))
        return {"stdout": _frame_stream(), "stderr": b"",
                "stdout_truncated": False, "stderr_truncated": False,
                "killed": False, "exit_code": 0}

    monkeypatch.setattr(ex, "run_capped", fake_run_capped)
    snap, tgt = _paste(client, "python", "pin.py",
                       "def main():\n    return 7\nmain()\n")
    eid = _submit_run(client, snap, tgt)
    job = wait_exec(client, eid, tries=40)
    assert job["status"] == "COMPLETED", (job.get("status"), job.get("error_code"))
    assert captured, "python run never reached the container argv"
    argv, cap = captured[0]
    assert cap == ex.FRAMED_STDOUT_CAP
    assert FAKE_ID_A in argv, argv
    assert "compilevista/runtime:m4" not in argv, "mutable tag in launch argv"
    assert not any(a.endswith(":/out") or ":/out," in a + "," for a in argv), \
        "python trace container must not mount a writable /out"
    assert "-v" in argv and any(a.endswith(":/work:ro") for a in argv)
    rec = client.get(f"/api/v1/executions/{eid}").json()
    assert rec["image_id"] == FAKE_ID_A, "recorded provenance != launched image"
    assert rec["trace_trust"] == "UNTRUSTED_TARGET"
    assert rec["trace_channel"] == "framed_stdout_pipe_no_writable_mount"
    assert rec["trace_integrity"] == "CONSISTENT"


def test_f_m7_02_tag_mutation_fails_closed(client, monkeypatch):
    """If the tag no longer resolves to the identity recorded at submission,
    the job must BLOCK — never launch a different image silently."""
    monkeypatch.setattr(analyzer_svc, "docker_status", lambda: (True, None))
    monkeypatch.setattr(analyzer_svc, "docker_available", lambda: True)
    state = {"n": 0}

    def mutating_resolve(tag):
        state["n"] += 1
        return FAKE_ID_A if state["n"] == 1 else FAKE_ID_B

    monkeypatch.setattr(ex, "resolve_image_id", mutating_resolve)

    def fail_loud(argv, timeout, stdout_cap=ex.STDOUT_CAP):
        raise AssertionError("container launched after image identity changed")

    monkeypatch.setattr(ex, "run_capped", fail_loud)
    snap, tgt = _paste(client, "python", "mut.py", "x = 1\n")
    eid = _submit_run(client, snap, tgt)
    job = wait_exec(client, eid, tries=40)
    assert job["status"] == "BLOCKED", job["status"]
    assert job["error_code"] == "IMAGE_ID_CHANGED", job["error_code"]


def test_f_m7_02_unresolvable_image_fails_closed(client, monkeypatch):
    monkeypatch.setattr(analyzer_svc, "docker_status", lambda: (True, None))
    monkeypatch.setattr(analyzer_svc, "docker_available", lambda: True)
    monkeypatch.setattr(ex, "resolve_image_id", lambda tag: None)
    snap, tgt = _paste(client, "python", "noimg.py", "x = 1\n")
    eid = _submit_run(client, snap, tgt)
    job = wait_exec(client, eid, tries=40)
    assert job["status"] == "BLOCKED" and \
        job["error_code"] == "IMAGE_ID_UNAVAILABLE"


def test_f_m7_02_parse_framed_stream_suspect_verdicts():
    """Tampered / incomplete frame streams must be SUSPECT, never promoted."""
    good = _frame_stream()
    assert ex.parse_framed_stream(good)["integrity"] == "CONSISTENT"
    # 1: injected foreign line
    tampered = good.replace(b"\n", b"\nNOT-JSON-AT-ALL\n", 1)
    assert ex.parse_framed_stream(tampered)["integrity"] == "SUSPECT"
    # 2: forged trace frame inflating the count (meta no longer matches)
    forged = good.replace(b'"c":"m"', b'"c":"t"', 1)
    assert ex.parse_framed_stream(forged)["integrity"] == "SUSPECT"
    # 3: meta not last
    lines = good.splitlines()
    reordered = b"\n".join([lines[0], lines[-1], *lines[1:-1]]) + b"\n"
    assert ex.parse_framed_stream(reordered)["integrity"] == "SUSPECT"
    # 4: no meta at all
    assert ex.parse_framed_stream(
        b"\n".join(lines[:-1]) + b"\n")["integrity"] == "SUSPECT"


# ---------------- F-M7-01/04: real container runs ------------------------------

@pytest.mark.skipif(not _docker_ready(), reason="docker daemon unavailable")
def test_f_m7_01_python_trace_channel_trust_and_pinned_image(client):
    snap, tgt = _paste(client, "python", "hello.py",
                       "def main():\n    print('hello channel')\n    return 3\n"
                       "main()\n")
    eid = _submit_run(client, snap, tgt)
    job = wait_exec(client, eid, tries=90)
    assert job["status"] == "COMPLETED", (job.get("status"), job.get("error_code"))
    assert job["trace_trust"] == "UNTRUSTED_TARGET"
    assert job["trace_channel"] == "framed_stdout_pipe_no_writable_mount"
    assert job["trace_integrity"] == "CONSISTENT"
    assert job["image_id"] == _live_image_id("compilevista/runtime:m4"), \
        "recorded image id must equal the live pinned runtime image id"
    out = client.get(f"/api/v1/executions/{eid}/output").json()
    assert "hello channel" in (out["stdout"] or "")
    evs = client.get(f"/api/v1/executions/{eid}/events", params={"limit": 500}).json()
    kinds = {e["kind"] for e in evs["events"]}
    assert {"call", "line", "return"} <= kinds


@pytest.mark.skipif(not _docker_ready(), reason="docker daemon unavailable")
def test_f_m7_01_trace_disabled_by_target_is_flagged_not_hidden(client):
    """Non-hostile adversarial fixture: the target disables its own tracer.
    The run must complete but honestly record that observation integrity was
    compromised — never silently promoted to a verified trace."""
    src = ("import sys\n"
           "def main():\n"
           "    print('before disable')\n"
           "    sys.settrace(None)\n"
           "    print('after disable')\n")
    snap, tgt = _paste(client, "python", "untrace.py", src)
    eid = _submit_run(client, snap, tgt)
    job = wait_exec(client, eid, tries=90)
    assert job["status"] == "COMPLETED", (job.get("status"), job.get("error_code"))
    meta = json.loads(job["trace_meta_json"])
    assert meta["trace_disabled_by_target"] is True, meta
    assert job["trace_trust"] == "UNTRUSTED_TARGET"
    out = client.get(f"/api/v1/executions/{eid}/output").json()
    assert "before disable" in out["stdout"] and "after disable" in out["stdout"]


@pytest.mark.skipif(not _docker_ready(), reason="docker daemon unavailable")
def test_f_m7_01_forged_event_line_cannot_enter_trace(client):
    """Printing a frame-shaped line must land in the stdout capture, never in
    the recorded trace events."""
    forged = json.dumps({"c": "t", "j": {"kind": "call", "fn": "FORGED",
                                          "line": 1, "depth": 9}})
    src = (f"def main():\n"
           f"    print({forged!r})\n"
           f"    return 0\n")
    snap, tgt = _paste(client, "python", "forge.py", src)
    eid = _submit_run(client, snap, tgt)
    job = wait_exec(client, eid, tries=90)
    assert job["status"] == "COMPLETED", (job.get("status"), job.get("error_code"))
    assert job["trace_integrity"] == "CONSISTENT"
    out = client.get(f"/api/v1/executions/{eid}/output").json()
    assert "FORGED" in (out["stdout"] or "")
    evs = client.get(f"/api/v1/executions/{eid}/events", params={"limit": 500}).json()
    assert all(e["payload"].get("fn") != "FORGED" for e in evs["events"]), \
        "a printed line was promoted into the trace"


@pytest.mark.skipif(not _docker_ready(), reason="docker daemon unavailable")
def test_f_m7_01_python_container_has_no_writable_out(client):
    """The /out forgery channel is GONE: the path does not exist in the
    container, so artifact writes from the target fail."""
    src = ("def main():\n"
           "    try:\n"
           "        f = open('/out/trace.jsonl', 'a')\n"
           "        f.write('{\"kind\":\"forged\"}')\n"
           "        f.close()\n"
           "        print('WRITE SUCCEEDED - REGRESSION')\n"
           "    except OSError as e:\n"
           "        print('REFUSED', type(e).__name__)\n")
    snap, tgt = _paste(client, "python", "outwrite.py", src)
    eid = _submit_run(client, snap, tgt)
    job = wait_exec(client, eid, tries=90)
    assert job["status"] == "COMPLETED", (job.get("status"), job.get("error_code"))
    out = client.get(f"/api/v1/executions/{eid}/output").json()
    assert "REFUSED" in out["stdout"], out["stdout"]
    assert "WRITE SUCCEEDED" not in out["stdout"]


@pytest.mark.skipif(not _docker_ready(), reason="docker daemon unavailable")
def test_f_m7_04_preview_never_calls_user_len_or_repr(client):
    """A list subclass with a side-effecting __len__ and one whose __len__
    raises, plus a str subclass with a raising __repr__: the tracer's previews
    must not invoke any of them (the run completes and the counter stays 0)."""
    src = ("calls = []\n"
           "class Spy(list):\n"
           "    def __len__(self):\n"
           "        calls.append(1)\n"
           "        return 99\n"
           "class Boom(list):\n"
           "    def __len__(self):\n"
           "        raise RuntimeError('user len boom')\n"
           "class LoudStr(str):\n"
           "    def __repr__(self):\n"
           "        raise RuntimeError('user repr boom')\n"
           "s = Spy([1, 2, 3])\n"
           "b = Boom([1, 2])\n"
           "ls = LoudStr('x')\n"
           "def main():\n"
           "    a = s\n"
           "    bb = b\n"
           "    c = ls\n"
           "    plain = [1, 2]\n"
           "    return len(plain)\n"
           "print('user_len_calls', len(calls))\n")
    snap, tgt = _paste(client, "python", "spylen.py", src)
    eid = _submit_run(client, snap, tgt)
    job = wait_exec(client, eid, tries=90)
    assert job["status"] == "COMPLETED", (job.get("status"), job.get("error_code"))
    out = client.get(f"/api/v1/executions/{eid}/output").json()
    assert "user_len_calls 0" in out["stdout"], \
        "the tracer invoked a user-defined __len__"
    evs = client.get(f"/api/v1/executions/{eid}/events", params={"limit": 500}).json()
    assert any(e["kind"] == "call" and e["payload"].get("fn") == "main"
               for e in evs["events"]), "traced frames were lost"


@pytest.mark.skipif(not _docker_ready(), reason="docker daemon unavailable")
def test_f_m7_01_c_channel_trace_meta_and_pinned_images(client):
    """C path: shim's final trace_meta validates the file channel; BOTH the
    build (analyzer) and exec (runtime) image IDs are pinned and recorded."""
    src = ("int add(int a, int b) { return a + b; }\n"
           "int main(void) { return add(2, 3) - 5; }\n")
    snap, tgt = _paste(client, "c", "pin.c", src)
    eid = _submit_run(client, snap, tgt)
    job = wait_exec(client, eid, tries=120)
    assert job["status"] == "COMPLETED", (job.get("status"), job.get("error_code"))
    meta = json.loads(job["trace_meta_json"])
    assert meta.get("observer") == "c_trace_shim", meta
    assert job["trace_integrity"] == "CONSISTENT", meta
    assert job["trace_channel"] == "container_file"
    assert job["image_id"] == _live_image_id("compilevista/runtime:m4")
    assert job["build_image_id"] == _live_image_id("compilevista/analyzer:m2")
    assert job["exit_code"] == 0


# ---------------- F-M7-03: benchmark correctness (real containers) -----------

def _bench(client, snap, tgt, config):
    r = client.post("/api/v1/experiments", json={
        "kind": "bench", "snapshot_id": snap, "target_id": tgt,
        "config": config})
    assert r.status_code == 200, r.text[:200]
    xid = r.json()["experiment_id"]
    for _ in range(300):
        j = client.get(f"/api/v1/experiments/{xid}").json()
        if j["status"] in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BLOCKED"):
            return j
        time.sleep(0.5)
    return j


@pytest.mark.skipif(not _docker_ready(), reason="docker daemon unavailable")
def test_f_m7_03_bench_varying_stdout_flagged_not_equivalent(client):
    """THE permanent regression: a main() that prints a different line each
    repeat while returning None must NOT produce identical checksums."""
    src = ("counter = {'n': 0}\n"
           "def main():\n"
           "    counter['n'] += 1\n"
           "    print('run', counter['n'])\n"
           "    return None\n")
    snap, tgt = _paste(client, "python", "vary.py", src)
    j = _bench(client, snap, tgt, {"repeats": 5, "language": "python"})
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"))
    bench = next(s for s in j["stages"] if s["stage"] == "bench")["result"]
    rec = bench["levels"]["py312"]
    assert rec["checksums_identical"] is False, \
        "differing stdout per repeat produced identical checksums"
    assert len(set(rec["checksums"])) == 5
    assert rec["exception_repeats"] == []
    assert bench["levels_semantics_equivalent"] is not True


@pytest.mark.skipif(not _docker_ready(), reason="docker daemon unavailable")
def test_f_m7_03_bench_stable_stdout_and_return_identical(client):
    src = ("def main():\n"
           "    print('stable line')\n"
           "    return 41 + 1\n")
    snap, tgt = _paste(client, "python", "stable.py", src)
    j = _bench(client, snap, tgt, {"repeats": 5, "language": "python"})
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"))
    bench = next(s for s in j["stages"] if s["stage"] == "bench")["result"]
    rec = bench["levels"]["py312"]
    assert rec["checksums_identical"] is True
    assert set(rec["checksum_includes"]) == {"stdout", "return_repr_bounded",
                                              "exception"}
    assert bench["levels_semantics_equivalent"] is True


@pytest.mark.skipif(not _docker_ready(), reason="docker daemon unavailable")
def test_f_m7_03_bench_raising_main_recorded_as_data(client):
    """A main() that raises must change the checksum (exception/exit status),
    not abort the benchmark or masquerade as a clean None return."""
    src = ("def main():\n"
           "    raise ValueError('boom every time')\n")
    snap, tgt = _paste(client, "python", "raise.py", src)
    j = _bench(client, snap, tgt, {"repeats": 5, "language": "python"})
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"))
    bench = next(s for s in j["stages"] if s["stage"] == "bench")["result"]
    rec = bench["levels"]["py312"]
    assert rec["exception_repeats"] == ["ValueError"] * 5
    assert rec["checksums_identical"] is True  # consistently the SAME failure
    assert bench["levels_semantics_equivalent"] is True  # equivalent failures
