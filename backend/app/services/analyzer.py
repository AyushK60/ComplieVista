"""M2 analysis orchestrator (ADR-0005).

Untrusted source is analyzed ONLY inside the pinned, restricted container:
 --network none, read-only rootfs, size-capped tmpfs, --cap-drop ALL,
 --security-opt no-new-privileges, non-root UID, memory/cpu/pids limits,
 snapshot mounted read-only, per-job output dir mounted rw (disposable job space),
 argv-array invocation only, external wall-clock timeout with orchestrator-enforced
 `docker rm -f` cleanup (M0 finding), no Docker socket anywhere near a container.

Jobs are queued (single bounded worker thread), persisted in SQLite, cancellable
while queued, and idempotent on (snapshot, target, tool fingerprint).
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

from app.core.config import (ANALYSIS_POLICY_VERSION, ANALYSIS_TIMEOUT_S,
                             ANALYZER_IMAGE, ANALYSIS_MAX_CONCURRENT)
from app.services.staging import jobs_root
from app.store.db import Store, new_id, now_utc

_BASE_FLAGS = [
    "--rm", "--network", "none", "--read-only",
    "--tmpfs", "/tmp:rw,size=64m,noexec",
    "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges",
    "--user", "1000:1000",
    "--memory", "512m", "--cpus", "1", "--pids-limit", "128",
]
_TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BLOCKED"}


class AnalysisError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def image_id() -> str:
    """Immutable identity of the pinned analyzer image."""
    out = subprocess.run(["docker", "image", "inspect", "-f", "{{.Id}}", ANALYZER_IMAGE],
                         capture_output=True, timeout=30)
    line = out.stdout.decode().strip()
    return line or "unavailable"


def tool_fingerprint() -> str:
    return hashlib.sha256(f"{ANALYZER_IMAGE}:{image_id()}:{ANALYSIS_POLICY_VERSION}".encode()).hexdigest()[:32]


def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info", "--format", "ok"], capture_output=True,
                              timeout=20).stdout.strip() == b"ok"
    except (OSError, subprocess.TimeoutExpired):
        return False


def build_run_argv(cname: str, src: Path, out: Path, worker: str, rel: str) -> list[str]:
    """The ONLY container invocation builder. Argv array, fixed flags, validated paths."""
    return [
        "docker", "run", "--rm", "--name", cname, *_BASE_FLAGS,
        "-v", f"{src}:/work:ro", "-v", f"{out}:/out",
        ANALYZER_IMAGE, "python3", f"/opt/analyzer/{worker}", "--file", rel, "--out", "/out",
    ]


class _JobRunner:
    """Single bounded worker thread consuming an in-memory queue of persisted jobs."""

    def __init__(self, store: Store):
        self.store = store
        self.q: queue.Queue[str] = queue.Queue()
        self._threads: list[threading.Thread] = []
        for i in range(ANALYSIS_MAX_CONCURRENT):
            t = threading.Thread(target=self._loop, daemon=True, name=f"analysis-{i}")
            t.start()
            self._threads.append(t)

    def enqueue(self, analysis_id: str) -> None:
        self.q.put(analysis_id)

    def _loop(self) -> None:
        while True:
            analysis_id = self.q.get()
            try:
                self._run(analysis_id)
            except Exception as e:  # noqa: BLE001 - a job must never kill the worker
                self.store.execute(
                    "UPDATE analyses SET status='FAILED', error_code=?, finished_utc=? WHERE id=?",
                    (f"WORKER:{type(e).__name__}", now_utc(), analysis_id))

    def _run(self, analysis_id: str) -> None:
        store = self.store
        job = store.query_one("SELECT * FROM analyses WHERE id=?", (analysis_id,))
        if not job or job["status"] != "QUEUED":
            return
        if job["cancel_requested"]:
            store.execute("UPDATE analyses SET status='CANCELLED', finished_utc=? WHERE id=?",
                          (now_utc(), analysis_id))
            return
        if not docker_available():
            store.execute(
                "UPDATE analyses SET status='BLOCKED', error_code='DOCKER_UNAVAILABLE',"
                " finished_utc=? WHERE id=?", (now_utc(), analysis_id))
            return
        store.execute("UPDATE analyses SET status='RUNNING', started_utc=?, tool_fingerprint=?,"
                      " image_id=? WHERE id=?", (now_utc(), tool_fingerprint(), image_id(),
                                                 analysis_id))

        # Materialize the immutable snapshot into disposable native job space.
        job_dir = jobs_root() / f"analysis-{analysis_id[:12]}"
        src = job_dir / "src"
        out = job_dir / "out"
        try:
            src.mkdir(parents=True)
            out.mkdir(parents=True)
            files = store.query("SELECT rel_path, content_sha256 FROM source_files WHERE snapshot_id=?",
                                (job["snapshot_id"],))
            for f in files:
                dest = src / f["rel_path"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(store.get_artifact(f["content_sha256"]))
            primary = src / job["primary_file"]
            if not primary.is_file():
                raise AnalysisError("PRIMARY_FILE_MISSING",
                                    f"{job['primary_file']} missing from snapshot")

            worker = "worker_python.py" if job["language"] == "python" else "worker_c.py"
            cname = f"cv-analysis-{analysis_id[:12]}"
            argv = build_run_argv(cname, src, out, worker, job["primary_file"])
            timeout = ANALYSIS_TIMEOUT_S
            t0 = time.perf_counter()
            killed = False
            try:
                proc = subprocess.run(argv, capture_output=True, timeout=timeout)
                run_failed = proc.returncode != 0
                stderr_tail = proc.stderr.decode("utf-8", "replace")[-500:]
            except subprocess.TimeoutExpired:
                killed = True
                run_failed = True
                stderr_tail = f"orchestrator timeout after {timeout}s"
                subprocess.run(["docker", "rm", "-f", cname], capture_output=True, timeout=60)
            duration_ms = int((time.perf_counter() - t0) * 1000)

            manifest_path = out / "manifest.json"
            if not manifest_path.is_file():
                store.execute(
                    "UPDATE analyses SET status=?, error_code='NO_MANIFEST', finished_utc=?,"
                    " duration_ms=? WHERE id=?",
                    ("TIMEOUT" if killed else "FAILED", now_utc(), duration_ms, analysis_id))
                return

            from app.services.normalize import ingest_stage_records
            stage_count = ingest_stage_records(store, analysis_id, out, job["language"])
            if killed:
                status = "CANCELLED" if store.query_one(
                    "SELECT cancel_requested FROM analyses WHERE id=?",
                    (analysis_id,))["cancel_requested"] else "TIMEOUT"
            elif stage_count == 0:
                status = "FAILED"
            else:
                status = "COMPLETED"
            store.execute(
                "UPDATE analyses SET status=?, finished_utc=?, duration_ms=?, error_code=? WHERE id=?",
                (status, now_utc(), duration_ms,
                 None if status == "COMPLETED" else stderr_tail[:200], analysis_id))
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)  # disposable job space, always cleaned

    def cancel(self, analysis_id: str) -> str:
        job = self.store.query_one("SELECT status, cancel_requested FROM analyses WHERE id=?",
                                   (analysis_id,))
        if not job:
            raise AnalysisError("NOT_FOUND", "unknown analysis id", 404)
        if job["status"] in _TERMINAL:
            return job["status"]
        if job["status"] == "QUEUED":
            self.store.execute("UPDATE analyses SET status='CANCELLED', finished_utc=? WHERE id=?",
                               (now_utc(), analysis_id))
            return "CANCELLED"
        self.store.execute("UPDATE analyses SET cancel_requested=1 WHERE id=?", (analysis_id,))
        return "CANCEL_REQUESTED"


_RUNNERS: dict[int, _JobRunner] = {}
_RUNNER_LOCK = threading.Lock()


def get_runner(store: Store) -> _JobRunner:
    key = id(store)
    with _RUNNER_LOCK:
        if key not in _RUNNERS:
            _RUNNERS[key] = _JobRunner(store)
        return _RUNNERS[key]


def create_analysis(store: Store, snapshot_id: str, target_id: str) -> dict:
    snap = store.query_one("SELECT * FROM source_snapshots WHERE id=?", (snapshot_id,))
    if not snap:
        raise AnalysisError("NOT_FOUND", "unknown snapshot", 404)
    target = store.query_one("SELECT * FROM compilation_targets WHERE id=? AND snapshot_id=?",
                             (target_id, snapshot_id))
    if not target:
        raise AnalysisError("NOT_FOUND", "unknown target for snapshot", 404)
    if target["status"] == "BLOCKED":
        raise AnalysisError("TARGET_BLOCKED",
                            "target is classified BLOCKED; analysis not offered")
    language = "python" if target["kind"].startswith("python") else "c"
    fp = f"{snap['combined_sha256']}:{target_id}:{tool_fingerprint()}"
    existing = store.query_one(
        "SELECT id, status FROM analyses WHERE fingerprint=? AND status IN ('COMPLETED','RUNNING','QUEUED')"
        " ORDER BY created_utc DESC LIMIT 1", (fp,))
    if existing:
        return {"analysis_id": existing["id"], "status": existing["status"], "existed": True}
    aid = new_id()
    store.execute(
        "INSERT INTO analyses (id, snapshot_id, target_id, language, primary_file, status,"
        " fingerprint, source_combined_sha256, created_utc) VALUES (?,?,?,?,?,?,?,?,?)",
        (aid, snapshot_id, target_id, language, target["primary_file"], "QUEUED", fp,
         snap["combined_sha256"], now_utc()))
    get_runner(store).enqueue(aid)
    return {"analysis_id": aid, "status": "QUEUED", "existed": False}
