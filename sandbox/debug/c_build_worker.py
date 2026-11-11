#!/usr/bin/env python3
"""Stage 4-C C build worker - runs INSIDE the pinned analyzer container.

Compiles the staged single-file target with pinned allowlisted flags:
  clang-18 -g -O0 -finstrument-functions (user code)
  + c_trace_shim.c compiled -fno-instrument-functions
Emits the executable, symbols.txt (nm -S for address→function resolution) and a
build manifest. No user-supplied flags exist on this path.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess

CLANG = "clang-18"
NM = "llvm-nm-18"

manifest: dict = {"worker": "c_build_worker.py", "stages": [], "tool_versions": {}}


def save(out: str, name: str, data: bytes, cap: int = 8 * 1024 * 1024) -> dict:
    with open(os.path.join(out, name), "wb") as f:
        f.write(data[:cap])
    import hashlib
    return {"file": name, "sha256": hashlib.sha256(data[:cap]).hexdigest(),
            "bytes": min(len(data), cap), "truncated": len(data) > cap}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    src = os.path.join("/work", args.file)
    out = args.out
    exe = os.path.join(out, "app")
    shim_src = os.path.join(out, "c_trace_shim.c")

    v = subprocess.run([CLANG, "--version"], capture_output=True, timeout=30).stdout
    manifest["tool_versions"]["clang"] = v.decode("utf-8", "replace").splitlines()[0]

    with open(shim_src, "wb") as f:
        f.write(open("/opt/analyzer/c_trace_shim.c", "rb").read())

    rec: dict = {"stage": "build", "argv_tail": [
        CLANG, "-g", "-O0", "-finstrument-functions", "-o", "app", args.file,
        "c_trace_shim.c"]}
    t0 = os.times()
    # THREE steps: user code instrumented; shim NOT (else the hooks instrument
    # themselves -> infinite recursion -> SIGSEGV); then link.
    compile_user = subprocess.run(
        [CLANG, "-g", "-O0", "-no-pie", "-finstrument-functions", "-c", "-o",
         os.path.join(out, "user.o"), src], capture_output=True, timeout=90)
    compile_shim = subprocess.run(
        [CLANG, "-g", "-O0", "-c", "-o",
         os.path.join(out, "shim.o"), shim_src],
        capture_output=True, timeout=90)  # default: NOT instrumented
    link = subprocess.run(
        [CLANG, "-no-pie", "-o", exe, os.path.join(out, "user.o"), os.path.join(out, "shim.o")],
        capture_output=True, timeout=90)
    class _BuildResult:
        returncode = max(compile_user.returncode, compile_shim.returncode,
                         link.returncode)
        stdout = compile_user.stdout + compile_shim.stdout + link.stdout
        stderr = compile_user.stderr + compile_shim.stderr + link.stderr
    build = _BuildResult()
    import time as _t
    rec["exit_code"] = build.returncode
    rec["stderr"] = save(out, "build_stderr.txt", build.stderr)
    rec["stdout"] = save(out, "build_stdout.txt", build.stdout)
    if build.returncode == 0:
        rec["artifacts"] = [save(out, "app.bin", open(exe, "rb").read(), 4 * 1024 * 1024)]
        nm = subprocess.run([NM, "-S", exe], capture_output=True, timeout=60)
        rec["artifacts"].append(save(out, "symbols.txt", nm.stdout, 2 * 1024 * 1024))
    manifest["stages"].append(rec)
    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)


if __name__ == "__main__":
    main()
