#!/usr/bin/env python3
"""M4-D Python trace harness — runs INSIDE the pinned restricted runtime container.

Executes the target ONCE under sys.settrace, capturing genuine call/line/return/
exception events with bounded, safe variable snapshots. Never calls user __repr__;
non-primitive values are summarized by type/identity. Caps: 5000 events, 64 frames
deep, 200 locals/frame, 120 bytes/string. Writes /out/trace.jsonl, stdout.txt, exit.json.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import traceback

MAX_EVENTS = 5000
MAX_DEPTH = 64
MAX_LOCALS = 200
MAX_STR = 120

out_dir = sys.argv[sys.argv.index("--out") + 1]
target = os.path.join("/work", sys.argv[sys.argv.index("--file") + 1])
events = 0
truncated = False


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
# fd-level redirect: captures C-level and Python-level stdout reliably
saved_fd = os.dup(1)
out_f = open(stdout_path, "wb")
os.dup2(out_f.fileno(), 1)
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
    os.dup2(saved_fd, 1)
    os.close(saved_fd)
    out_f.close()

emit({"kind": "exit", "exit_code": exit_code,
      "duration_ms": int((time.monotonic() - t0) * 1000)})
trace_f.write(json.dumps({"kind": "meta", "python": sys.version.split()[0],
                          "events": events, "truncated": truncated,
                          "max_events": MAX_EVENTS}) + "\n")
trace_f.close()
sys.exit(exit_code)
