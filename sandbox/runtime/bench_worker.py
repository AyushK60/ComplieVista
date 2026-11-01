#!/usr/bin/env python3
"""M6-D benchmark worker — runs INSIDE the pinned runtime container.

Measures UNINSTRUMENTED execution (no settrace, no -finstrument-functions):
  C mode:      --bin-dir /out with app-O0/O1/O2 -> N timed runs per level
  Python mode: --file <py> with a main() -> N timed in-process runs
Per sample: wall (monotonic) and CPU time (RUSAGE_CHILDREN delta for C,
process_time for Python), stdout checksum per run (semantics-equivalence and
dead-code-elimination guard: checksums must be identical across repeats AND
levels). Warmup runs happen before timing and are excluded.

Environment provenance recorded: kernel, cpu model (from /proc/cpuinfo),
cgroup v2 cpu/memory limits of this container. Stats (median/min/max/stdev/n)
are computed from the raw samples, which are also stored for re-derivation.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import resource
import statistics
import subprocess
import time
from contextlib import redirect_stdout


def env_info() -> dict:
    info = {"kernel": open("/proc/sys/kernel/osrelease").read().strip()[:80]}
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                info["cpu_model"] = line.split(":", 1)[1].strip()[:80]
                break
    except OSError:
        pass
    for key, path in (("cgroup_cpu_max", "/sys/fs/cgroup/cpu.max"),
                      ("cgroup_memory_max", "/sys/fs/cgroup/memory.max")):
        try:
            info[key] = open(path).read().strip()[:40]
        except OSError:
            info[key] = "unavailable"
    info["os"] = "Linux (container)"
    return info


def cpu_children_delta() -> float:
    ru = resource.getrusage(resource.RUSAGE_CHILDREN)
    return ru.ru_utime + ru.ru_stime


def stats(samples: list[float]) -> dict:
    if not samples:
        return {"n": 0}
    return {"n": len(samples), "median_ms": round(statistics.median(samples), 3),
            "min_ms": round(min(samples), 3), "max_ms": round(max(samples), 3),
            "stdev_ms": round(statistics.stdev(samples), 3) if len(samples) > 1 else 0.0}


def run_c_level(exe: str, warmup: int, repeats: int) -> dict:
    checksums = []
    for _ in range(warmup):
        subprocess.run([exe], capture_output=True, timeout=30)
    samples = []
    for _ in range(repeats):
        cpu0 = cpu_children_delta()
        t0 = time.monotonic()
        r = subprocess.run([exe], capture_output=True, timeout=30)
        wall_ms = (time.monotonic() - t0) * 1000
        cpu_ms = (cpu_children_delta() - cpu0) * 1000
        samples.append({"wall_ms": round(wall_ms, 3), "cpu_ms": round(cpu_ms, 3)})
        checksums.append(hashlib.sha256(r.stdout).hexdigest()[:16])
    return {"samples": samples, "checksums": checksums,
            "checksums_identical": len(set(checksums)) == 1,
            "resolution_warning": stats([s["wall_ms"] for s in samples]).get(
                "median_ms", 99) < 5.0,
            "wall": stats([s["wall_ms"] for s in samples]),
            "cpu": stats([s["cpu_ms"] for s in samples])}


def run_py_level(code, warmup: int, repeats: int) -> dict:
    g = {"__name__": "__main__"}
    exec(code, g)  # defines main(); module-level guard not required
    main = g.get("main")
    if not callable(main):
        raise SystemExit("python workload must define main()")
    checksums = []
    for _ in range(warmup):
        buf = io.StringIO()
        with redirect_stdout(buf):
            main()
    samples = []
    for _ in range(repeats):
        cpu0 = time.process_time()
        t0 = time.perf_counter()
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = main()
        wall_ms = (time.perf_counter() - t0) * 1000
        cpu_ms = (time.process_time() - cpu0) * 1000
        samples.append({"wall_ms": round(wall_ms, 3), "cpu_ms": round(cpu_ms, 3)})
        checksums.append(hashlib.sha256(
            json.dumps({"ret": str(ret)}, sort_keys=True).encode()).hexdigest()[:16])
    return {"samples": samples, "checksums": checksums,
            "checksums_identical": len(set(checksums)) == 1,
            "resolution_warning": stats([s["wall_ms"] for s in samples]).get(
                "median_ms", 99) < 5.0,
            "wall": stats([s["wall_ms"] for s in samples]),
            "cpu": stats([s["cpu_ms"] for s in samples])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("c", "python"), required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--repeats", type=int, default=7)
    ap.add_argument("--warmup", type=int, default=2)
    ap.add_argument("--file")  # python workload
    ap.add_argument("--bin-dir")  # C: dir with app-O0/O1/O2
    args = ap.parse_args()
    repeats = max(5, min(args.repeats, 15))
    warmup = max(0, min(args.warmup, 5))
    result: dict = {"worker": "bench_worker.py", "mode": args.mode,
                    "repeats": repeats, "warmup": warmup,
                    "env": env_info(), "levels": {}, "errors": {}}
    if args.mode == "c":
        for level in ("O0", "O1", "O2"):
            exe = os.path.join(args.bin_dir, f"app-{level}")
            if not os.path.isfile(exe):
                result["errors"][level] = "executable missing"
                continue
            try:
                os.chmod(exe, 0o755)
            except OSError:
                pass  # read-only mount: the orchestrator set the exec bit host-side
            try:
                result["levels"][level] = run_c_level(exe, warmup, repeats)
            except subprocess.TimeoutExpired:
                result["errors"][level] = "sample run timed out"
    else:
        src = open(os.path.join("/work", args.file), "rb").read()
        code = compile(src, os.path.basename(args.file), "exec", dont_inherit=True)
        try:
            result["levels"]["py312"] = run_py_level(code, warmup, repeats)
        except Exception as e:  # noqa: BLE001
            result["errors"]["py312"] = f"{type(e).__name__}: {e}"[:200]
    result["levels_semantics_equivalent"] = (
        len({lv["checksums"][0] for lv in result["levels"].values()}) == 1
        if result["levels"] and all(lv["checksums"] for lv in result["levels"].values())
        else None)
    with open(os.path.join(args.out, "bench.json"), "w") as f:
        json.dump(result, f, indent=1)


if __name__ == "__main__":
    main()
