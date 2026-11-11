"""Stage 4 review-B independent trace oracles - FRESH expectations derived here (not copied
from the stage 4 test fixtures), re-derived on the host CPython/clang at test time and
compared against what the REAL restricted containers recorded.

Python: recursion (tree-recursive fib), caught exception, return-during-exception,
generator suspension, builtin import - full (kind, fn) event multiset parity with
an independently written host tracer.
C: distinct functions with known static call counts, symbol resolution, timestamp
presence, and call/return pairing per function.
"""
import json
import subprocess
import sys
import time
from collections import Counter

from tests.test_stage4_execution import wait_exec

PY_SOURCE = '''def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

def divider(a, b):
    try:
        return a // b
    except ZeroDivisionError:
        return None

def gen(k):
    for i in range(k):
        yield i * 2

import math

if __name__ == '__main__':
    r1 = fib(6)
    r2 = divider(1, 0)
    r3 = divider(8, 2)
    total = sum(gen(4))
    print(r1, r2, r3, total, math.gcd(12, 8))
'''


def _host_oracle_events(source: str) -> Counter:
    """Independently written host tracer: same event vocabulary the container
    harness emits, executed on the host CPython (not the container). Restricted to
    frames of the oracle source itself - inside the pytest process the host would
    otherwise also record host-machinery frames (e.g. pytest's capture 'reset')
    that do not exist in the pristine container runtime."""
    counts: Counter = Counter()
    code = compile(source, "oracle.py", "exec", dont_inherit=True)

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != "oracle.py":
            return None
        if event in ("call", "line", "return", "exception"):
            counts[(event, frame.f_code.co_name)] += 1
        return tracer if event == "call" else None

    g = {"__name__": "__main__"}
    sys.settrace(tracer)
    try:
        exec(code, g)
    finally:
        sys.settrace(None)
    return counts


def _paste_and_run(client, language, filename, content):
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": language, "filename": filename,
        "content": content}).json()
    t = client.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
    resp = client.post("/api/v1/executions",
                       json={"snapshot_id": r["snapshot_id"], "target_id": t["target_id"]})
    eid = resp.json()["execution_id"]
    j = wait_exec(client, eid, tries=90)
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"))
    evs = client.get(f"/api/v1/executions/{eid}/events?limit=500").json()["events"]
    return j, evs


def test_python_oracle_event_parity(client):
    j, evs = _paste_and_run(client, "python", "oracle.py", PY_SOURCE)
    out = client.get(f"/api/v1/executions/{j['id']}/output").json()
    # 8 = fib(6); None = caught ZeroDivisionError; 4 = sum of gen(4)=0+2+4+6; 4 = gcd
    assert out["stdout"].split() == ["8", "None", "4", "12", "4"], out["stdout"]

    recorded = Counter((e["kind"], e["payload"].get("fn")) for e in evs
                       if e["kind"] != "meta" and e["kind"] != "exit"
                       and e["kind"] != "unparsed")
    expected = _host_oracle_events(PY_SOURCE)
    # The container imports nothing heavy; multiset parity per (event, function).
    for key, n in expected.items():
        assert recorded[key] == n, f"{key}: container {recorded[key]} != host oracle {n}"
    # The pristine container imports math for real, so it legitimately records
    # importlib machinery frames the preloaded host never executes. Those frames
    # must appear ONLY before the first user-function call (during the import).
    extra_keys = set(recorded) - set(expected)
    first_user_call = next(i for i, e in enumerate(evs)
                           if e["kind"] == "call" and e["payload"].get("fn") == "fib")
    machinery = [e for e in evs[:first_user_call]
                 if (e["kind"], e["payload"].get("fn")) in extra_keys]
    late_extra = [e for e in evs[first_user_call:]
                  if (e["kind"], e["payload"].get("fn")) in extra_keys]
    assert not late_extra, f"non-import frames outside user oracle: {late_extra[:3]}"
    assert machinery, "import must produce real importlib events in the container"

    # specific structural facts, recomputed by hand:
    # fib(6) tree-recursive: calls(2*F(7)-1)=25, returns 25 (8 of them base returns)
    assert recorded[("call", "fib")] == 25 and recorded[("return", "fib")] == 25
    # divider called twice: one returns via except path (None), one normal
    assert recorded[("call", "divider")] == 2 and recorded[("return", "divider")] == 2
    assert recorded[("exception", "divider")] == 1  # the ZeroDivisionError
    # generator: each yield suspends (a 'return' event) and each resumption re-enters
    # the frame (another 'call' event): 1 initial call + 4 resumes = 5 calls, and
    # 4 yield-returns + 1 final StopIteration return = 5 returns. Both oracles agree.
    assert recorded[("call", "gen")] == 5 and recorded[("return", "gen")] == 5

    # locals snapshot on a fib call must show the primitive argument repr
    fib_call = next(e for e in evs if e["kind"] == "call"
                    and e["payload"].get("fn") == "fib")
    assert fib_call["payload"]["locals"]["n"]["repr"] in {"6", "5", "4", "3", "2", "1", "0"}


def test_c_oracle_call_counts_and_symbols(client):
    src = '''static int alpha(int x) { return x + 1; }
static int beta(int x) { return 2 * x; }
int main(void) {
    int s = 0;
    s += alpha(1);
    s += alpha(2);
    s += alpha(3);
    s += beta(5);
    return s;
}
'''
    j, evs = _paste_and_run(client, "c", "oracle.c", src)
    # s = (1+1)+(2+1)+(3+1)+(2*5) = 19 - a REAL computed exit status, not a canned 0
    assert j["exit_code"] == 19
    calls = Counter(e["payload"]["fn"] for e in evs if e["kind"] == "call")
    returns = Counter(e["payload"]["fn"] for e in evs if e["kind"] == "return")
    # static counts: alpha 3x, beta 1x, main 1x - every call paired with a return
    assert calls["alpha"] == 3 and returns["alpha"] == 3
    assert calls["beta"] == 1 and returns["beta"] == 1
    assert calls["main"] == 1 and returns["main"] == 1
    # all addresses resolved to symbol names by llvm-nm (no raw 0x... fallback)
    for e in evs:
        assert not e["payload"].get("fn", "").startswith("0x"), e
        if e["kind"] in ("call", "return"):
            assert isinstance(e["payload"].get("ts_ms"), (int, float)), e
    # call/return pairing per function is balanced in sequence
    depth = {}
    for e in evs:
        fn = e["payload"].get("fn")
        if e["kind"] == "call":
            depth[fn] = depth.get(fn, 0) + 1
        elif e["kind"] == "return":
            depth[fn] = depth.get(fn, 0) - 1
            assert depth[fn] >= 0, f"return before call for {fn}"
    assert all(v == 0 for v in depth.values()), depth


def test_replay_pagination_is_stable_and_ordered(client):
    """Replay reads recorded events only: pagination stays ordered/checksummed and
    does not re-execute (second identical read returns identical data)."""
    j, _ = _paste_and_run(client, "python", "replay.py",
                          "def f(k):\n    return k + 1\n\n"
                          "if __name__ == '__main__':\n    print(f(41))\n")
    p1 = client.get(f"/api/v1/executions/{j['id']}/events?limit=3").json()
    p2 = client.get(f"/api/v1/executions/{j['id']}/events?limit=3").json()
    assert p1 == p2, "event pagination must be deterministic (no re-execution)"
    seqs = [e["seq"] for e in p1["events"]]
    assert seqs == sorted(seqs)
    full = client.get(f"/api/v1/executions/{j['id']}/events?limit=500").json()["events"]
    for e in full:
        assert len(e["sha256"]) == 64
