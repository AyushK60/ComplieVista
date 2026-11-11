"""Stage 6 OptimizationLab / benchmark / pair-comparison orchestrator (ADR-0009).

Reuses the established patterns (single bounded worker thread, argv-array docker
invocations, restricted baseline flags, run_capped with byte caps, defensive
reads, forced container cleanup) - NOT a second executor: opt builds compile in
the pinned analyzer image, benchmark timing runs in the pinned runtime image on
UNINSTRUMENTED binaries, and pair comparison reuses the stage 4 execution pipeline
(create_execution) end-to-end.

No arbitrary compilation flags: worker flags are fixed and recorded verbatim.
GitHub-imported snapshots are refused (fail-closed), like executions.
"""
from __future__ import annotations

import hashlib
import json
import queue
import subprocess
import threading
import time
from pathlib import Path

from app.core.config import ANALYZER_IMAGE
from app.services.analyzer import docker_status
from app.services.execution import (_read_capped, _BASE_FLAGS, RUNTIME_IMAGE,
                                    ExecutionError, create_execution,
                                    get_execution_runner, resolve_image_id)
from app.services.staging import jobs_root, remove_disposable_dir
from app.store.db import Store, new_id, now_utc

EXP_TIMEOUT_S = 300
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BLOCKED"}
ARTIFACT_TEXT_CAP = 64 * 1024
POLICY_VERSION = "m6.experiments.v1"

ARTIFACT_TEXT_KINDS = {"ir": "ir.ll", "asm": "asm.s", "symbols": "symbols.txt"}


class ExperimentError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _stage(store: Store, eid: str, stage: str, availability: str,
           result: dict, artifact: str | None = None,
           duration_ms: int | None = None) -> None:
    store.execute(
        "INSERT OR REPLACE INTO experiment_stages"
        " (experiment_id, stage, availability, result_json, artifact_sha256,"
        " duration_ms) VALUES (?,?,?,?,?,?)",
        (eid, stage, availability, json.dumps(result), artifact, duration_ms))


