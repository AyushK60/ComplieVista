#!/usr/bin/env python3
"""M6-A C optimization build worker — runs INSIDE the pinned analyzer container.

Builds ONE immutable source at -O0/-O1/-O2 (allowlisted flags only, recorded
verbatim) with NO trace instrumentation (bench/compare builds are uninstrumented;
M4's instrumented builds remain separate). Per level, under out/<O>/:
  ir.ll (-S -emit-llvm), asm.s (-S), obj.o (-c), app (linked), symbols.txt
  (llvm-nm-18 -S), sizes, per-step durations, digests.
Manifest out/manifest.json records clang version/target, flags, digests,
durations and stderr tails. Optimization remarks: captured with -Rpass=.* when
the compiler actually emits them (availability recorded honestly).

Omitted/empty artifacts stay absent — availability is explicit, never faked.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time

CLANG = "clang-18"
NM = "llvm-nm-18"
LEVELS = ("O0", "O1", "O2")
CAP = 8 * 1024 * 1024


def save(path: str, data: bytes) -> dict:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data[:CAP])
    return {"file": os.path.relpath(path, OUT), "sha256":
            hashlib.sha256(data[:CAP]).hexdigest(),
            "bytes": min(len(data), CAP), "truncated": len(data) > CAP}


OUT = ""
manifest: dict = {"worker": "c_opt_worker.py", "levels": {}, "tool": {}}


def main() -> None:
    global OUT
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    OUT = args.out
    src = os.path.join("/work", args.file)

    ver = subprocess.run([CLANG, "--version"], capture_output=True, timeout=30)
    tgt = subprocess.run([CLANG, "-print-target-triple"], capture_output=True,
                         timeout=30)
    manifest["tool"] = {"clang": ver.stdout.decode("utf-8", "replace").splitlines()[0],
                        "target": tgt.stdout.decode().strip(),
                        "full_version": ver.stdout.decode("utf-8", "replace")[:400]}
    base_flags = ["-g", "-no-pie", "-fno-omit-frame-pointer"]

    for level in LEVELS:
        rec: dict = {"flags": [f"-{level}"] + base_flags, "steps": {},
                     "artifacts": [], "remarks_available": False}
        odir = os.path.join(OUT, level)
        os.makedirs(odir, exist_ok=True)

        def run_step(name: str, argv: list[str]) -> None:
            t0 = time.monotonic()
            r = subprocess.run(argv, capture_output=True, timeout=90)
            dt = int((time.monotonic() - t0) * 1000)
            rec["steps"][name] = {
                "exit_code": r.returncode, "duration_ms": dt,
                "stderr_tail": r.stderr.decode("utf-8", "replace")[-600:]}
            if name == "ir" and r.returncode == 0 and (
                    b"remark:" in r.stderr or b"pass" in r.stderr.lower()):
                rec["remarks_available"] = True
            return r

        ir = run_step("ir", [CLANG, f"-{level}", "-S", "-emit-llvm", "-o",
                             os.path.join(odir, "ir.ll"), src] + base_flags)
        if ir.returncode == 0:
            rec["artifacts"].append(save(os.path.join(odir, "ir.ll"),
                                         open(os.path.join(odir, "ir.ll"), "rb").read()))
        asm = run_step("asm", [CLANG, f"-{level}", "-S", "-o",
                               os.path.join(odir, "asm.s"), src] + base_flags)
        if asm.returncode == 0:
            rec["artifacts"].append(save(os.path.join(odir, "asm.s"),
                                         open(os.path.join(odir, "asm.s"), "rb").read()))
        obj = run_step("obj", [CLANG, f"-{level}", "-c", "-o",
                               os.path.join(odir, "obj.o"), src] + base_flags)
        if obj.returncode == 0:
            rec["artifacts"].append(save(os.path.join(odir, "obj.o"),
                                         open(os.path.join(odir, "obj.o"), "rb").read()))
        link = run_step("link", [CLANG, f"-{level}", "-o", os.path.join(odir, "app"),
                                 src] + base_flags)
        if link.returncode == 0:
            exe = os.path.join(odir, "app")
            os.chmod(exe, 0o755)
            rec["artifacts"].append(save(exe, open(exe, "rb").read()))
            nm = subprocess.run([NM, "-S", exe], capture_output=True, timeout=60)
            rec["artifacts"].append(save(os.path.join(odir, "symbols.txt"), nm.stdout))
            rec["exe_bytes"] = os.path.getsize(exe)
        rec["ok"] = all(rec["steps"][s]["exit_code"] == 0
                        for s in ("ir", "asm", "obj", "link"))
        manifest["levels"][level] = rec

    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)


if __name__ == "__main__":
    main()
