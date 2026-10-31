#!/usr/bin/env python3
"""M4-D Python trace harness — runs INSIDE the pinned restricted runtime container.

Executes the target ONCE under sys.settrace, capturing genuine call/line/return/
exception events with bounded, safe variable snapshots. Never calls user __repr__;
non-primitive values are summarized by type/identity. Caps: 5000 events, 64 frames
deep, 200 locals/frame, 120 bytes/string, 1 MB stdout (M4QA-02: the stdout file on
the bind mount is size-capped at the source; excess is drained and discarded, so a
flood cannot grow the host-side file without bound).
Writes /out/trace.jsonl, stdout.txt (capped), exit status via process code.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback

MAX_EVENTS = 5000
MAX_DEPTH = 64
MAX_LOCALS = 200
MAX_STR = 120
STDOUT_CAP = 1024 * 1024

out_dir = sys.argv[sys.argv.index("--out") + 1]
target = os.path.join("/work", sys.argv[sys.argv.index("--file") + 1])
events = 0
truncated = False
stdout_truncated = False


def safe_value(v):
    if isinstance(v, (int, float, bool, type(None))):
        return {"type": type(v).__name__, "repr": repr(v)[:MAX_STR]}
    if isinstance(v, str):
        return {"type": "str", "repr": repr(v)[:MAX_STR],
                "truncated": len(v) > MAX_STR}
    if isinstance(v, (bytes, bytearray)):
        return {"type": type(v).__name__, "len": len(v)}
    if isinstance(v, (list, tuple, set, frozenset, dict)):
        return {"type": type(v).__name__, "len": len(v)}
    # Never call user __repr__ (M4-D): identity summary only.
    return {"type": type(v).__module__ + "." + type(v).__qualname__, "identity": id(v) % 10**8}


def safe_locals(frame):
    out = {}
    for i, (k, v) in enumerate(frame.f_locals.items()):
        if i >= MAX_LOCALS:
            out["__elided__"] = True
            break
        try:
            out[k] = safe_value(v)
        except Exception:
            out[k] = {"type": "unknown"}
    return out


def emit(rec):
    global events, truncated
    if events >= MAX_EVENTS:
        truncated = True
        return
    events += 1
    trace_f.write(json.dumps(rec) + "\n")


trace_path = os.path.join(out_dir, "trace.jsonl")
trace_f = open(trace_path, "w")

t0 = time.monotonic()


def tracer(frame, event, arg):
    # Only trace frames BELOW the harness (user code).
    depth = 0
    f = frame
    while f is not None:
        depth += 1
        f = f.f_back
    if depth > MAX_DEPTH:
        return None
    if event == "call":
        emit({"kind": "call", "fn": frame.f_code.co_name, "line": frame.f_lineno,
              "depth": depth, "locals": safe_locals(frame)})
        return tracer
    if event == "line":
        emit({"kind": "line", "fn": frame.f_code.co_name, "line": frame.f_lineno,
              "depth": depth})
        return tracer
    if event == "return":
        emit({"kind": "return", "fn": frame.f_code.co_name, "line": frame.f_lineno,
              "depth": depth, "arg": safe_value(arg)})
        return tracer
    if event == "exception":
        exc = arg[0] if isinstance(arg, tuple) else None
        emit({"kind": "exception", "fn": frame.f_code.co_name, "line": frame.f_lineno,
              "depth": depth,
              "exc": type(exc).__name__ if exc else None,
              "msg": str(exc)[:MAX_STR] if exc else None})
        return tracer
    return None


code = compile(open(target, "rb").read(), os.path.basename(target), "exec",
               dont_inherit=True)
g = {"__name__": "__main__", "__file__": target}
exit_code = 0
stdout_path = os.path.join(out_dir, "stdout.txt")
# fd-level redirect (captures C-level and Python-level stdout) through a draining
# pump thread that stops persisting after STDOUT_CAP bytes but keeps consuming, so
# the writer never blocks and the bind-mount file stays bounded (M4QA-02).
saved_fd = os.dup(1)
pipe_r, pipe_w = os.pipe()
out_f = open(stdout_path, "wb")


def _pump() -> None:
    global stdout_truncated
    kept = 0
    while True:
        try:
            chunk = os.read(pipe_r, 65536)
        except OSError:
            break
        if not chunk:
            break
        if kept < STDOUT_CAP:
            keep = chunk[: STDOUT_CAP - kept]
            out_f.write(keep)
            kept += len(keep)
        else:
            stdout_truncated = True


pump = threading.Thread(target=_pump, daemon=True)
pump.start()
os.dup2(pipe_w, 1)
os.close(pipe_w)
try:
    sys.settrace(tracer)
    exec(code, g)  # M4-D: genuine in-container execution, bounded by harness
    sys.settrace(None)
except BaseException as e:
    exit_code = 1
    emit({"kind": "termination", "exc": type(e).__name__, "msg": str(e)[:MAX_STR]})
    traceback.print_exc(file=sys.stderr)
finally:
    sys.settrace(None)
    sys.stdout.flush()
    sys.stderr.flush()
    os.dup2(saved_fd, 1)
    os.close(saved_fd)
    os.close(pipe_r)  # writer is gone; pump drains whatever remains and exits
    pump.join(timeout=5)
    out_f.close()

emit({"kind": "exit", "exit_code": exit_code,
      "duration_ms": int((time.monotonic() - t0) * 1000)})
trace_f.write(json.dumps({"kind": "meta", "python": sys.version.split()[0],
                          "events": events, "truncated": truncated,
                          "stdout_truncated": stdout_truncated,
                          "max_events": MAX_EVENTS}) + "\n")
trace_f.close()
sys.exit(exit_code)
