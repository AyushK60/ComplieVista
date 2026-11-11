"""Pasted-code execution check against the running stack (Stage 4 gate: restricted containers).

Pastes fresh programs through the same API the UI uses, runs them, and verifies stdout, exit code and
trace; then runs three defensive probes of the sandbox itself (network, filesystem write, runaway loop)
on the app's own containers. Exit code 0 only if every check holds.
Usage: python e2e/paste_exec_check.py   (stack running on :5173)
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

B = "http://127.0.0.1:5173/api/v1"
FAIL: list[str] = []


def call(path: str, body: dict | None = None) -> dict | list:
    req = urllib.request.Request(B + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"},
                                 method="POST" if body is not None else "GET")
    try:
        return json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} on {path}: {e.read().decode()[:300]}")


def ok(cond: bool, what: str) -> None:
    print(("  ok: " if cond else "  FAIL: ") + what)
    if not cond:
        FAIL.append(what)


def run(lang: str, fname: str, src: str, wait: int = 150):
    s = call("/sources", {"kind": "paste", "language": lang, "filename": fname, "content": src})
    tg = call(f"/projects/{s['project_id']}/targets")[0]
    ex = call("/executions", {"snapshot_id": s["snapshot_id"], "target_id": tg["target_id"]})
    eid = ex["execution_id"]
    t0 = time.time()
    for _ in range(wait):
        j = call(f"/executions/{eid}")
        if j["status"] not in ("QUEUED", "RUNNING"):
            break
        time.sleep(1)
    out = call(f"/executions/{eid}/output")
    return j, out, time.time() - t0


PY_OK = """def tri(n):
    return n * (n + 1) // 2


if __name__ == "__main__":
    print("tri", tri(10))
    print("sq", [x * x for x in range(5)])
"""
C_OK = """#include <stdio.h>

static int f(int n) { return n < 2 ? n : f(n - 1) + f(n - 2); }

int main(void) {
    printf("fib=%d\\n", f(12));
    return 3;
}
"""
PY_PROBE = """import socket

if __name__ == "__main__":
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=3)
        print("NET_OK")
    except Exception as e:
        print("NET_BLOCKED", type(e).__name__)
    try:
        open("/etc/cv_probe", "w").write("x")
        print("WRITE_OK")
    except Exception as e:
        print("WRITE_BLOCKED", type(e).__name__)
"""
PY_LOOP = """if __name__ == "__main__":
    while True:
        pass
"""


def main() -> None:
    print("[python paste]")
    j, out, dt = run("python", "fresh_a.py", PY_OK)
    ok(j["status"] == "COMPLETED" and j["exit_code"] == 0, f"status {j['status']} exit {j.get('exit_code')} in {dt:.0f}s")
    ok(out["stdout"] == "tri 55\nsq [0, 1, 4, 9, 16]\n", f"stdout correct: {out['stdout']!r}")
    ok((j.get("events_count") or 0) > 0, f"recorded trace has {j.get('events_count')} events")
    ok(j.get("trace_trust") == "UNTRUSTED_TARGET", f"pasted code is labelled untrusted ({j.get('trace_trust')})")

    print("[c paste]")
    j, out, dt = run("c", "fresh_b.c", C_OK)
    ok(j["status"] == "COMPLETED", f"status {j['status']} in {dt:.0f}s")
    ok(j["exit_code"] == 3, f"exit code preserved ({j.get('exit_code')})")
    ok(out["stdout"] == "fib=144\n", f"stdout correct: {out['stdout']!r}")

    print("[sandbox probes]")
    j, out, _ = run("python", "probe_net.py", PY_PROBE)
    so = out["stdout"] or ""
    ok("NET_OK" not in so and "NET_BLOCKED" in so, f"network is blocked ({so.splitlines()[:1]})")
    ok("WRITE_OK" not in so and "WRITE_BLOCKED" in so, f"writes outside the scratch area are blocked ({so.splitlines()[-1:]})")
    j, out, dt = run("python", "probe_loop.py", PY_LOOP, wait=170)
    ok(j["status"] in ("TIMEOUT", "FAILED", "CANCELLED"), f"runaway loop is stopped (status {j['status']} after {dt:.0f}s)")

    print("\nFAILURES: " + "; ".join(FAIL) if FAIL else "\nALL CHECKS PASSED")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
