#!/usr/bin/env python3
"""M5-B curated C debug worker — runs INSIDE the pinned debug image (clang-18 + gdb).

Curated allowlisted fixtures ONLY (never pasted code — gdb parses untrusted
DWARF/ELF, which is attack surface; ADR-0008). Compiles the target exactly like the
standard build worker, then runs it under `gdb -batch` with breakpoint commands
derived from the curated manifest: at every stop it records `info args`,
`info locals` and the manifest-declared inspect expressions VERBATIM as gdb printed
them (tool-formatted text, observation_class=observed, tool=gdb).

Real addresses are recorded as observed in this run; they are NOT stable across
runs (ASLR) and this caveat is attached to every record.

Outputs into /out (merged memory stream): memory.jsonl gains {"kind":"debug_stop"}
records in stop order; the allocator interposer in the shim writes alloc/free
records into the same file; trace.jsonl gets the usual instrumented call/return
stream (capped 5000); process.jsonl from the shim sampler.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess

CLANG = "clang-18"
SHIM = "/opt/debug/c_trace_shim.c"
MAX_STOPS = 200


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--bp", required=True, help="JSON: [{fn, inspect?: [expr]}]")
    args = ap.parse_args()
    out = args.out
    src = os.path.join("/work", args.file)
    bps = json.loads(args.bp)
    if not isinstance(bps, list) or not bps or len(bps) > 8:
        raise SystemExit("invalid breakpoint manifest")
    for bp in bps:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", bp["fn"]):
            raise SystemExit("invalid breakpoint function name")
        if "line" in bp and (not isinstance(bp["line"], int)
                             or not 1 <= bp["line"] <= 100000):
            raise SystemExit("invalid breakpoint line")
        for expr in bp.get("inspect", []):
            if len(expr) > 60 or not re.fullmatch(r"[&*A-Za-z0-9_\[\]\. ]{1,60}", expr):
                raise SystemExit(f"invalid inspect expression: {expr!r}")

    # Build WITHOUT -finstrument-functions: the entry hook shifts gdb's breakpoint
    # location ahead of argument setup (garbage args observed). gdb stops replace
    # the call/return stream; the shim still provides malloc interposition + /proc
    # sampling.
    comp = subprocess.run(
        [CLANG, "-g", "-O0", "-no-pie", "-c", "-o",
         os.path.join(out, "user.o"), src], capture_output=True, timeout=90)
    shim = subprocess.run(
        [CLANG, "-g", "-O0", "-c", "-o", os.path.join(out, "shim.o"), SHIM],
        capture_output=True, timeout=90)
    link = subprocess.run(
        [CLANG, "-no-pie", "-g", "-o", os.path.join(out, "app"),
         os.path.join(out, "user.o"), os.path.join(out, "shim.o")],
        capture_output=True, timeout=90)
    if max(comp.returncode, shim.returncode, link.returncode) != 0:
        err = (comp.stderr + shim.stderr + link.stderr).decode("utf-8", "replace")
        with open(os.path.join(out, "debug.jsonl"), "w") as f:
            f.write(json.dumps({"kind": "debug_error", "stage": "build",
                                "stderr": err[-400:]}) + "\n")
        return

    # gdb command FILE: -ex cannot carry `commands` bodies (separate -ex args run
    # immediately; embedded newlines are not split), so the sequence goes into a
    # script file read line-by-line by -x. Content derives from the curated
    # manifest only (fn names and inspect expressions validated above).
    script_lines = ["set pagination off", "set confirm off"]
    for bp in bps:
        loc = f"{src}:{bp['line']}" if "line" in bp else bp["fn"]
        script_lines.append(f"break {loc}")
        script_lines.append("commands")
        script_lines.append('printf "===M5STOP stop\\n"')
        script_lines.append("echo ===M5ARGS===\\n")
        script_lines.append("info args")
        script_lines.append("echo ===M5LOCALS===\\n")
        script_lines.append("info locals")
        for expr in bp.get("inspect", []):
            script_lines.append(f"echo ===M5EXPR {expr}===\\n")
            script_lines.append(f"print {expr}")
        script_lines.append("continue")
        script_lines.append("end")
    script_lines.append("run")
    script_path = os.path.join(out, "gdb_script.txt")
    with open(script_path, "w") as f:
        f.write("\n".join(script_lines) + "\n")

    gdb_argv = ["gdb", "-batch", "-nx", "-x", script_path, os.path.join(out, "app")]
    env = dict(os.environ)
    env["CV_MEM_OUT"] = os.path.join(out, "memory.jsonl")
    env["CV_PROC_OUT"] = os.path.join(out, "process.jsonl")
    env.pop("CV_TRACE_OUT", None)  # instrumented call/return duplicated by gdb stops
    r = subprocess.run(gdb_argv, capture_output=True, timeout=90, env=env)

    stops: list[dict] = []
    pending_fn = None
    pending_block: list[str] = []
    pending_inspect: list[str] = []
    section = None
    current_expr = None
    hit_re = re.compile(r"Breakpoint \d+,\s*([A-Za-z_][A-Za-z0-9_]*) \(")

    def flush() -> None:
        nonlocal pending_block, pending_inspect, pending_fn, section, current_expr
        if pending_fn is None:
            return
        if len(stops) < MAX_STOPS:
            stops.append({"kind": "debug_stop", "fn": pending_fn,
                          "gdb_text": [l for l in pending_block if l.strip()][:24],
                          "inspect_raw": pending_inspect[:8],
                          "tool": "gdb",
                          "observation_class": "observed",
                          "caveat": "addresses are as observed in this run; ASLR "
                                    "makes them unstable across runs; presence of "
                                    "the debugger may alter timing (Heisenberg)"})
        pending_block = []
        pending_inspect = []
        pending_fn = None
        section = None
        current_expr = None

    text = r.stdout.decode("utf-8", "replace").splitlines()
    for raw_line in text:
        line = raw_line.lstrip(">")  # gdb echoes command-list lines with '> '
        if "===M5STOP" in line:
            continue  # marker only bounds output; the Breakpoint line opens a stop
        if line.startswith("===M5ARGS==="):
            section = "args"
            continue
        if line.startswith("===M5LOCALS==="):
            section = "locals"
            continue
        if line.startswith("===M5EXPR "):
            section = "expr"
            current_expr = line[len("===M5EXPR "):].rstrip("= ").strip()
            continue
        m = hit_re.search(line)
        if m:
            # a new stop begins: flush the previous one (fn known at hit line)
            flush()
            pending_fn = m.group(1)
            continue
        if pending_fn is None:
            continue
        if section == "expr" and line.startswith("$") and current_expr:
            pending_inspect.append(f"{current_expr} = "
                                   + line.split("=", 1)[-1].strip())
            continue
        if line.startswith("$"):
            continue  # print output without a managed marker: ignore
        pending_block.append(line)
    flush()
    if len(stops) >= MAX_STOPS:
        stops.append({"kind": "meta", "truncated": True, "max_stops": MAX_STOPS})

    with open(os.path.join(out, "memory.jsonl"), "a") as f:
        for rec in stops:
            f.write(json.dumps(rec) + "\n")
    with open(os.path.join(out, "debug.jsonl"), "w") as f:
        f.write(json.dumps({"kind": "debug_meta", "tool": "gdb",
                            "gdb_output_tail": r.stdout.decode("utf-8", "replace")[-4000:],
                            "gdb_returncode": r.returncode,
                            "stops": len(stops)}) + "\n")


if __name__ == "__main__":
    main()
