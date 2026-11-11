#!/usr/bin/env python3
"""Stage 7 C-05 multi-file link worker - runs INSIDE the pinned analyzer container.

Compiles the curated translation units listed in --tus (JSON; derived from the
versioned demo manifest - NEVER from user input) with the same allowlisted flags
as the single-file build worker, then links all TUs + the trace shim. Emits the
executable, symbols.txt (llvm-nm-18 -S) and a manifest with digests/durations so
the linker-resolved cross-TU symbols are inspectable evidence.

No make/CMake/repo scripts: every argv is fixed here.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time

CLANG = "clang-18"
NM = "llvm-nm-18"
CAP = 8 * 1024 * 1024


def save(path: str, data: bytes) -> dict:
    with open(path, "wb") as f:
        f.write(data[:CAP])
    return {"file": os.path.basename(path),
            "sha256": hashlib.sha256(data[:CAP]).hexdigest(),
            "bytes": min(len(data), CAP), "truncated": len(data) > CAP}


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--primary", required=True)
    ap.add_argument("--tus", required=True, help="JSON array of TU paths (relative to /work)")
    args = ap.parse_args()
    out = args.out
    tus = json.loads(args.tus)
    if not isinstance(tus, list) or not 1 < len(tus) <= 8:
        raise SystemExit("invalid TU list")
    manifest: dict = {"worker": "c_link_worker.py", "tool": {}, "steps": {},
                      "tus": tus, "artifacts": []}
    ver = subprocess.run([CLANG, "--version"], capture_output=True, timeout=30)
    manifest["tool"]["clang"] = ver.stdout.decode("utf-8", "replace").splitlines()[0]

    base = ["-g", "-O0", "-no-pie", "-finstrument-functions"]
    objects = []
    for i, tu in enumerate(tus):
        if not isinstance(tu, str) or "/" in tu or not tu.endswith(".c"):
            raise SystemExit(f"invalid TU: {tu!r}")
        obj = os.path.join(out, f"tu{i}.o")
        t0 = time.monotonic()
        r = subprocess.run([CLANG] + base + ["-c", "-o", obj,
                                             os.path.join("/work", tu)],
                           capture_output=True, timeout=90)
        manifest["steps"][f"compile:{tu}"] = {
            "exit_code": r.returncode,
            "duration_ms": int((time.monotonic() - t0) * 1000),
            "stderr_tail": r.stderr.decode("utf-8", "replace")[-400:]}
        if r.returncode != 0:
            break
        objects.append(obj)

    shim_src = os.path.join(out, "c_trace_shim.c")
    with open(shim_src, "wb") as f:
        f.write(open("/opt/analyzer/c_trace_shim.c", "rb").read())
    shim_obj = os.path.join(out, "shim.o")
    r_shim = subprocess.run([CLANG, "-g", "-O0", "-c", "-o", shim_obj, shim_src],
                            capture_output=True, timeout=90)
    manifest["steps"]["compile:shim"] = {
        "exit_code": r_shim.returncode,
        "stderr_tail": r_shim.stderr.decode("utf-8", "replace")[-200:]}

    if len(objects) == len(tus) and r_shim.returncode == 0:
        exe = os.path.join(out, "app")
        t0 = time.monotonic()
        r_link = subprocess.run([CLANG, "-no-pie", "-o", exe, *objects, shim_obj],
                                capture_output=True, timeout=90)
        manifest["steps"]["link"] = {
            "exit_code": r_link.returncode,
            "duration_ms": int((time.monotonic() - t0) * 1000),
            "stderr_tail": r_link.stderr.decode("utf-8", "replace")[-400:]}
        if r_link.returncode == 0:
            manifest["artifacts"].append(save(os.path.join(out, "app.bin"),
                                              open(exe, "rb").read()))
            nm = subprocess.run([NM, "-S", exe], capture_output=True, timeout=60)
            manifest["artifacts"].append(save(os.path.join(out, "symbols.txt"),
                                              nm.stdout))
            # record the binary digest for provenance
            manifest["app_sha256"] = hashlib.sha256(
                open(exe, "rb").read()).hexdigest()

    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)


if __name__ == "__main__":
    main()
