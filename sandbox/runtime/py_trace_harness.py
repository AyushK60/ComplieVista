#!/usr/bin/env python3
"""M4-D/M5 Python trace harness — runs INSIDE the pinned restricted runtime container.

Executes the target ONCE under sys.settrace, capturing genuine call/line/return/
exception events with bounded, safe variable snapshots. Never calls user __repr__;
non-primitive values are summarized by type/identity. Caps: 5000 events, 64 frames
deep, 200 locals/frame, 120 bytes/string, 1 MB stdout (M4QA-02), 3000 memory
records, 240 process samples, 60-node object graph (M5).

M5 additions (all OBSERVED inside this run; nothing inferred or fabricated):
- memory.jsonl: per-call frame snapshots with stable in-run frame ids and
  id()-based object identity (aliasing grounded in observed identity), a bounded
  object-reference graph, tracemalloc snapshot statistics, gc activity.
- process.jsonl: container-side process evidence — pid namespace identity,
  /proc RSS/VM/thread/fd samples at a stated interval, observed child pids.
Value previews use name-based secret redaction and never execute user code.
Writes /out/trace.jsonl, stdout.txt (capped), memory.jsonl, process.jsonl.
"""
from __future__ import annotations

import gc
import json
import os
import sys
import threading
import time
import tracemalloc
import traceback

MAX_EVENTS = 5000
MAX_DEPTH = 64
MAX_LOCALS = 200
MAX_STR = 120
STDOUT_CAP = 1024 * 1024
MEMORY_RECORDS_CAP = 3000
PROC_SAMPLES_CAP = 240
PROC_SAMPLE_INTERVAL_S = 0.05
GRAPH_NODES_CAP = 60
GRAPH_EDGES_CAP = 120
GRAPH_DEPTH = 2
# Name-based secret redaction rule (M5-E): values bound to secret-ish names are
# never previewed; this is a documented heuristic, not content inspection.
SECRET_NAME_PARTS = ("pass", "secret", "token", "key", "pwd", "credential")

out_dir = sys.argv[sys.argv.index("--out") + 1]
target = os.path.join("/work", sys.argv[sys.argv.index("--file") + 1])
events = 0
truncated = False
stdout_truncated = False
mem_records = 0
mem_truncated = False

_SECRET_FLAGS = tuple(part.encode() for part in SECRET_NAME_PARTS)


def _is_secret_name(name: str) -> bool:
    low = name.lower().encode()
    return any(part in low for part in _SECRET_FLAGS)


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


trace_path = os.path.join(out_dir, "trace.jsonl")
trace_f = open(trace_path, "w")
mem_path = os.path.join(out_dir, "memory.jsonl")
mem_f = open(mem_path, "w")

frame_ids: dict[int, int] = {}
next_frame_id = 0


def frame_id_for(frame) -> int:
    global next_frame_id
    key = id(frame)
    if key not in frame_ids:
        next_frame_id += 1
        frame_ids[key] = next_frame_id
    return frame_ids[key]


def mem_emit(rec) -> None:
    global mem_records, mem_truncated
    if mem_records >= MEMORY_RECORDS_CAP:
        mem_truncated = True
        return
    mem_records += 1
    mem_f.write(json.dumps(rec) + "\n")


def emit(rec):
    global events, truncated
    if events >= MAX_EVENTS:
        truncated = True
        return
    events += 1
    trace_f.write(json.dumps(rec) + "\n")


