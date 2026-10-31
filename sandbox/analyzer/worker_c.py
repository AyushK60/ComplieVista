#!/usr/bin/env python3
"""M2 trusted C analyzer worker — runs INSIDE the pinned, network-less container.

Reads only /work/<file> (staged snapshot copy), writes only /out. Fixed allowlisted
flag sets only — no user-supplied flags exist on this path. Emits raw stage outputs
plus an incrementally-updated manifest.json so a killed run keeps completed stages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time

OUT_CAP = 8 * 1024 * 1024
STAGE_TIMEOUT = 45
CLANG = "clang-18"
READELF = "llvm-readelf-18"
OBJDUMP = "llvm-objdump-18"

manifest: dict = {"worker": "worker_c.py", "stages": [], "tool_versions": {}}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(out: str, name: str, data: bytes, cap: int = OUT_CAP) -> dict:
    truncated = len(data) > cap
    with open(os.path.join(out, name), "wb") as f:
        f.write(data[:cap])
    return {"file": name, "sha256": sha(data[:cap]), "bytes": min(len(data), cap),
            "truncated": truncated}


def run_stage(out: str, stage: str, argv: list[str], outputs: list[tuple[str, str, int]]) -> None:
    """Run one fixed argv; save stdout/stderr and declared outputs; update manifest."""
    rec: dict = {"stage": stage, "argv_tail": argv[1:], "tool": argv[0]}
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(argv, capture_output=True, timeout=STAGE_TIMEOUT)
        rec["exit_code"] = proc.returncode
        stdout, stderr = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        rec["exit_code"] = -1
        rec["timeout"] = True
        stdout, stderr = e.stdout or b"", e.stderr or b""
    rec["duration_ms"] = int((time.perf_counter() - t0) * 1000)
    rec["stdout"] = save(out, f"{stage}_stdout.txt", stdout)
    rec["stderr"] = save(out, f"{stage}_stderr.txt", stderr)
    rec["artifacts"] = []
    if rec.get("exit_code") == 0:
        for fname, source, cap in outputs:
            if source == "stdout":
                data = stdout
            elif source == "stderr":
                data = stderr
            else:
                path = os.path.join(out, source)
                if not os.path.isfile(path):
                    continue
                with open(path, "rb") as f:
                    data = f.read()
                os.remove(path)
            rec["artifacts"].append(save(out, fname, data, cap))
    manifest["stages"].append(rec)
    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)   # rel path under /work
    ap.add_argument("--out", required=True)    # /out
    args = ap.parse_args()
    src = os.path.join("/work", args.file)
    out = args.out
    base = os.path.basename(args.file)
    stem = os.path.splitext(base)[0]

    try:
        v = subprocess.run([CLANG, "--version"], capture_output=True, timeout=30).stdout
        manifest["tool_versions"]["clang"] = v.decode("utf-8", "replace").splitlines()[0]
    except Exception as e:  # pragma: no cover
        manifest["tool_versions"]["clang"] = f"unavailable: {e}"

    # Fixed, allowlisted flag sets. The file argument is a validated staged path.
    run_stage(out, "preprocess", [CLANG, "-E", src], [("preprocessed.i", "stdout", OUT_CAP)])
    run_stage(out, "tokens", [CLANG, "-fsyntax-only", "-Xclang", "-dump-tokens", src], [])
    run_stage(out, "ast", [CLANG, "-fsyntax-only", "-Xclang", "-ast-dump=json", src],
              [("ast.json", "stdout", 16 * 1024 * 1024)])
    run_stage(out, "ir_o0", [CLANG, "-S", "-emit-llvm", "-g", "-O0", "-o",
                             os.path.join(out, "ir_O0.ll"), src],
              [("ir_O0.ll", "ir_O0.ll", OUT_CAP)])
    run_stage(out, "ir_o2", [CLANG, "-S", "-emit-llvm", "-g", "-O2", "-o",
                             os.path.join(out, "ir_O2.ll"), src],
              [("ir_O2.ll", "ir_O2.ll", OUT_CAP)])
    run_stage(out, "assembly", [CLANG, "-S", "-g", "-O0", "-o",
                                os.path.join(out, f"{stem}_O0.s"), src],
              [("assembly_O0.s", f"{stem}_O0.s", OUT_CAP)])
    run_stage(out, "object", [CLANG, "-c", "-g", "-O0", "-o",
                              os.path.join(out, "object.o"), src], [])
    if any(a["stage"] == "object" and a.get("exit_code") == 0 for a in manifest["stages"]):
        obj_rec = next(a for a in manifest["stages"] if a["stage"] == "object")
        with open(os.path.join(out, "object.o"), "rb") as f:
            obj_rec["artifacts"].append(save(out, "object.bin", f.read(), 2 * 1024 * 1024))
        run_stage(out, "symbols", [READELF, "-s", os.path.join(out, "object.o")],
                  [("symbols.txt", "stdout", 2 * 1024 * 1024)])
        run_stage(out, "disassembly", [OBJDUMP, "-d", os.path.join(out, "object.o")],
                  [("disassembly.txt", "stdout", 2 * 1024 * 1024)])
        obj_path = os.path.join(out, "object.o")
        if os.path.isfile(obj_path):
            os.remove(obj_path)
    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)


if __name__ == "__main__":
    main()
