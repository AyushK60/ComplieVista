"""Stage 4-B execution orchestrator - controlled C/Python execution, traces, replay data.

Separate privilege domain from static analysis: builds happen in the pinned analyzer
container (clang-18 + instrumentation shim); execution happens in the minimal runtime
container. Both run with the restrictive baseline (network none, read-only rootfs,
tmpfs, cap-drop ALL, no-new-privileges, non-root, cpu/mem/pids caps, external timeout,
orchestrator-forced cleanup). No Docker socket in any container; argv arrays only.

Modes (ADR-0007): static analysis (pre-existing), curated/pasted execution - both use
the same restricted runner; pasted execution is admitted only for targets whose
classification and provenance pass admission. GitHub-imported snapshots NEVER execute
in stage 4 (EXECUTION_ORIGIN_BLOCKED - explicit-fail, per the project notes "never auto-run" and
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

from app.core.config import (ANALYSIS_TIMEOUT_S, ANALYZER_IMAGE, DEBUG_IMAGE,
                             RUNTIME_IMAGE)
from app.services.execution_trace import (  # noqa: F401  (re-exported)
    _is_event_line, _meta_flags, _parse_symbols, _read_capped, _resolve_c_addr,
    parse_framed_stream)
from app.services.staging import jobs_root
from app.store.db import Store, new_id, now_utc

RUN_TIMEOUT_S = 30
BUILD_TIMEOUT_S = 90
STDOUT_CAP = 1024 * 1024
STDERR_CAP = 1024 * 1024
EVENTS_CAP = 5000
# the Python trace harness multiplexes trace/memory/process/stdout over
# the container stdout pipe (protected channel, no writable /out mount); the
# framed stream needs a larger pipe cap than a plain stdout capture.
FRAMED_STDOUT_CAP = 32 * 1024 * 1024
# Defensive read cap for container-written files: the shim/harness cap their own
# output in-band, but the orchestrator never trusts a file's size.
TRACE_FILE_CAP = 8 * 1024 * 1024
# Stage 5 observation caps: container files are capped in-harness; the orchestrator
# additionally reads through defensive caps and stores bounded rows.
OBS_FILE_CAP = 4 * 1024 * 1024
MEMORY_ROW_CAP = 2000
PROCESS_ROW_CAP = 2000
MAX_CONCURRENT = 1

# Trace trust contract (Stage 8, ADR-0011): a trace is CURATED_COOPERATIVE only
# when the snapshot origin is the curated demo/fixture manifests (regression-
# tested not to tamper with instrumentation). Everything else - pasted, uploaded
# - is UNTRUSTED_TARGET: the traced program could attempt to alter or disable
# observation, so its events are never labeled guaranteed-genuine.
TRUST_CURATED = "CURATED_COOPERATIVE"
TRUST_UNTRUSTED = "UNTRUSTED_TARGET"
CHANNEL_FRAMED = "framed_stdout_pipe_no_writable_mount"
CHANNEL_FILE = "container_file"

_BASE_FLAGS = [
    "--rm", "--network", "none", "--read-only",
    "--tmpfs", "/tmp:rw,size=16m,noexec",
    "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges",
    "--user", "1000:1000",
    "--memory", "256m", "--cpus", "0.5", "--pids-limit", "64",
]

TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BLOCKED"}
_TERMINAL = TERMINAL


class ExecutionError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def resolve_image_id(tag: str) -> str | None:
    """Immutable identity of `tag` RIGHT NOW (finding). Returns the sha256 image
    ID, or None when the daemon is unreachable or the tag does not resolve.
    Callers MUST fail closed on None and launch argv with the returned ID -
    never with the mutable tag."""
    try:
        out = subprocess.run(["docker", "image", "inspect", "-f", "{{.Id}}", tag],
                             capture_output=True, timeout=30)
        line = out.stdout.decode().strip()
        if out.returncode == 0 and line.startswith("sha256:"):
            return line
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def trace_trust_for(origin: str | None) -> str:
    """Honest per-run trust label (finding): only curated manifests are
    regression-tested cooperative targets; pasted/uploaded code is untrusted."""
    return TRUST_CURATED if origin == "curated" else TRUST_UNTRUSTED


def _rmtree_or_privileged(job_dir: Path) -> None:
    """Remove a job dir; shared robust helper in staging (Stage 4 review: retry + visible
    fallback failure)."""
    from app.services.staging import remove_disposable_dir
    remove_disposable_dir(job_dir, RUNTIME_IMAGE)



def _store_observations(store: Store, eid: str, kind: str, path: Path,
                        row_cap: int) -> tuple[int, str | None, bool]:
    """Read a container-written observation file (defensively capped), store the
    artifact and bounded, checksummed rows. Returns (rows, artifact_sha, truncated)."""
    data, file_truncated = _read_capped(path, OBS_FILE_CAP)
    if not data:
        return 0, None, False
    artifact = store.put_artifact(data)
    lines = data.splitlines()
    truncated = file_truncated or len(lines) > row_cap
    seq = 0
    for raw in lines[:row_cap]:
        seq += 1
        try:
            payload = json.loads(raw)
        except ValueError:  # JSONDecodeError and UnicodeDecodeError (Stage 5: never
            # let one malformed container line abort the whole execution)
            payload = {"kind": "unparsed",
                       "raw": raw[:300].decode("utf-8", "replace")}
        store.execute(
            "INSERT OR REPLACE INTO execution_observations"
            " (execution_id, kind, seq, payload_json, sha256) VALUES (?,?,?,?,?)",
            (eid, kind, seq, json.dumps(payload), hashlib.sha256(raw).hexdigest()))
    return min(len(lines), row_cap), artifact, truncated


def _store_stream_rows(store: Store, eid: str, kind: str, data: bytes,
                       row_cap: int) -> tuple[int, str | None, bool]:
    """Store a merged in-memory observation stream (bounded rows, checksummed)."""
    if not data:
        return 0, None, False
    artifact = store.put_artifact(data)
    lines = data.splitlines()
    truncated = len(lines) > row_cap
    seq = 0
    for raw in lines[:row_cap]:
        seq += 1
        try:
            payload = json.loads(raw)
        except ValueError:  # JSONDecodeError and UnicodeDecodeError (Stage 5: never
            # let one malformed container line abort the whole execution)
            payload = {"kind": "unparsed",
                       "raw": raw[:300].decode("utf-8", "replace")}
        store.execute(
            "INSERT OR REPLACE INTO execution_observations"
            " (execution_id, kind, seq, payload_json, sha256) VALUES (?,?,?,?,?)",
            (eid, kind, seq, json.dumps(payload), hashlib.sha256(raw).hexdigest()))
    return min(len(lines), row_cap), artifact, truncated


def _store_memory_bytes(store: Store, eid: str,
                        data: bytes) -> tuple[int, str | None, bool]:
    """Store a merged in-memory memory-observation stream (bounded rows)."""
    return _store_stream_rows(store, eid, "memory", data, MEMORY_ROW_CAP)


def _host_pid_sampler(cname: str, stop: threading.Event) -> list[int]:
    """Best-effort host-side PID of the container as long as it exists (Stage 5-D:
    distinguishes container PID namespace from host PID). Returns [pid] or []."""
    while not stop.is_set():
        r = subprocess.run(["docker", "inspect", "-f", "{{.State.Pid}}", cname],
                           capture_output=True, timeout=20)
        pid = r.stdout.decode().strip()
        if pid.isdigit() and int(pid) > 0:
            return [int(pid)]
        stop.wait(0.3)
    return []


def run_capped(argv: list[str], timeout: int,
               stdout_cap: int = STDOUT_CAP) -> dict:
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
        # pass the effective caps (run_capped's stdout_cap param wires through
        # here - the framed trace channel needs the larger cap)
        threading.Thread(target=lambda: pump(proc.stdout, sink_out, stdout_cap,
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
        # mop up orphaned execution job dirs (e.g. a previous process was
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
        # resolve the IMMUTABLE image IDs immediately before use and
        # launch argv with those IDs, never the mutable tags. Fail closed when
        # resolution fails or the tag no longer matches the identity recorded at
        # submission (TOCTOU: tag mutated/repainted between request and run).
        profile = job["profile"] or "standard"
        exec_tag = DEBUG_IMAGE if profile == "debug" else RUNTIME_IMAGE
        build_needed = profile in ("standard", "demo-link")
        exec_ref = resolve_image_id(exec_tag)
        build_ref = resolve_image_id(ANALYZER_IMAGE) if build_needed else exec_ref
        if exec_ref is None or build_ref is None:
            store.execute("UPDATE executions SET status='BLOCKED',"
                          " error_code='IMAGE_ID_UNAVAILABLE', finished_utc=?"
                          " WHERE id=?", (now_utc(), eid))
            return
        try:
            requested = json.loads(job["requested_image_ids"]) \
                if job["requested_image_ids"] else {}
        except ValueError:
            requested = {}
        if (requested.get("exec") and exec_ref != requested["exec"]) or \
                (build_needed and requested.get("build")
                 and build_ref != requested["build"]):
            store.execute("UPDATE executions SET status='BLOCKED',"
                          " error_code='IMAGE_ID_CHANGED', finished_utc=?"
                          " WHERE id=?", (now_utc(), eid))
            return
        store.execute("UPDATE executions SET status='RUNNING', started_utc=?,"
                      " image_id=?, build_image_id=? WHERE id=?",
                      (now_utc(), exec_ref, build_ref if build_needed else None,
                       eid))

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
            # a cancel that arrives while the job is starting must not
            # launch a container afterwards (previously the container ran its full
            # wall-clock before cancel_requested was observed).
            if store.query_one("SELECT cancel_requested FROM executions WHERE id=?",
                               (eid,))["cancel_requested"]:
                self._finish(store, eid, "CANCELLED", None)
                return
            if profile == "debug":
                self._run_debug(store, eid, job, src, run_out, cname, exec_ref)
            elif profile == "demo-link":
                self._run_demo_link(store, eid, job, src, build_out, run_out,
                                    cname, build_ref, exec_ref)
            elif job["language"] == "c":
                self._run_c(store, eid, job, src, build_out, run_out, cname,
                            build_ref, exec_ref)
            else:
                self._run_python(store, eid, job, src, run_out, cname, exec_ref)
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
               build_out: Path, run_out: Path, cname: str,
               build_ref: str, exec_ref: str) -> None:
        # Build in the analyzer container (clang-18 + instrumentation shim).
        # Output bind mount: Docker Desktop chowns the dir after container writes,
        # so the orchestrator ONLY READS from it (never writes) - audit F05 lesson.
        # immutable image IDs resolved by the runner, not tags.
        build_argv = ["docker", "run", "--rm", "--name", f"cv-build-{eid[:12]}",
                      "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,size=16m",
                      "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                      "--user", "1000:1000", "--memory", "256m", "--pids-limit", "64",
                      "-v", f"{src}:/work:ro", "-v", f"{build_out}:/out",
                      build_ref, "python3", "/opt/analyzer/c_build_worker.py",
                      "--file", job["primary_file"], "--out", "/out"]
        b = run_capped(build_argv, BUILD_TIMEOUT_S)
        if b["killed"]:
            # Killing the docker CLI does not stop the build container.
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
            # Stage 7 Error Microscope: surface the real compiler/linker diagnostic
            # (e.g. "undefined reference"), not just "no executable".
            err_tail = ""
            bs = build_out / "build_stderr.txt"
            if bs.is_file():
                err_tail = bs.read_text("utf-8", "replace")[-300:]
            self._finish(store, eid, "FAILED", "C build failed: " + err_tail)
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

        # Execute in the minimal runtime container. Stage 5: the shim additionally
        # interposes the allocator (memory.jsonl) and samples /proc (process.jsonl).
        run_argv = ["docker", "run", "--rm", "--name", cname, *_BASE_FLAGS,
                    "-e", "CV_TRACE_OUT=/out/trace.jsonl",
                    "-e", "CV_MEM_OUT=/out/memory.jsonl",
                    "-e", "CV_PROC_OUT=/out/process.jsonl",
                    "-v", f"{bin_dir}:/app:ro", "-v", f"{run_out}:/out",
                    exec_ref, "/app/app"]
        symbol_map = _parse_symbols(build_out / "symbols.txt")
        self._execute_and_record(store, eid, run_argv, run_out, cname,
                                 symbol_map=symbol_map)

    def _run_demo_link(self, store: Store, eid: str, job, src: Path,
                       build_out: Path, run_out: Path, cname: str,
                       build_ref: str, exec_ref: str) -> None:
        """Stage 7 C-05: compile ALL curated TUs, link with the shim, then run the
        linked binary exactly like the standard C path (instrumented trace)."""
        from app.services.demos import _demo_link_tus
        snap = store.query_one(
            "SELECT combined_sha256 FROM source_snapshots WHERE id=?",
            (job["snapshot_id"],))
        entry = _demo_link_tus()[snap["combined_sha256"]]
        tus = json.dumps(entry["tus"])
        bargv = ["docker", "run", "--rm", "--name", f"cv-build-{eid[:12]}",
                 "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,size=16m",
                 "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                 "--user", "1000:1000", "--memory", "256m", "--pids-limit", "64",
                 "-v", f"{src}:/work:ro", "-v", f"{build_out}:/out",
                 build_ref, "python3", "/opt/analyzer/c_link_worker.py",
                 "--primary", entry["primary_file"], "--tus", tus, "--out", "/out"]
        b = run_capped(bargv, BUILD_TIMEOUT_S)
        if b["killed"]:
            subprocess.run(["docker", "rm", "-f", f"cv-build-{eid[:12]}"],
                           capture_output=True, timeout=60)
            self._finish(store, eid, "TIMEOUT", "build timeout")
            return
        manifest_p = build_out / "manifest.json"
        if not manifest_p.is_file():
            self._finish_failed_build(store, eid, b)
            return
        link_manifest = json.loads(manifest_p.read_text())
        if link_manifest.get("steps", {}).get("link", {}).get("exit_code") != 0:
            self._finish_failed_build(store, eid, b, "C link failed")
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
        run_argv = ["docker", "run", "--rm", "--name", cname, *_BASE_FLAGS,
                    "-e", "CV_TRACE_OUT=/out/trace.jsonl",
                    "-e", "CV_MEM_OUT=/out/memory.jsonl",
                    "-e", "CV_PROC_OUT=/out/process.jsonl",
                    "-v", f"{bin_dir}:/app:ro", "-v", f"{run_out}:/out",
                    exec_ref, "/app/app"]
        symbol_map = _parse_symbols(build_out / "symbols.txt")
        self._execute_and_record(store, eid, run_argv, run_out, cname,
                                 symbol_map=symbol_map)

    def _finish_failed_build(self, store: Store, eid: str,
                             b: dict, prefix: str = "C build failed") -> None:
        self._finish(store, eid, "FAILED",
                     prefix + ": " + b["stderr"].decode("utf-8", "replace")[:300])

    def _run_debug(self, store: Store, eid: str, job, src: Path,
                   run_out: Path, cname: str, exec_ref: str) -> None:
        """Stage 5-B curated debug profile: gdb frame/variable/pointer observations for
        allowlisted curated C fixtures only (ADR-0008). One container, no privilege
        expansion (gdb traces its own child under cap-drop ALL / no-new-privileges)."""
        from app.services.curated import curated_entry
        snap = store.query_one("SELECT combined_sha256 FROM source_snapshots WHERE id=?",
                               (job["snapshot_id"],))
        entry = curated_entry(snap["combined_sha256"])
        if not entry:
            self._finish(store, eid, "BLOCKED", "curated manifest entry vanished")
            return
        run_argv = ["docker", "run", "--rm", "--name", cname, *_BASE_FLAGS,
                    "-v", f"{src}:/work:ro", "-v", f"{run_out}:/out",
                    exec_ref, "python3", "/opt/debug/c_debug_worker.py",
                    "--file", job["primary_file"], "--out", "/out",
                    "--bp", json.dumps(entry["breakpoints"])]
        self._execute_and_record(store, eid, run_argv, run_out, cname,
                                 stdout_from_file=False, profile="debug")

    def _execute_and_record(self, store: Store, eid: str, argv: list[str],
                            run_out: Path, cname: str,
                            symbol_map: list | None = None,
                            stdout_from_file: bool = False,
                            profile: str = "standard",
                            framed: bool = False) -> None:
        if store.query_one("SELECT cancel_requested FROM executions WHERE id=?",
                           (eid,))["cancel_requested"]:
            self._finish(store, eid, "CANCELLED", None)
            return
        trace_channel = CHANNEL_FRAMED if framed else CHANNEL_FILE
        store.execute("UPDATE executions SET trace_channel=? WHERE id=?",
                      (trace_channel, eid))
        # best-effort host-side PID of the container while it exists.
        pid_stop = threading.Event()
        pid_result: list[int] = []
        pid_thread = threading.Thread(target=lambda: pid_result.extend(
            _host_pid_sampler(cname, pid_stop)), daemon=True)
        pid_thread.start()
        try:
            r = run_capped(argv, RUN_TIMEOUT_S,
                           stdout_cap=FRAMED_STDOUT_CAP if framed else STDOUT_CAP)
        finally:
            pid_stop.set()
            pid_thread.join(timeout=20)
        if store.query_one("SELECT cancel_requested FROM executions WHERE id=?",
                           (eid,))["cancel_requested"]:
            subprocess.run(["docker", "rm", "-f", cname], capture_output=True, timeout=60)
            self._finish(store, eid, "CANCELLED", None)
            return
        if r["killed"]:
            # Killing the docker CLI does NOT stop the container (stage 4 review-01: a timed-out
            # `while True` container stayed Up and kept burning CPU). Force-remove it.
            subprocess.run(["docker", "rm", "-f", cname], capture_output=True, timeout=60)
            self._finish(store, eid, "TIMEOUT", "run timeout")
            return

        if framed:
            # Protected channel (finding): artifacts arrive as harness frames.
            frames = parse_framed_stream(r["stdout"])
            meta_fr = frames["meta"] or {}
            meta_record = {"kind": "meta",
                           "python": meta_fr.get("python"),
                           "events": meta_fr.get("events"),
                           "truncated": meta_fr.get("truncated"),
                           "stdout_truncated": meta_fr.get("stdout_truncated"),
                           "max_events": meta_fr.get("max_events"),
                           "schema": "m8g0",
                           "memory_records": meta_fr.get("memory_records"),
                           "memory_truncated": meta_fr.get("memory_truncated"),
                           "trace_disabled_by_target":
                               meta_fr.get("trace_disabled_by_target"),
                           "channel_frames_dropped":
                               meta_fr.get("channel_frames_dropped"),
                           "channel": CHANNEL_FRAMED,
                           "foreign_frames": frames["foreign"],
                           "integrity": frames["integrity"]}
            lines = frames["trace"] + [json.dumps(meta_record).encode()]
            trace_bytes = b"\n".join(lines) + (b"\n" if lines else b"")
            trace_file_truncated = False
            trace_ref = store.put_artifact(trace_bytes) if trace_bytes.strip() \
                else None
            meta_payloads: list[dict] = [meta_record]
            n_events = self._record_events(store, eid, frames["trace"])
            mem_rows, mem_art, mem_trunc = _store_stream_rows(
                store, eid, "memory", b"\n".join(frames["memory"]),
                MEMORY_ROW_CAP)
            proc_rows, proc_art, proc_trunc = _store_stream_rows(
                store, eid, "process", b"\n".join(frames["process"]),
                PROCESS_ROW_CAP)
        else:
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
            # C-channel integrity (finding): verify the shim's final trace_meta
            # record - count consistency; absence of the record (e.g. an abrupt
            # kill or tampering) is SUSPECT, never silently promoted.
            c_integrity = "SUSPECT"
            c_meta_rec: dict = {"kind": "trace_meta_record", "channel": CHANNEL_FILE}
            if lines and lines[-1]:
                try:
                    last = json.loads(lines[-1])
                    if last.get("kind") == "trace_meta" and \
                            isinstance(last.get("events"), int):
                        n_ev = sum(
                            1 for ln2 in lines[:-1]
                            if ln2 and _is_event_line(ln2))
                        if last["events"] == n_ev:
                            c_integrity = "CONSISTENT"
                        c_meta_rec |= {"events": last["events"],
                                       "observed_event_lines": n_ev,
                                       "truncated": last.get("truncated"),
                                       "observer": "c_trace_shim"}
                except json.JSONDecodeError:
                    pass
            meta_payloads.append(c_meta_rec)
            # Events are recorded from the ORIGINAL shim lines; the meta record is
            # appended to the stored artifact afterwards (not counted as an event).
            n_events = self._record_events(store, eid, lines)
            lines = lines + [json.dumps(
                c_meta_rec | {"integrity": c_integrity}).encode()]
            trace_bytes = b"\n".join(lines) + (b"\n" if lines else b"")
            trace_ref = store.put_artifact(trace_bytes) if trace_p.is_file() else None

            # bounded observation capture (memory + process streams).
            mem_rows, mem_art, mem_trunc = self._capture_memory(
                store, eid, run_out, profile)
            proc_rows, proc_art, proc_trunc = _store_observations(
                store, eid, "process", run_out / "process.jsonl", PROCESS_ROW_CAP)

        # Python harness frames carry stdout; C binary writes to the docker pipe.
        stdout_file_trunc = stderr_file_trunc = False
        if framed:
            stdout_bytes, stdout_file_trunc = frames["stdout"], \
                bool(meta_fr.get("stdout_truncated")) or r["stdout_truncated"]
            stderr_bytes, stderr_file_trunc = r["stderr"], r["stderr_truncated"]
        elif stdout_from_file:
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
        integrity = frames["integrity"] if framed else c_integrity
        store.execute(
            "UPDATE executions SET status='COMPLETED', exit_code=?, stdout_sha256=?,"
            " stderr_sha256=?, trace_sha256=?, events_count=?, events_truncated=?,"
            " stdout_truncated=?, stderr_truncated=?, finished_utc=?, host_pid=?,"
            " memory_sha256=?, process_sha256=?, memory_count=?, process_count=?,"
            " trace_integrity=?, trace_meta_json=? WHERE id=?",
            (r["exit_code"], stdout_art, stderr_art, trace_ref, n_events,
             int(n_events >= EVENTS_CAP or r["stdout_truncated"] or r["stderr_truncated"]
                 or trace_file_truncated or meta["trace"]),
             int(r["stdout_truncated"] or stdout_file_trunc or meta["stdout"]),
             int(r["stderr_truncated"] or stderr_file_trunc or meta["stderr"]),
             now_utc(),
             pid_result[0] if pid_result else None,
             mem_art, proc_art, mem_rows, proc_rows,
             integrity, json.dumps(meta_record if framed else c_meta_rec), eid))
        _ = (mem_trunc, proc_trunc)  # stored rows are already bounded by row caps

    def _capture_memory(self, store: Store, eid: str, run_out: Path,
                        profile: str) -> tuple[int, str | None, bool]:
        """Store the memory observation stream; standard C runs always get the
        honest debugger-unavailable marker first (even for curated snapshots run
        in the standard profile - no gdb ran there). Never writes into the
        container output dir (orchestrator only reads it)."""
        job = store.query_one("SELECT language FROM executions WHERE id=?", (eid,))
        p = run_out / "memory.jsonl"
        if profile == "standard" and job and job["language"] == "c":
            marker = {"kind": "unavailable",
                      "topic": "c_frame_locals_and_pointer_dereferences",
                      "observation_class": "unavailable",
                      "reason": "debugger-based capture (gdb) runs only in the "
                                "curated debug profile (ADR-0008); allocator "
                                "interposition still provides real heap evidence "
                                "for this run"}
            pre = json.dumps(marker).encode() + b"\n"
            data = pre + p.read_bytes() if p.is_file() else pre
            return _store_memory_bytes(store, eid, data)
        return _store_observations(store, eid, "memory", p, MEMORY_ROW_CAP)

    def _run_python(self, store: Store, eid: str, job, src: Path,
                    run_out: Path, cname: str, exec_ref: str) -> None:
        # Stage 8 finding: NO writable /out mount - the untrusted target cannot
        # write trace artifacts. The harness multiplexes all observations over
        # the container stdout pipe (protected channel); the orchestrator parses
        # and stores them host-side.
        run_argv = ["docker", "run", "--rm", "--name", cname, *_BASE_FLAGS,
                    "-v", f"{src}:/work:ro",
                    exec_ref, "python3", "/opt/runtime/py_trace_harness.py",
                    "--file", job["primary_file"]]
        self._execute_and_record(store, eid, run_argv, run_out, cname,
                                 stdout_from_file=True, framed=True)

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
        # (stage 4 review-06: a cancel during the C build phase used to leave cv-build running).
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


_RUNNERS: dict[int, _ExecRunner] = {}
_RUNNER_LOCK = threading.Lock()


def get_execution_runner(store: Store) -> _ExecRunner:
    key = id(store)
    with _RUNNER_LOCK:
        if key not in _RUNNERS:
            _RUNNERS[key] = _ExecRunner(store)
            _RUNNERS[key]._reconcile_interrupted()
        return _RUNNERS[key]


def create_execution(store: Store, snapshot_id: str, target_id: str,
                     profile: str = "standard") -> dict:
    snap = store.query_one("SELECT * FROM source_snapshots WHERE id=?", (snapshot_id,))
    if not snap:
        raise ExecutionError("NOT_FOUND", "unknown snapshot", 404)
    trust = trace_trust_for(snap["origin"])
    if snap["origin"] == "github":
        # the project notes / Stage 4-A: imported repositories NEVER auto-run. Explicit
        # user-run of imported code needs the stage 9 deployment review - fail closed.
        raise ExecutionError("EXECUTION_ORIGIN_BLOCKED",
                             "execution of imported repository code is disabled "
                             "pending independent security review", 403)
    if profile not in ("standard", "debug", "demo-link"):
        raise ExecutionError("INVALID_PROFILE", f"unknown profile {profile!r}", 400)
    target = store.query_one("SELECT * FROM compilation_targets WHERE id=? AND snapshot_id=?",
                             (target_id, snapshot_id))
    if not target:
        raise ExecutionError("NOT_FOUND", "unknown target for snapshot", 404)
    eligible = target["status"] in ("EXECUTABLE_CANDIDATE", "COMPILATION_CANDIDATE")
    if not eligible:
        raise ExecutionError("NOT_EXECUTABLE",
                             f"target status {target['status']} is not execution-eligible")
    language = "python" if target["kind"].startswith("python") else "c"
    # Stage 5-B (ADR-0008): the gdb debug profile is admitted ONLY for curated
    # allowlisted C fixtures - content-hash allowlist computed from the pinned
    # manifest, never from user input. Pasted/untrusted code: fail closed.
    if profile == "debug":
        from app.services.curated import curated_entry
        if language != "c" or not curated_entry(snap["combined_sha256"]):
            raise ExecutionError(
                "DEBUG_PROFILE_BLOCKED",
                "debugger capture is restricted to curated allowlisted C fixtures "
                "(ADR-0008); pasted code keeps an explicit unavailable state", 403)
    if profile == "demo-link":
        # Stage 7 C-05: multi-TU compile+link for curated demo-manifest snapshots
        # only; the TU list comes from the versioned manifest, never from input.
        from app.services.demos import _demo_link_tus
        if language != "c" or snap["combined_sha256"] not in _demo_link_tus():
            raise ExecutionError(
                "DEMO_LINK_BLOCKED",
                "multi-file linking is restricted to curated demo programs", 403)
    available, reason = None, None
    from app.services.analyzer import docker_status
    available, reason = docker_status()
    if not available:
        eid = new_id()
        store.execute(
            "INSERT INTO executions (id, snapshot_id, target_id, language, primary_file,"
            " status, fingerprint, source_combined_sha256, error_code, created_utc,"
            " profile, trace_trust, trace_channel)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid, snapshot_id, target_id, language, target["primary_file"], "BLOCKED",
             "unavailable", snap["combined_sha256"], reason, now_utc(), profile,
             trust, CHANNEL_FRAMED if language == "python" else CHANNEL_FILE))
        return {"execution_id": eid, "status": "BLOCKED", "error": reason, "existed": False}
    exec_tag = DEBUG_IMAGE if profile == "debug" else RUNTIME_IMAGE
    exec_ref = resolve_image_id(exec_tag)
    build_needed = language == "c"  # standard/demo-link C builds use the analyzer image
    build_ref = resolve_image_id(ANALYZER_IMAGE) if build_needed else None
    if exec_ref is None or (build_needed and build_ref is None):
        eid = new_id()
        store.execute(
            "INSERT INTO executions (id, snapshot_id, target_id, language, primary_file,"
            " status, fingerprint, source_combined_sha256, error_code, created_utc,"
            " profile, trace_trust, trace_channel)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid, snapshot_id, target_id, language, target["primary_file"], "BLOCKED",
             "unavailable", snap["combined_sha256"], "IMAGE_ID_UNAVAILABLE",
             now_utc(), profile, trust, CHANNEL_FRAMED if language == "python"
             else CHANNEL_FILE))
        return {"execution_id": eid, "status": "BLOCKED",
                "error": "IMAGE_ID_UNAVAILABLE", "existed": False}
    requested_ids = json.dumps(
        {"exec": exec_ref, "build": build_ref} if build_needed
        else {"exec": exec_ref})
    fp = f"{snap['combined_sha256']}:{target_id}:{exec_ref}:{profile}"
    existing = store.query_one(
        "SELECT id, status FROM executions WHERE fingerprint=? AND status IN"
        " ('COMPLETED','RUNNING','QUEUED') ORDER BY created_utc DESC LIMIT 1", (fp,))
    if existing:
        return {"execution_id": existing["id"], "status": existing["status"], "existed": True}
    eid = new_id()
    store.execute(
        "INSERT INTO executions (id, snapshot_id, target_id, language, primary_file,"
        " status, fingerprint, source_combined_sha256, created_utc, profile,"
        " requested_image_ids, trace_trust, trace_channel)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (eid, snapshot_id, target_id, language, target["primary_file"], "QUEUED", fp,
         snap["combined_sha256"], now_utc(), profile, requested_ids, trust,
         CHANNEL_FRAMED if language == "python" else CHANNEL_FILE))
    get_execution_runner(store).enqueue(eid)
    return {"execution_id": eid, "status": "QUEUED", "existed": False}