def emit_frame_snapshot(frame, event_seq: int) -> None:
    fid = frame_id_for(frame)
    locals_out = []
    alias_names: dict[int, list[str]] = {}
    for i, (k, v) in enumerate(frame.f_locals.items()):
        if i >= MAX_LOCALS:
            break
        if isinstance(v, (int, float, bool, type(None), str, bytes, bytearray)):
            entry = {"name": k, "kind": "primitive" if not isinstance(
                v, (str, bytes, bytearray)) else type(v).__name__,
                "preview": safe_value(v)}
            if _is_secret_name(k):
                entry["preview"] = {"type": "redacted", "repr": "«redacted:name-rule»"}
                entry["redacted"] = True
            locals_out.append(entry)
            continue
        oid = id(v) % 10**8
        # len() only on builtins we know are safe: arbitrary objects/classes may
        # define __len__ that raises or misbehaves (observed: classes in the
        # import machinery during heavy imports).
        entry = {"name": k, "kind": "object", "type": type(v).__name__,
                 "obj_id": oid,
                 "len": len(v) if isinstance(v, (list, tuple, dict, set,
                                                 frozenset, str, bytes,
                                                 bytearray)) else None}
        if _is_secret_name(k):
            entry["redacted"] = True
        locals_out.append(entry)
        alias_names.setdefault(oid, []).append(k)
    mem_emit({"kind": "frame_snapshot", "event_seq": event_seq, "frame_id": fid,
              "fn": frame.f_code.co_name, "line": frame.f_lineno, "locals": locals_out})
    # Alias links: two names bound to the same object identity in this snapshot.
    emitted_alias = 0
    for oid, names in alias_names.items():
        if len(names) > 1 and emitted_alias < 8:
            emitted_alias += 1
            mem_emit({"kind": "alias", "event_seq": event_seq, "frame_id": fid,
                      "names": names, "obj_id": oid})


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
        emit_frame_snapshot(frame, events)  # seq of the call event just written
        return tracer
    if event == "line":
        emit({"kind": "line", "fn": frame.f_code.co_name, "line": frame.f_lineno,
              "depth": depth})
        return tracer
    if event == "return":
        emit({"kind": "return", "fn": frame.f_code.co_name, "line": frame.f_lineno,
              "depth": depth, "arg": safe_value(arg)})
        emit_frame_snapshot(frame, events)  # exit-time locals: aliasing/lifetime here
        frame_ids.pop(id(frame), None)  # frame lifetime ends here (observed)
        return tracer
    if event == "exception":
        exc = arg[0] if isinstance(arg, tuple) else None
        emit({"kind": "exception", "fn": frame.f_code.co_name, "line": frame.f_lineno,
              "depth": depth,
              "exc": type(exc).__name__ if exc else None,
              "msg": str(exc)[:MAX_STR] if exc else None})
        return tracer
    return None


# ---------------- process sampler (container-side, M5-D) ----------------
proc_path = os.path.join(out_dir, "process.jsonl")
proc_f = open(proc_path, "w")
proc_samples = 0
proc_truncated = False


def proc_emit(rec) -> None:
    global proc_samples, proc_truncated
    if rec.get("kind") == "proc_sample":
        if proc_samples >= PROC_SAMPLES_CAP:
            proc_truncated = True
            return
        proc_samples += 1
    proc_f.write(json.dumps(rec) + "\n")


def read_status_fields() -> dict | None:
    try:
        fields = {}
        with open("/proc/self/status", "rb") as f:
            for line in f:
                for key in (b"VmRSS:", b"VmSize:", b"Threads:"):
                    if line.startswith(key):
                        fields[key.decode().rstrip(":")] = \
                            line.split()[1].decode()
        return fields or None
    except OSError:
        return None


def count_fds() -> int:
    try:
        return len(os.listdir("/proc/self/fd"))
    except OSError:
        return -1


def observed_children() -> list[int]:
    me = os.getpid()
    out: list[int] = []
    try:
        for entry in os.listdir("/proc"):
            if not entry.isdigit() or int(entry) == me:
                continue
            try:
                with open(f"/proc/{entry}/stat", "rb") as pf:
                    fields = pf.read().split()
                if int(fields[3]) == me:
                    out.append(int(entry))
            except (OSError, IndexError, ValueError):
                continue
    except OSError:
        pass
    return out[:32]


def sampler_loop() -> None:
    n = 0
    while not sampler_stop.is_set():
        t_ms = int((time.monotonic() - t0) * 1000)
        fields = read_status_fields()
        proc_emit({"kind": "proc_sample", "t_ms": t_ms,
                   "rss_kb": int(fields.get("VmRSS", -1)) if fields else None,
                   "vm_size_kb": int(fields.get("VmSize", -1)) if fields else None,
                   "threads": int(fields.get("Threads", -1)) if fields else None,
                   "fds": count_fds()})
        if n % 2 == 0:  # frequent child-process observation while they are alive
            kids = observed_children()
            if kids:
                proc_emit({"kind": "proc_children", "t_ms": t_ms, "pids": kids,
                           "observed": "during run"})
        n += 1
        sampler_stop.wait(PROC_SAMPLE_INTERVAL_S)


