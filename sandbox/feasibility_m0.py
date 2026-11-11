#!/usr/bin/env python3
"""Stage 0 Deliverable F - controlled-execution FEASIBILITY probe (not a safety claim).

Runs two curated trivial fixtures under the ADR-0003 restrictive Docker baseline:
  --network none, --read-only rootfs, size-capped tmpfs /tmp, --cap-drop ALL,
  --security-opt no-new-privileges, non-root --user, --memory/--cpus/--pids-limit,
  --ulimit fsize, no ports, read-only bind of a staged job dir, --rm.
Plus a deliberate infinite-loop probe proving the external wall-clock timeout kills
the run and leaves no container behind. Records image RepoDigests for immutability.

This does NOT authorize pasted-code execution and is not adversarial validation (Stage 4).
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

from app.services import staging  # noqa: E402

EVID = REPO / "evidence" / "m0" / "docker"
TIMEOUT_S = 120

C_RUN_IMAGE = "ubuntu:24.04"
PY_IMAGE = "python:3.12-slim"

BASE_FLAGS = [
    "--rm", "--network", "none", "--read-only",
    "--tmpfs", "/tmp:rw,size=4m,noexec",
    "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges",
    "--user", "1000:1000",
    "--memory", "128m", "--cpus", "0.5", "--pids-limit", "64",
    "--ulimit", "fsize=1048576:1048576",
]


def sh(argv: list[str], timeout: int = TIMEOUT_S) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, timeout=timeout)


def container_count() -> int:
    out = sh(["docker", "ps", "-aq"]).stdout.decode().strip()
    return len(out.splitlines()) if out else 0


def image_digest(image: str) -> str | None:
    out = sh(["docker", "image", "inspect", "-f", "{{index .RepoDigests 0}}", image])
    line = out.stdout.decode().strip()
    return line if out.returncode == 0 and line else None


def ensure_image(image: str) -> dict:
    d = image_digest(image)
    if d is None:
        proc = sh(["docker", "pull", image], timeout=600)
        if proc.returncode != 0:
            raise RuntimeError(f"pull failed for {image}: {proc.stderr.decode()[:300]}")
        d = image_digest(image)
    return {"image": image, "repo_digest": d}


def docker_run(name: str, image: str, digest: str | None, staged_src: str,
               tail_argv: list[str], expected_exit: int, expected_stdout: str,
               timeout_s: int = TIMEOUT_S) -> dict:
    cname = f"m0-{name}-{uuid.uuid4().hex[:8]}"
    argv = ["docker", "run", "--name", cname, *BASE_FLAGS,
            "-v", f"{staged_src}:/work:ro", image, *tail_argv]
    before = container_count()
    t0 = time.perf_counter()
    killed_by_timeout = False
    cleanup_enforced = False
    try:
        proc = subprocess.run(argv, capture_output=True, timeout=timeout_s)
        rc, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        # External timeout kills the docker CLI but NOT the container: the orchestrator
        # must enforce process-tree termination itself (the project notes). Record both facts.
        rc, out, err = -1, e.stdout or b"", e.stderr or b""
        killed_by_timeout = True
        rm = sh(["docker", "rm", "-f", cname], timeout=60)
        cleanup_enforced = rm.returncode == 0
    ms = int((time.perf_counter() - t0) * 1000)
    after = container_count()
    gone = sh(["docker", "inspect", cname]).returncode != 0
    out_text = out.decode("utf-8", "replace")
    return {
        "probe": name,
        "container_name": cname,
        "argv_tail": tail_argv,
        "image": image,
        "image_repo_digest": digest,
        "restrictive_flags": BASE_FLAGS,
        "exit_code": rc,
        "stdout": out_text[:500],
        "stdout_sha256": hashlib.sha256(out).hexdigest(),
        "stderr_excerpt": err.decode("utf-8", "replace")[:500],
        "duration_ms": ms,
        "killed_by_external_timeout": killed_by_timeout,
        "orchestrator_forced_cleanup": cleanup_enforced,
        "containers_before": before,
        "containers_after": after,
        "cleanup_ok": gone and after <= before,
        "expected_exit": expected_exit,
        "expected_stdout": expected_stdout,
        "pass": (rc == expected_exit) and out_text == expected_stdout and gone and after <= before,
    }


def main() -> int:
    EVID.mkdir(parents=True, exist_ok=True)
    docker_server = sh(["docker", "version", "--format", "{{.Server.Version}}"]).stdout.decode().strip()

    # Stage curated sources into Linux-native job storage (ADR-0001 mechanism).
    job_id = f"m0-feas-{uuid.uuid4().hex[:8]}"
    manifest = staging.snapshot_tree(REPO / "sandbox" / "fixtures", job_id)
    staged_src = manifest["staged_dir"]

    # Compile the curated C fixture on the host (Ubuntu 24.04 glibc == ubuntu:24.04 image),
    # then place the binary next to the staged sources (its digest is recorded here).
    bin_path = Path(staged_src) / "c_curated"
    comp = sh(["clang", "-O0", "-o", str(bin_path), str(REPO / "demos" / "m0" / "c_fixture.c")])
    if comp.returncode != 0:
        raise RuntimeError("curated C compile failed: " + comp.stderr.decode()[:300])
    c_bin_sha = hashlib.sha256(bin_path.read_bytes()).hexdigest()

    images = [ensure_image(C_RUN_IMAGE), ensure_image(PY_IMAGE)]
    results = []

    results.append(docker_run(
        "python_curated_deterministic", PY_IMAGE, images[1]["repo_digest"], staged_src,
        ["python3", "/work/py_curated.py"], 0, "total=28\n"))
    results.append(docker_run(
        "c_curated_deterministic", C_RUN_IMAGE, images[0]["repo_digest"], staged_src,
        ["/work/c_curated"], 0, "total=28\n"))
    results.append(docker_run(
        "python_infinite_loop_timeout", PY_IMAGE, images[1]["repo_digest"], staged_src,
        ["python3", "/work/py_spin.py"], expected_exit=-1, expected_stdout="",
        timeout_s=20))

    out = {
        "schema_version": "m0.v1",
        "purpose": "FEASIBILITY ONLY - not a secure-sandbox claim (ADR-0003, docs/SECURITY.md)",
        "docker_server_version": docker_server,
        "host": platform.platform(),
        "staged_job": {"job_id": job_id, "combined_sha256": manifest["combined_sha256"],
                       "file_count": manifest["file_count"]},
        "c_binary_sha256": c_bin_sha,
        "images": images,
        "probes": results,
        "not_tested_here": ["adversarial escape tests", "fork bombs", "network attacks",
                            "docker escape probes", "ptrace/GDB (declared UNSUPPORTED)"],
        "limitations": [
            "Docker-in-WSL2 shares one kernel with the analysis worker.",
            "Default seccomp profile only; AppArmor/LSM customization unverified.",
            "Docker socket access is host-equivalent privilege; held by trusted orchestration only.",
        ],
    }
    (EVID / "manifest.json").write_text(json.dumps(out, indent=1))
    print(f"Docker feasibility: server={docker_server}")
    for r in results:
        print(f"  {r['probe']:32s} pass={r['pass']} exit={r['exit_code']} "
              f"out={r['stdout']!r} cleanup_ok={r['cleanup_ok']} {r['duration_ms']}ms")
    staging.cleanup_job(job_id)
    ok = all(r["pass"] for r in results)
    print("OVERALL:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
