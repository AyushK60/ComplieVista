"""M4-B execution orchestrator — controlled C/Python execution, traces, replay data.

Separate privilege domain from static analysis: builds happen in the pinned analyzer
container (clang-18 + instrumentation shim); execution happens in the minimal runtime
container. Both run with the restrictive baseline (network none, read-only rootfs,
tmpfs, cap-drop ALL, no-new-privileges, non-root, cpu/mem/pids caps, external timeout,
orchestrator-forced cleanup). No Docker socket in any container; argv arrays only.

Modes (ADR-0007): static analysis (pre-existing), curated/pasted execution — both use
the same restricted runner; pasted execution is admitted only for targets whose
classification and provenance pass admission. GitHub-imported snapshots NEVER execute
in M4 (EXECUTION_ORIGIN_BLOCKED — explicit-fail, per README §10 "never auto-run" and
fail-closed policy).
"""
from __future__ import annotations

import hashlib
import json
import queue
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from app.core.config import ANALYSIS_TIMEOUT_S, ANALYZER_IMAGE
from app.services.analyzer import image_id as analyzer_image_id
from app.services.staging import jobs_root
from app.store.db import Store, new_id, now_utc

RUNTIME_IMAGE = "compilevista/runtime:m4"
RUN_TIMEOUT_S = 30
BUILD_TIMEOUT_S = 90
STDOUT_CAP = 1024 * 1024
STDERR_CAP = 1024 * 1024
EVENTS_CAP = 5000
# Defensive read cap for container-written files: the shim/harness cap their own
# output in-band, but the orchestrator never trusts a file's size (M4QA-02/03).
TRACE_FILE_CAP = 8 * 1024 * 1024
MAX_CONCURRENT = 1

_BASE_FLAGS = [
    "--rm", "--network", "none", "--read-only",
    "--tmpfs", "/tmp:rw,size=16m,noexec",
    "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges",
    "--user", "1000:1000",
    "--memory", "256m", "--cpus", "0.5", "--pids-limit", "64",
]

_TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BLOCKED"}


class ExecutionError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def runtime_image_id() -> str:
    try:
        out = subprocess.run(["docker", "image", "inspect", "-f", "{{.Id}}", RUNTIME_IMAGE],
                             capture_output=True, timeout=30)
        return out.stdout.decode().strip() or "unavailable"
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"



def _rmtree_or_privileged(job_dir: Path) -> None:
    """Remove a job dir; shared robust helper in staging (M4QA: retry + visible
    fallback failure)."""
    from app.services.staging import remove_disposable_dir
    remove_disposable_dir(job_dir, RUNTIME_IMAGE)