class _ExperimentRunner:
    """Single bounded worker thread for experiments."""

    def __init__(self, store: Store):
        self.store = store
        self.q: queue.Queue[str] = queue.Queue()
        threading.Thread(target=self._loop, daemon=True, name="experiment-0").start()

    def _reconcile_interrupted(self) -> None:
        for r in self.store.query("SELECT id FROM experiments WHERE status='RUNNING'"):
            self.store.execute(
                "UPDATE experiments SET status='FAILED',"
                " error_code='INTERRUPTED_BY_RESTART', finished_utc=? WHERE id=?",
                (now_utc(), r["id"]))
        for r in self.store.query("SELECT id FROM experiments WHERE status='QUEUED'"):
            self.q.put(r["id"])

    def enqueue(self, eid: str) -> None:
        self.q.put(eid)

    def _loop(self) -> None:
        while True:
            eid = self.q.get()
            try:
                self._run(eid)
            except Exception as e:  # noqa: BLE001
                import traceback
                tb = traceback.format_exc().splitlines()[-1][:200]
                self.store.execute(
                    "UPDATE experiments SET status='FAILED', error_code=?,"
                    " finished_utc=? WHERE id=?",
                    (f"WORKER:{type(e).__name__}: {tb}", now_utc(), eid))

    def _materialize(self, store: Store, snapshot_id: str, job_dir: Path) -> Path:
        src = job_dir / "src"
        src.mkdir(parents=True, exist_ok=True)
        for f in store.query("SELECT rel_path, content_sha256 FROM source_files"
                             " WHERE snapshot_id=?", (snapshot_id,)):
            dest = src / f["rel_path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(store.get_artifact(f["content_sha256"]))
        return src

    def _run(self, eid: str) -> None:
        store = self.store
        job = store.query_one("SELECT * FROM experiments WHERE id=?", (eid,))
        if not job or job["status"] != "QUEUED":
            return
        if job["cancel_requested"]:
            store.execute("UPDATE experiments SET status='CANCELLED', finished_utc=?"
                          " WHERE id=?", (now_utc(), eid))
            return
        available, reason = docker_status()
        if not available:
            store.execute("UPDATE experiments SET status='BLOCKED',"
                          " error_code='DOCKER_UNAVAILABLE', finished_utc=? WHERE id=?",
                          (now_utc(), eid))
            return
        # launch OptimizationLab/benchmark containers with the IMMUTABLE
        # image IDs resolved right now, never the mutable tags; fail closed when
        # resolution fails or the tag no longer matches the submission-time ID.
        build_ref = resolve_image_id(ANALYZER_IMAGE)
        exec_ref = resolve_image_id(RUNTIME_IMAGE)
        if build_ref is None or exec_ref is None:
            store.execute("UPDATE experiments SET status='BLOCKED',"
                          " error_code='IMAGE_ID_UNAVAILABLE', finished_utc=?"
                          " WHERE id=?", (now_utc(), eid))
            return
        try:
            requested = json.loads(job["requested_image_ids"]) \
                if job["requested_image_ids"] else {}
        except ValueError:
            requested = {}
        if (requested.get("build") and build_ref != requested["build"]) or \
                (requested.get("exec") and exec_ref != requested["exec"]):
            store.execute("UPDATE experiments SET status='BLOCKED',"
                          " error_code='IMAGE_ID_CHANGED', finished_utc=?"
                          " WHERE id=?", (now_utc(), eid))
            return
        store.execute("UPDATE experiments SET status='RUNNING', started_utc=? WHERE id=?",
                      (now_utc(), eid))
        job_dir = jobs_root() / f"experiment-{eid[:12]}"
        try:
            config = json.loads(job["config_json"])
            if job["kind"] == "opt":
                self._run_opt(store, eid, job, config, job_dir, build_ref)
            elif job["kind"] == "bench":
                self._run_bench(store, eid, job, config, job_dir, build_ref,
                                exec_ref)
            elif job["kind"] == "compare":
                self._run_compare(store, eid, job, config)
        finally:
            remove_disposable_dir(job_dir, ANALYZER_IMAGE)

    # ---------------- stage 6-A: optimization builds ----------------
    def _run_opt(self, store: Store, eid: str, job, config: dict,
                 job_dir: Path, build_ref: str) -> None:
        src = self._materialize(store, job["snapshot_id"], job_dir)
        out = job_dir / "out"
        out.mkdir(exist_ok=True)
        cname = f"cv-exp-{eid[:12]}"
        argv = ["docker", "run", "--rm", "--name", cname, *_BASE_FLAGS,
                "-v", f"{src}:/work:ro", "-v", f"{out}:/out",
                build_ref, "python3", "/opt/analyzer/c_opt_worker.py",
                "--file", self._primary(store, job), "--out", "/out"]
        r = self._run_capped_or_timeout(argv, cname, eid)
        if r is None:
            return
        manifest_p = out / "manifest.json"
        if not manifest_p.is_file():
            self._finish_failed(store, eid, "opt worker produced no manifest"
                                + (": " + r["stderr"].decode("utf-8", "replace")[:200]))
            return
        manifest = json.loads(manifest_p.read_text())
        for level in ("O0", "O1", "O2"):
            rec = manifest["levels"].get(level, {})
            result = {"flags": rec.get("flags"), "steps": rec.get("steps", {}),
                      "exe_bytes": rec.get("exe_bytes"), "ok": rec.get("ok"),
                      "remarks_available": rec.get("remarks_available", False),
                      "tool": manifest.get("tool"),
                      "artifacts": rec.get("artifacts", [])}
            # store bounded text artifacts for diffing (ir/asm/symbols)
            for kind, fname in ARTIFACT_TEXT_KINDS.items():
                p = out / level / fname
                data, trunc = _read_capped(p, ARTIFACT_TEXT_CAP)
                if data:
                    sha = store.put_artifact(data)
                    result[kind] = {"sha256": sha, "bytes": len(data),
                                    "truncated": trunc or len(data) >= ARTIFACT_TEXT_CAP}
            _stage(store, eid, level, "AVAILABLE" if rec.get("ok") else "UNAVAILABLE",
                   result)
        store.execute("UPDATE experiments SET status='COMPLETED', finished_utc=?,"
                      " result_sha256=? WHERE id=?",
                      (now_utc(), store.put_artifact(manifest_p.read_bytes()), eid))

    def _primary(self, store: Store, job) -> str:
        row = store.query_one("SELECT primary_file FROM compilation_targets WHERE id=?",
                              (job["target_id"],))
        return row["primary_file"]

    # ---------------- stage 6-D: benchmarks ----------------
    def _run_bench(self, store: Store, eid: str, job, config: dict,
                   job_dir: Path, build_ref: str, exec_ref: str) -> None:
        src = self._materialize(store, job["snapshot_id"], job_dir)
        out = job_dir / "out"
        out.mkdir(exist_ok=True)
        primary = self._primary(store, job)
        language = "python" if config.get("language") == "python" else "c"
        repeats = int(config.get("repeats", 7))
        if language == "c":
            # phase 1: uninstrumented builds at O0/O1/O2 (analyzer image)
            cname = f"cv-exp-{eid[:12]}"
            argv = ["docker", "run", "--rm", "--name", cname, *_BASE_FLAGS,
                    "-v", f"{src}:/work:ro", "-v", f"{out}:/out",
                    build_ref, "python3", "/opt/analyzer/c_opt_worker.py",
                    "--file", primary, "--out", "/out"]
            r = self._run_capped_or_timeout(argv, cname, eid)
            if r is None:
                return
            if not (out / "manifest.json").is_file():
                self._finish_failed(store, eid, "benchmark build failed")
                return
            # phase 2: timing in the runtime image (uninstrumented binaries)
            bin_dir = job_dir / "bin"
            bin_dir.mkdir(exist_ok=True)
            for level in ("O0", "O1", "O2"):
                app = out / level / "app"
                if app.is_file():
                    dest = bin_dir / f"app-{level}"
                    dest.write_bytes(app.read_bytes())
                    dest.chmod(0o755)
            cname = f"cv-exp-{eid[:12]}"
            argv = ["docker", "run", "--rm", "--name", cname, *_BASE_FLAGS,
                    "-v", f"{bin_dir}:/app:ro", "-v", f"{out}:/out",
                    exec_ref, "python3", "/opt/runtime/bench_worker.py",
                    "--mode", "c", "--bin-dir", "/app", "--out", "/out",
                    "--repeats", str(repeats)]
        else:
            cname = f"cv-exp-{eid[:12]}"
            argv = ["docker", "run", "--rm", "--name", cname, *_BASE_FLAGS,
                    "-v", f"{src}:/work:ro", "-v", f"{out}:/out",
                    exec_ref, "python3", "/opt/runtime/bench_worker.py",
                    "--mode", "python", "--file", primary, "--out", "/out",
                    "--repeats", str(repeats)]
        r = self._run_capped_or_timeout(argv, cname, eid)
        if r is None:
            return
        bench_p = out / "bench.json"
        if not bench_p.is_file():
            self._finish_failed(store, eid, "benchmark worker produced no result")
            return
        bench = json.loads(bench_p.read_text())
        _stage(store, eid, "bench", "AVAILABLE", bench)
        store.execute("UPDATE experiments SET status='COMPLETED', finished_utc=?,"
                      " result_sha256=? WHERE id=?",
                      (now_utc(), store.put_artifact(bench_p.read_bytes()), eid))

    # ---------------- stage 6-C: pair comparison (reuses stage 4 executions) ----------------
    def _run_compare(self, store: Store, eid: str, job, config: dict) -> None:
        from app.services.curated import CURATED_DIR
        pair_id = config.get("pair_id", "")
        manifest = json.loads((CURATED_DIR.parent / "pairs" / "manifest.json")
                              .read_text("utf-8"))
        pair = next((p for p in manifest["pairs"] if p["id"] == pair_id), None)
        if not pair:
            self._finish_failed(store, eid, f"unknown pair {pair_id!r}")
            return
        result: dict = {"pair": pair["id"], "concept": pair["concept"],
                        "expected_stdout": pair["expected_stdout"],
                        "sides": {}, "match": None}
        ok_all = True
        for side in ("c", "python"):
            ref = config.get(side) or {}
            try:
                ex = create_execution(store, ref["snapshot_id"], ref["target_id"])
            except ExecutionError as e:
                result["sides"][side] = {"error": e.code, "message": e.message}
                ok_all = False
                continue
            ex_id = ex["execution_id"]
            for _ in range(180):
                rec = store.query_one("SELECT status FROM executions WHERE id=?",
                                      (ex_id,))
                if rec and rec["status"] in TERMINAL:
                    break
                time.sleep(0.5)
            rec = store.query_one(
                "SELECT status, exit_code, stdout_sha256, duration_ms, image_id"
                " FROM executions WHERE id=?", (ex_id,))
            stdout = None
            if rec["stdout_sha256"]:
                stdout = store.get_artifact(rec["stdout_sha256"]).decode(
                    "utf-8", "replace")[:4000]
            side_result = {"execution_id": ex_id, "status": rec["status"],
                           "exit_code": rec["exit_code"],
                           "duration_ms": rec["duration_ms"],
                           "image_id": rec["image_id"], "stdout": stdout,
                           "expected_match": (stdout or "").strip()
                           == pair["expected_stdout"]}
            result["sides"][side] = side_result
            ok_all = ok_all and side_result["expected_match"] and \
                rec["status"] == "COMPLETED"
        result["match"] = ok_all
        _stage(store, eid, "compare", "AVAILABLE" if result["sides"] else "UNAVAILABLE",
               result)
        store.execute("UPDATE experiments SET status='COMPLETED', finished_utc=?"
                      " WHERE id=?", (now_utc(), eid))

    # ---------------- shared helpers ----------------
    def _run_capped_or_timeout(self, argv: list[str], cname: str, eid: str):
        from app.services.execution import run_capped
        store = self.store
        r = run_capped(argv, EXP_TIMEOUT_S)
        if store.query_one("SELECT cancel_requested FROM experiments WHERE id=?",
                           (eid,))["cancel_requested"]:
            subprocess.run(["docker", "rm", "-f", cname], capture_output=True,
                           timeout=60)
            self._finish_cancelled(store, eid)
            return None
        if r["killed"]:
            subprocess.run(["docker", "rm", "-f", cname], capture_output=True,
                           timeout=60)
            store.execute("UPDATE experiments SET status='TIMEOUT', finished_utc=?"
                          " WHERE id=?", (now_utc(), eid))
            return None
        return r

    def _finish_failed(self, store: Store, eid: str, message: str) -> None:
        store.execute("UPDATE experiments SET status='FAILED', error_code=?,"
                      " finished_utc=? WHERE id=?", (message[:300], now_utc(), eid))

    def _finish_cancelled(self, store: Store, eid: str) -> None:
        store.execute("UPDATE experiments SET status='CANCELLED', finished_utc=?"
                      " WHERE id=?", (now_utc(), eid))

    def cancel(self, eid: str) -> str:
        job = self.store.query_one("SELECT status FROM experiments WHERE id=?", (eid,))
        if not job:
            raise ExperimentError("NOT_FOUND", "unknown experiment id", 404)
        if job["status"] in TERMINAL:
            return job["status"]
        if job["status"] == "QUEUED":
            self._finish_cancelled(self.store, eid)
            return "CANCELLED"
        subprocess.run(["docker", "rm", "-f", f"cv-exp-{eid[:12]}"],
                       capture_output=True, timeout=60)
        self.store.execute("UPDATE experiments SET cancel_requested=1 WHERE id=?",
                           (eid,))
        return "CANCEL_REQUESTED"


_RUNNERS: dict[int, _ExperimentRunner] = {}
_LOCK = threading.Lock()


def get_experiment_runner(store: Store) -> _ExperimentRunner:
    key = id(store)
    with _LOCK:
        if key not in _RUNNERS:
            runner = _ExperimentRunner(store)
            runner._reconcile_interrupted()
            _RUNNERS[key] = runner
        return _RUNNERS[key]


def create_experiment(store: Store, kind: str, snapshot_id: str | None,
                      target_id: str | None, config: dict | None = None) -> dict:
    if kind not in ("opt", "bench", "compare"):
        raise ExperimentError("INVALID_KIND", f"unknown experiment kind {kind!r}")
    config = config or {}
    if kind == "compare":
        c_side = config.get("c") or {}
        py_side = config.get("python") or {}
        fp_src = f"{c_side.get('snapshot_id', '')}/{c_side.get('target_id', '')}:" \
                 f"{py_side.get('snapshot_id', '')}/{py_side.get('target_id', '')}"
        fp = f"{kind}:{config.get('pair_id', '')}:{fp_src}:{POLICY_VERSION}"
    else:
        snap = store.query_one("SELECT * FROM source_snapshots WHERE id=?",
                               (snapshot_id,))
        if not snap:
            raise ExperimentError("NOT_FOUND", "unknown snapshot", 404)
        if snap["origin"] == "github":
            raise ExperimentError("EXPERIMENT_ORIGIN_BLOCKED",
                                  "experiments on imported repository code are "
                                  "disabled (fail-closed)", 403)
        target = store.query_one(
            "SELECT * FROM compilation_targets WHERE id=? AND snapshot_id=?",
            (target_id, snapshot_id))
        if not target or target["status"] not in (
                "EXECUTABLE_CANDIDATE", "COMPILATION_CANDIDATE"):
            raise ExperimentError("NOT_ELIGIBLE",
                                  "target is not experiment-eligible")
        fp = f"{kind}:{snap['combined_sha256']}:{target_id}:" \
             f"{config.get('repeats', 7)}:{POLICY_VERSION}"
    existing = store.query_one(
        "SELECT id, status FROM experiments WHERE fingerprint=? AND status IN"
        " ('COMPLETED','RUNNING','QUEUED') ORDER BY created_utc DESC LIMIT 1", (fp,))
    if existing:
        return {"experiment_id": existing["id"], "status": existing["status"],
                "existed": True}
    requested_ids = None
    if kind != "compare":
        # pin the immutable image identities at submission; the runner
        # fails closed if the tags no longer match them at run time.
        build_ref = resolve_image_id(ANALYZER_IMAGE)
        exec_ref = resolve_image_id(RUNTIME_IMAGE)
        if build_ref is None or exec_ref is None:
            raise ExperimentError(
                "IMAGE_ID_UNAVAILABLE",
                "pinned experiment images could not be resolved (docker daemon "
                "down or image missing); refusing to run with mutable tags", 503)
        requested_ids = json.dumps({"build": build_ref, "exec": exec_ref})
    eid = new_id()
    store.execute(
        "INSERT INTO experiments (id, kind, snapshot_id, target_id, config_json,"
        " status, fingerprint, source_combined_sha256, created_utc,"
        " requested_image_ids)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (eid, kind, snapshot_id, target_id, json.dumps(config), "QUEUED", fp,
         snap["combined_sha256"] if kind != "compare" else None, now_utc(),
         requested_ids))
    get_experiment_runner(store).enqueue(eid)
    return {"experiment_id": eid, "status": "QUEUED", "existed": False}