sampler_stop = threading.Event()
sampler = threading.Thread(target=sampler_loop, daemon=True)
proc_emit({"kind": "proc_meta",
           "os": "Linux (container pid namespace)",
           "kernel": open("/proc/sys/kernel/osrelease").read().strip()[:80],
           "container_pid": os.getpid(),
           "ppid": os.getppid(),
           "python": sys.version.split()[0],
           "sample_interval_ms": int(PROC_SAMPLE_INTERVAL_S * 1000),
           "sample_cap": PROC_SAMPLES_CAP,
           "metric_definitions": {
               "rss_kb": "VmRSS from /proc/self/status (resident set, kB)",
               "vm_size_kb": "VmSize from /proc/self/status (kB)",
               "threads": "Threads from /proc/self/status",
               "fds": "count of /proc/self/fd entries",
               "t_ms": "ms since harness start (monotonic, in-run)"}})

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

tracemalloc.start()
sampler.start()
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
    sampler_stop.set()
    sampler.join(timeout=2)

    # ---- M5 memory evidence (observed, bounded) ----
    current_b, peak_b = tracemalloc.get_traced_memory()
    snap = tracemalloc.take_snapshot()
    top = []
    for stat in snap.statistics("lineno")[:10]:
        top.append({"file": (stat.traceback[0].filename or "?")[-60:],
                    "line": stat.traceback[0].lineno,
                    "size_bytes": stat.size, "count": stat.count})
    mem_emit({"kind": "tracemalloc",
              "traced_current_bytes": current_b, "traced_peak_bytes": peak_b,
              "top": top,
              "caveat": "tracemalloc traces only allocations made while tracing "
                        "was active; totals exclude interpreter baseline and "
                        "pre-existing allocations"})
    gc_before = gc.get_stats()
    collected = gc.collect()  # instrumented effect: forced collection, documented
    gc_after = gc.get_stats()
    mem_emit({"kind": "gc",
              "counts_before": [g0.get("collections", 0) for g0 in gc_before],
              "counts_after": [g0.get("collections", 0) for g0 in gc_after],
              "collected_by_forced_collect": collected,
              "caveat": "forced collection at harness exit is an instrumented "
                        "effect; it does not describe the program's own GC pacing"})
    # Bounded object-reference graph from surviving module globals.
    nodes: dict[int, dict] = {}
    edges: list = []

    def add_node(v) -> int | None:
        if len(nodes) >= GRAPH_NODES_CAP:
            return None
        oid = id(v) % 10**8
        if oid not in nodes:
            nodes[oid] = {"obj_id": oid, "type": type(v).__name__,
                          "preview": safe_value(v), "len":
                          len(v) if isinstance(v, (list, tuple, dict, set,
                                                   frozenset, str, bytes,
                                                   bytearray)) else None}
        return oid

    def walk(v, depth: int) -> None:
        if depth > GRAPH_DEPTH or len(edges) >= GRAPH_EDGES_CAP:
            return
        src = add_node(v)
        if src is None:
            return
        try:
            refs = gc.get_referents(v)
        except Exception:
            return
        for r in refs[:12]:
            if r is None or isinstance(r, (str, int, float, bool, type(None),
                                           type, type(sys))):
                continue
            dst = add_node(r)
            if dst is None or len(edges) >= GRAPH_EDGES_CAP:
                return
            edges.append({"src": src, "dst": dst})
            walk(r, depth + 1)

    for gv in list(g.values())[:24]:
        if isinstance(gv, (str, int, float, bool, type(None), type(sys))):
            continue
        walk(gv, 0)
    mem_emit({"kind": "object_graph", "nodes": list(nodes.values()),
              "edges": edges,
              "caps": {"nodes": GRAPH_NODES_CAP, "edges": GRAPH_EDGES_CAP,
                       "depth": GRAPH_DEPTH},
              "caveat": "bounded reachable subgraph from module globals at exit; "
                        "not full-heap coverage"})
    # Observed child processes (container pid namespace) at exit.
    proc_emit({"kind": "proc_children", "pids": observed_children(),
               "observed": "at exit"})
    proc_emit({"kind": "proc_exit", "exit_code": exit_code,
               "duration_ms": int((time.monotonic() - t0) * 1000),
               "samples": proc_samples, "samples_truncated": proc_truncated})
    mem_f.close()
    proc_f.close()

emit({"kind": "exit", "exit_code": exit_code,
      "duration_ms": int((time.monotonic() - t0) * 1000)})
trace_f.write(json.dumps({
    "kind": "meta", "python": sys.version.split()[0], "events": events,
    "truncated": truncated, "stdout_truncated": stdout_truncated,
    "max_events": MAX_EVENTS, "schema": "m5",
    "memory_records": mem_records, "memory_truncated": mem_truncated}) + "\n")
trace_f.close()
sys.exit(exit_code)