def _parse_symbols(symbols_txt: Path) -> list[tuple[int, int, str]]:
    """nm -S lines: ADDR SIZE type name → [(start, end, name)] for functions."""
    out = []
    for line in symbols_txt.read_text("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[2] in ("t", "T"):
            try:
                start = int(parts[0], 16)
                size = int(parts[1], 16)
                out.append((start, start + size, parts[3].strip()))
            except (ValueError, IndexError):
                continue
    return out


def _resolve_c_addr(raw: bytes, symbols: list[tuple[int, int, str]]) -> bytes:
    try:
        rec = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    addr = rec.get("addr")
    if addr is None:
        return raw
    for start, end, name in symbols:
        if start <= addr < end:
            rec["fn"] = name
            break
    else:
        rec["fn"] = f"0x{addr:x}"
    return json.dumps(rec).encode()


def run_capped(argv: list[str], timeout: int) -> dict:
    """Run argv, streaming stdout/stderr with byte caps (flood-safe): reads at most
    cap+1 bytes from each pipe, discards the remainder, writes sinks to files."""
    result: dict = {"stdout": b"", "stderr": b"", "stdout_truncated": False,
                    "stderr_truncated": False, "killed": False}

    sink_out: list = []
    sink_err: list = []

    def pump(pipe, sink: list, cap: int, trunc_key: str) -> None:
        read = 0
        while True:
            chunk = pipe.read(65536)
            if not chunk:
                break
            read += len(chunk)
            if read <= cap:
                sink.append(chunk)
            elif len(b"".join(sink)) < cap:
                sink.append(chunk[:cap - (read - len(chunk))])
            if read > cap:
                result[trunc_key] = True

    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    threads = [
        threading.Thread(target=lambda: pump(proc.stdout, sink_out, STDOUT_CAP,
                                             "stdout_truncated")),
        threading.Thread(target=lambda: pump(proc.stderr, sink_err, STDERR_CAP,
                                             "stderr_truncated")),
    ]
    for t in threads:
        t.start()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        result["killed"] = True
        proc.kill()
    for t in threads:
        t.join(timeout=10)
    result["stdout"] = b"".join(sink_out)
    result["stderr"] = b"".join(sink_err)
    result["exit_code"] = proc.returncode
    return result



class _ExecRunner:
    """Single bounded worker thread for execution jobs (separate from analysis)."""

    def __init__(self, store: Store):
        self.store = store
        self.q: queue.Queue[str] = queue.Queue()
        threading.Thread(target=self._loop, daemon=True, name="execution-0").start()

    def _reconcile_interrupted(self) -> None:
        # Remove leftover cv-build-*/cv-exec-* containers from crashed runs
        # (scoped to our name prefixes; audit T3: no ghost containers).
        out = subprocess.run(["docker", "ps", "-aq", "--filter",
                              "name=cv-build-", "--filter", "name=cv-exec-"],
                             capture_output=True, timeout=30)
        for cid in out.stdout.decode().split():
            subprocess.run(["docker", "rm", "-f", cid], capture_output=True, timeout=60)
        for r in self.store.query("SELECT id FROM executions WHERE status='RUNNING'"):
            self.store.execute(
                "UPDATE executions SET status='FAILED', error_code='INTERRUPTED_BY_RESTART',"
                " finished_utc=? WHERE id=?", (now_utc(), r["id"]))
        for r in self.store.query("SELECT id FROM executions WHERE status='QUEUED'"):
            self.q.put(r["id"])
        # M4QA-09: mop up orphaned execution job dirs (e.g. a previous process was
        # killed mid-job, so its `finally` cleanup never ran). Safe locally: this
        # runner is the single execution worker, and terminal jobs never touch
        # their job dir again.
        active = {r["id"][:12] for r in self.store.query(
            "SELECT id FROM executions WHERE status IN ('QUEUED','RUNNING')")}
        try:
            for d in jobs_root().glob("execution-*"):
                if d.name.removeprefix("execution-") not in active:
                    shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass

    def enqueue(self, execution_id: str) -> None:
        self.q.put(execution_id)

    def _loop(self) -> None:
        while True:
            eid = self.q.get()
            try:
                self._run(eid)
            except Exception as e:  # noqa: BLE001
                import traceback
                tb = traceback.format_exc().splitlines()[-1][:200]
                self.store.execute(
                    "UPDATE executions SET status='FAILED', error_code=?, finished_utc=?"
                    " WHERE id=?", (f"WORKER:{type(e).__name__}: {tb}", now_utc(), eid))

    def _run(self, eid: str) -> None:
        store = self.store
        job = store.query_one("SELECT * FROM executions WHERE id=?", (eid,))
        if not job or job["status"] != "QUEUED":
            return
        if job["cancel_requested"]:
            store.execute("UPDATE executions SET status='CANCELLED', finished_utc=? WHERE id=?",
                          (now_utc(), eid))
            return
        from app.services.analyzer import docker_available
        if not docker_available():
            store.execute("UPDATE executions SET status='BLOCKED',"
                          " error_code='DOCKER_UNAVAILABLE', finished_utc=? WHERE id=?",
                          (now_utc(), eid))
            return
        store.execute("UPDATE executions SET status='RUNNING', started_utc=?, image_id=?"
                      " WHERE id=?", (now_utc(), runtime_image_id(), eid))

        job_dir = jobs_root() / f"execution-{eid[:12]}"
        src = job_dir / "src"
        build_out = job_dir / "build"
        run_out = job_dir / "run"
        cname = f"cv-exec-{eid[:12]}"
        try:
            src.mkdir(parents=True, exist_ok=True)
            build_out.mkdir(parents=True, exist_ok=True)  # host-owned BEFORE mount
            run_out.mkdir(parents=True, exist_ok=True)
            for f in store.query("SELECT rel_path, content_sha256 FROM source_files"
                                 " WHERE snapshot_id=?", (job["snapshot_id"],)):
                dest = src / f["rel_path"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(store.get_artifact(f["content_sha256"]))

            t0 = time.monotonic()
            # M4QA-06: a cancel that arrives while the job is starting must not
            # launch a container afterwards (previously the container ran its full
            # wall-clock before cancel_requested was observed).
            if store.query_one("SELECT cancel_requested FROM executions WHERE id=?",
                               (eid,))["cancel_requested"]:
                self._finish(store, eid, "CANCELLED", None)
                return
            if job["language"] == "c":
                self._run_c(store, eid, job, src, build_out, run_out, cname)
            else:
                self._run_python(store, eid, job, src, run_out, cname)
            store.execute("UPDATE executions SET duration_ms=? WHERE id=?",
                          (int((time.monotonic() - t0) * 1000), eid))
        finally:
            _rmtree_or_privileged(job_dir)

    def _store_stream(self, store: Store, eid: str, kind: str, data: bytes) -> str:
        return store.put_artifact(data)

    def _record_events(self, store: Store, eid: str, lines: list[bytes]) -> int:
        seq = 0
        for raw in lines[:EVENTS_CAP]:
            seq += 1
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"kind": "unparsed", "raw": raw[:300].decode("utf-8", "replace")}
            store.execute(
                "INSERT INTO execution_events (execution_id, seq, kind, payload_json,"
                " sha256) VALUES (?,?,?,?,?)",
                (eid, seq, payload.get("kind", "?"), json.dumps(payload),
                 hashlib.sha256(raw).hexdigest()))
        return min(len(lines), EVENTS_CAP)

    def _finish(self, store: Store, eid: str, status: str, error: str | None) -> None:
        store.execute("UPDATE executions SET status=?, error_code=?, finished_utc=? WHERE id=?",
                      (status, error, now_utc(), eid))

    def _run_c(self, store: Store, eid: str, job, src: Path,
               build_out: Path, run_out: Path, cname: str) -> None:
        # Build in the analyzer container (clang-18 + instrumentation shim).
        # Output bind mount: Docker Desktop chowns the dir after container writes,
        # so the orchestrator ONLY READS from it (never writes) — audit F05 lesson.
        build_argv = ["docker", "run", "--rm", "--name", f"cv-build-{eid[:12]}",
                      "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,size=16m",
                      "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                      "--user", "1000:1000", "--memory", "256m", "--pids-limit", "64",
                      "-v", f"{src}:/work:ro", "-v", f"{build_out}:/out",
                      ANALYZER_IMAGE, "python3", "/opt/analyzer/c_build_worker.py",
                      "--file", job["primary_file"], "--out", "/out"]
        b = run_capped(build_argv, BUILD_TIMEOUT_S)
        if b["killed"]:
            # Killing the docker CLI does not stop the build container (M4QA-01).
            subprocess.run(["docker", "rm", "-f", f"cv-build-{eid[:12]}"],
                           capture_output=True, timeout=60)
            self._finish(store, eid, "TIMEOUT", "build timeout")
            return
        manifest_p = build_out / "manifest.json"
        if b["exit_code"] != 0 or not manifest_p.is_file():
            self._finish(store, eid, "FAILED",
                         "C build failed: " + b["stderr"].decode("utf-8", "replace")[:300])
            return
        manifest = json.loads(manifest_p.read_text())
        build_rec = manifest["stages"][0]
        exe_art = next((a for a in build_rec.get("artifacts", [])
                        if a["file"] == "app.bin"), None)
        if not exe_art:
            self._finish(store, eid, "FAILED", "build produced no executable")
            return

        bin_dir = build_out.parent / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        app_bytes = (build_out / "app.bin").read_bytes()
        app_sha = store.put_artifact(app_bytes)
        app_path = bin_dir / "app"
        app_path.write_bytes(app_bytes)
        app_path.chmod(0o755)
        store.execute("UPDATE executions SET binary_sha256=? WHERE id=?",
                      (app_sha, eid))

        # Execute in the minimal runtime container.
        run_argv = ["docker", "run", "--rm", "--name", cname, *_BASE_FLAGS,
                    "-e", "CV_TRACE_OUT=/out/trace.jsonl",
                    "-v", f"{bin_dir}:/app:ro", "-v", f"{run_out}:/out",
                    RUNTIME_IMAGE, "/app/app"]
        symbol_map = _parse_symbols(build_out / "symbols.txt")
        self._execute_and_record(store, eid, run_argv, run_out, cname,
                                 symbol_map=symbol_map)

    def _run_python(self, store: Store, eid: str, job, src: Path,
                    run_out: Path, cname: str) -> None:
        run_argv = ["docker", "run", "--rm", "--name", cname, *_BASE_FLAGS,
                    "-v", f"{src}:/work:ro", "-v", f"{run_out}:/out",
                    RUNTIME_IMAGE, "python3", "/opt/runtime/py_trace_harness.py",
                    "--file", job["primary_file"], "--out", "/out"]
        self._execute_and_record(store, eid, run_argv, run_out, cname,
                                 stdout_from_file=True)

    def _execute_and_record(self, store: Store, eid: str, argv: list[str],
                            run_out: Path, cname: str,
                            symbol_map: list | None = None,
                            stdout_from_file: bool = False) -> None:
        if store.query_one("SELECT cancel_requested FROM executions WHERE id=?",
                           (eid,))["cancel_requested"]:
            self._finish(store, eid, "CANCELLED", None)
            return
        r = run_capped(argv, RUN_TIMEOUT_S)
        if store.query_one("SELECT cancel_requested FROM executions WHERE id=?",
                           (eid,))["cancel_requested"]:
            subprocess.run(["docker", "rm", "-f", cname], capture_output=True, timeout=60)
            self._finish(store, eid, "CANCELLED", None)
            return
        if r["killed"]:
            # Killing the docker CLI does NOT stop the container (M4QA-01: a timed-out
            # `while True` container stayed Up and kept burning CPU). Force-remove it.
            subprocess.run(["docker", "rm", "-f", cname], capture_output=True, timeout=60)
            self._finish(store, eid, "TIMEOUT", "run timeout")
            return
        trace_p = run_out / "trace.jsonl"
        trace_bytes, trace_file_truncated = _read_capped(trace_p, TRACE_FILE_CAP)
        lines = trace_bytes.splitlines()
        meta_payloads: list[dict] = []
        if symbol_map:
            lines = [_resolve_c_addr(ln, symbol_map) for ln in lines]
        for ln in lines:
            try:
                rec = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if rec.get("kind") == "meta":
                meta_payloads.append(rec)
        n_events = self._record_events(store, eid, lines)
        trace_ref = store.put_artifact(trace_bytes) if trace_p.is_file() else None
        # Python harness redirects fd 1 to a file: read the file for stdout.
        # C binary writes to the docker pipe: use run_capped's captured bytes.
        stdout_file_trunc = stderr_file_trunc = False
        if stdout_from_file:
            stdout_bytes, stdout_file_trunc = _read_capped(run_out / "stdout.txt",
                                                           STDOUT_CAP)
            stderr_bytes, stderr_file_trunc = _read_capped(run_out / "stderr.txt",
                                                           STDERR_CAP)
            stderr_bytes = (stderr_bytes if (run_out / "stderr.txt").is_file()
                            else r["stderr"])
        else:
            stdout_bytes, stderr_bytes = r["stdout"], r["stderr"]
        stdout_art = store.put_artifact(stdout_bytes) if stdout_bytes else None
        stderr_art = store.put_artifact(stderr_bytes) if stderr_bytes else None
        meta = _meta_flags(meta_payloads)
        store.execute(
            "UPDATE executions SET status='COMPLETED', exit_code=?, stdout_sha256=?,"
            " stderr_sha256=?, trace_sha256=?, events_count=?, events_truncated=?,"
            " stdout_truncated=?, stderr_truncated=?, finished_utc=? WHERE id=?",
            (r["exit_code"], stdout_art, stderr_art, trace_ref, n_events,
             int(n_events >= EVENTS_CAP or r["stdout_truncated"] or r["stderr_truncated"]
                 or trace_file_truncated or meta["trace"]),
             int(r["stdout_truncated"] or stdout_file_trunc or meta["stdout"]),
             int(r["stderr_truncated"] or stderr_file_trunc or meta["stderr"]),
             now_utc(), eid))

    def cancel(self, execution_id: str) -> str:
        job = self.store.query_one("SELECT status FROM executions WHERE id=?",
                                   (execution_id,))
        if not job:
            raise ExecutionError("NOT_FOUND", "unknown execution id", 404)
        if job["status"] in _TERMINAL:
            return job["status"]
        if job["status"] == "QUEUED":
            self.store.execute(
                "UPDATE executions SET status='CANCELLED', finished_utc=? WHERE id=?",
                (now_utc(), execution_id))
            return "CANCELLED"
        # RUNNING: stop BOTH the run container and any in-flight build container
        # (M4QA-06: a cancel during the C build phase used to leave cv-build running).
        # The flag is committed BEFORE the kill so the worker's post-run check can
        # never miss a cancel that already destroyed the container (the runner used
        # to record COMPLETED for a killed run in that gap). The rm -f is retried
        # briefly: the worker may be milliseconds from starting the container when
        # the first removal lands as a no-op.
        self.store.execute("UPDATE executions SET cancel_requested=1 WHERE id=?",
                           (execution_id,))
        for _ in range(4):
            subprocess.run(["docker", "rm", "-f", f"cv-exec-{execution_id[:12]}"],
                           capture_output=True, timeout=60)
            subprocess.run(["docker", "rm", "-f", f"cv-build-{execution_id[:12]}"],
                           capture_output=True, timeout=60)
            if self.store.query_one(
                    "SELECT status FROM executions WHERE id=?",
                    (execution_id,))["status"] != "RUNNING":
                break  # worker already recorded a terminal state
            time.sleep(0.25)
        return "CANCEL_REQUESTED"


def _meta_flags(meta_payloads: list[dict]) -> dict:
    """In-band truncation markers written by the shim/harness (trusted: they are
    emitted by the pinned container code, not by user source)."""
    return {
        "trace": any(p.get("truncated") is True for p in meta_payloads),
        "stdout": any(p.get("stdout_truncated") is True for p in meta_payloads),
        "stderr": any(p.get("stderr_truncated") is True for p in meta_payloads),
    }


def _read_capped(path: Path, cap: int) -> tuple[bytes, bool]:
    """Read at most `cap` bytes from a container-written file. Container output is
    untrusted: the orchestrator never trusts a file's size (M4QA-02/03)."""
    if not path.is_file():
        return b"", False
    with path.open("rb") as f:
        data = f.read(cap + 1)
    return data[:cap], len(data) > cap


_RUNNERS: dict[int, _ExecRunner] = {}
_RUNNER_LOCK = threading.Lock()


def get_execution_runner(store: Store) -> _ExecRunner:
    key = id(store)
    with _RUNNER_LOCK:
        if key not in _RUNNERS:
            _RUNNERS[key] = _ExecRunner(store)
            _RUNNERS[key]._reconcile_interrupted()
        return _RUNNERS[key]


def create_execution(store: Store, snapshot_id: str, target_id: str) -> dict:
    snap = store.query_one("SELECT * FROM source_snapshots WHERE id=?", (snapshot_id,))
    if not snap:
        raise ExecutionError("NOT_FOUND", "unknown snapshot", 404)
    if snap["origin"] == "github":
        # README §10 / M4-A: imported repositories NEVER auto-run. Explicit
        # user-run of imported code needs the M9 deployment review — fail closed.
        raise ExecutionError("EXECUTION_ORIGIN_BLOCKED",
                             "execution of imported repository code is disabled "
                             "pending independent security review", 403)
    target = store.query_one("SELECT * FROM compilation_targets WHERE id=? AND snapshot_id=?",
                             (target_id, snapshot_id))
    if not target:
        raise ExecutionError("NOT_FOUND", "unknown target for snapshot", 404)
    eligible = target["status"] in ("EXECUTABLE_CANDIDATE", "COMPILATION_CANDIDATE")
    if not eligible:
        raise ExecutionError("NOT_EXECUTABLE",
                             f"target status {target['status']} is not execution-eligible")
    language = "python" if target["kind"].startswith("python") else "c"
    available, reason = None, None
    from app.services.analyzer import docker_status
    available, reason = docker_status()
    if not available:
        eid = new_id()
        store.execute(
            "INSERT INTO executions (id, snapshot_id, target_id, language, primary_file,"
            " status, fingerprint, source_combined_sha256, error_code, created_utc)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (eid, snapshot_id, target_id, language, target["primary_file"], "BLOCKED",
             "unavailable", snap["combined_sha256"], reason, now_utc()))
        return {"execution_id": eid, "status": "BLOCKED", "error": reason, "existed": False}
    fp = f"{snap['combined_sha256']}:{target_id}:{runtime_image_id()}"
    existing = store.query_one(
        "SELECT id, status FROM executions WHERE fingerprint=? AND status IN"
        " ('COMPLETED','RUNNING','QUEUED') ORDER BY created_utc DESC LIMIT 1", (fp,))
    if existing:
        return {"execution_id": existing["id"], "status": existing["status"], "existed": True}
    eid = new_id()
    store.execute(
        "INSERT INTO executions (id, snapshot_id, target_id, language, primary_file,"
        " status, fingerprint, source_combined_sha256, created_utc) VALUES (?,?,?,?,?,?,?,?,?)",
        (eid, snapshot_id, target_id, language, target["primary_file"], "QUEUED", fp,
         snap["combined_sha256"], now_utc()))
    get_execution_runner(store).enqueue(eid)
    return {"execution_id": eid, "status": "QUEUED", "existed": False}
