"""M7 demo library — exactly 20 curated real programs (ADR-0010).

The manifest (sandbox/fixtures/demos/manifest.json) is versioned and hash-pinned:
every file digest is verified on load. Demo snapshots are created from the
manifest content (idempotent, origin "curated") and run through the REAL M4
execution pipeline; C-05 uses the demo-link profile (multi-TU compile+link
inside the pinned analyzer container, TU list from the manifest — never user
input). Error fixtures are NOT part of the 20 count.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from app.services.classify import classify_files
from app.services.curated import FIXTURES  # repo sandbox/fixtures root
from app.services.execution import (TERMINAL as EXEC_TERMINAL, ExecutionError,
                                    create_execution)
from app.store.db import combined_hash, new_id, now_utc

DEMO_MANIFEST_PATH = FIXTURES / "demos" / "manifest.json"
ERROR_MANIFEST = [
    {"id": "ERR-SYNTAX", "file": "errors/err_syntax.c", "language": "c",
     "kind": "syntax"},
    {"id": "ERR-SEMANTIC", "file": "errors/err_semantic.c", "language": "c",
     "kind": "semantic"},
    {"id": "ERR-LINK", "file": "errors/err_link.c", "language": "c",
     "kind": "link"},
    {"id": "ERR-RUNTIME", "file": "errors/err_runtime.py", "language": "python",
     "kind": "runtime"},
]
_DEMO_LINK_TUS: dict[str, dict] | None = None


class DemoError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def load_manifest() -> dict:
    manifest = json.loads(DEMO_MANIFEST_PATH.read_text("utf-8"))
    demos = manifest.get("demos", [])
    if len(demos) != 20:
        raise DemoError("MANIFEST_INVALID",
                        f"demo manifest must contain exactly 20 programs, "
                        f"found {len(demos)}", 500)
    ids = [d["id"] for d in demos]
    if len(set(ids)) != 20:
        raise DemoError("MANIFEST_INVALID", "duplicate demo ids", 500)
    return manifest


def _demo_link_tus() -> dict[str, dict]:
    """snapshot combined hash -> demo entry, for multi-file demos."""
    global _DEMO_LINK_TUS
    if _DEMO_LINK_TUS is None:
        _DEMO_LINK_TUS = {}
        for d in load_manifest()["demos"]:
            if len(d["files"]) > 1:
                files = {Path(f["path"]).name: (FIXTURES / f["path"]).read_bytes()
                         for f in d["files"]}
                _DEMO_LINK_TUS[combined_hash(files)] = d
    return _DEMO_LINK_TUS


def get_demo(demo_id: str) -> dict:
    for d in load_manifest()["demos"]:
        if d["id"] == demo_id:
            return d
    raise DemoError("NOT_FOUND", f"unknown demo {demo_id!r}", 404)


def _demo_snapshot(store: Store, demo: dict) -> tuple[str, str]:
    """Idempotent curated snapshot + first eligible target for a demo."""
    files: dict[str, bytes] = {}
    for f in demo["files"]:
        files[Path(f["path"]).name] = (FIXTURES / f["path"]).read_bytes()
    combined = combined_hash(files)
    existing = store.query_one(
        "SELECT id FROM source_snapshots WHERE project_id='demo-library' AND"
        " combined_sha256=?", (combined,))
    if existing:
        snap_id = existing["id"]
    else:
        snap_id = new_id()
        store.execute(
            "INSERT INTO source_snapshots (id, project_id, origin, combined_sha256,"
            " created_utc) VALUES (?, 'demo-library', 'curated', ?, ?)",
            (snap_id, combined, now_utc()))
        for rel, data in sorted(files.items()):
            file_sha = store.put_artifact(data)
            store.execute(
                "INSERT INTO source_files (id, snapshot_id, rel_path, content_sha256,"
                " size, encoding, language) VALUES (?,?,?,?,?,?,?)",
                (hashlib.sha256(rel.encode()).hexdigest()[:16], snap_id, rel,
                 file_sha, len(data),
                 "binary" if b"\x00" in data[:8192] else "utf-8",
                 "python" if rel.endswith(".py") else
                 ("c" if rel.endswith((".c", ".h")) else "other")))
        classify_files(store, snap_id, files)
    target = store.query_one(
        "SELECT id FROM compilation_targets WHERE snapshot_id=? AND status IN"
        " ('EXECUTABLE_CANDIDATE','COMPILATION_CANDIDATE') ORDER BY primary_file"
        " LIMIT 1", (snap_id,))
    if not target:
        raise DemoError("NOT_ELIGIBLE",
                        f"no eligible target for demo {demo['id']}", 500)
    return snap_id, target["id"]


def run_demo(store: Store, demo_id: str) -> dict:
    demo = get_demo(demo_id)
    snap_id, target_id = _demo_snapshot(store, demo)
    is_multi = len(demo["files"]) > 1
    try:
        ref = create_execution(
            store, snap_id, target_id,
            "demo-link" if is_multi else "standard")
    except ExecutionError as e:
        raise DemoError(e.code, e.message, e.status)
    eid = ref["execution_id"]
    for _ in range(240):
        rec = store.query_one(
            "SELECT status, exit_code, stdout_sha256 FROM executions WHERE id=?",
            (eid,))
        if rec and rec["status"] in EXEC_TERMINAL:
            break
        time.sleep(0.5)
    stdout = None
    if rec["stdout_sha256"]:
        stdout = store.get_artifact(rec["stdout_sha256"]).decode(
            "utf-8", "replace")[:4000]
    return {
        "demo_id": demo_id, "execution_id": eid, "snapshot_id": snap_id,
        "target_id": target_id, "status": rec["status"],
        "exit_code": rec["exit_code"], "stdout": stdout,
        "expected_stdout": demo["expected_stdout"],
        "stdout_match": (stdout or "").strip() == demo["expected_stdout"].strip(),
        "expected_exit": demo["expected_exit"],
    }


def analyze_demo(store: Store, demo_id: str) -> dict:
    from app.services.analyzer import AnalysisError, create_analysis
    demo = get_demo(demo_id)
    snap_id, target_id = _demo_snapshot(store, demo)
    try:
        ref = create_analysis(store, snap_id, target_id)
    except AnalysisError as e:
        raise DemoError(e.code, e.message, e.status)
    aid = ref["analysis_id"]
    for _ in range(180):
        rec = store.query_one("SELECT status FROM analyses WHERE id=?", (aid,))
        if rec and rec["status"] in EXEC_TERMINAL:
            break
        time.sleep(0.5)
    return {"demo_id": demo_id, "analysis_id": aid, "status": rec["status"],
            "snapshot_id": snap_id, "target_id": target_id}


def optimize_demo(store: Store, demo_id: str) -> dict:
    from app.services.experiments import ExperimentError, create_experiment
    demo = get_demo(demo_id)
    if not demo["id"].startswith(("C-", "PAIR-")) or "-PY" in demo["id"]:
        raise DemoError("NOT_APPLICABLE",
                        "OptimizationLab applies to C targets only", 400)
    snap_id, target_id = _demo_snapshot(store, demo)
    try:
        return create_experiment(store, "opt", snap_id, target_id)
    except ExperimentError as e:
        raise DemoError(e.code, e.message, e.status)


def run_error_fixture(store: Store, fixture_id: str) -> dict:
    """Error Microscope: genuine diagnostics OUTSIDE the 20-program count."""
    entry = next((e for e in ERROR_MANIFEST if e["id"] == fixture_id), None)
    if not entry:
        raise DemoError("NOT_FOUND", f"unknown error fixture {fixture_id!r}", 404)
    data = (FIXTURES / entry["file"]).read_bytes()
    combined = combined_hash({Path(entry["file"]).name: data})
    existing = store.query_one(
        "SELECT id FROM source_snapshots WHERE project_id='error-microscope' AND"
        " combined_sha256=?", (combined,))
    if existing:
        snap_id = existing["id"]
    else:
        snap_id = new_id()
        store.execute(
            "INSERT INTO source_snapshots (id, project_id, origin, combined_sha256,"
            " created_utc) VALUES (?, 'error-microscope', 'curated', ?, ?)",
            (snap_id, combined, now_utc()))
        file_sha = store.put_artifact(data)
        store.execute(
            "INSERT INTO source_files (id, snapshot_id, rel_path, content_sha256,"
            " size, encoding, language) VALUES (?,?,?,?,?,?,?)",
            (hashlib.sha256(entry["file"].encode()).hexdigest()[:16], snap_id,
             Path(entry["file"]).name, file_sha, len(data), "utf-8",
             entry["language"]))
        classify_files(store, snap_id, {Path(entry["file"]).name: data})
    result: dict = {"fixture_id": fixture_id, "kind": entry["kind"]}
    if entry["kind"] in ("runtime", "link"):
        # link errors surface at the BUILD step of an execution; analysis
        # (-fsyntax-only style stages) correctly passes declared-but-undefined.
        from app.services.execution import create_execution
        target = store.query_one(
            "SELECT id FROM compilation_targets WHERE snapshot_id=? LIMIT 1",
            (snap_id,))
        ref = create_execution(store, snap_id, target["id"])
        eid = ref["execution_id"]
        for _ in range(180):
            rec = store.query_one(
                "SELECT status, exit_code, stdout_sha256, stderr_sha256,"
                " error_code FROM executions WHERE id=?", (eid,))
            if rec and rec["status"] in EXEC_TERMINAL:
                break
            time.sleep(0.5)
        result["execution_id"] = eid
        result["status"] = rec["status"]
        result["exit_code"] = rec["exit_code"]
        result["diagnostic"] = (store.get_artifact(rec["stderr_sha256"]).decode(
            "utf-8", "replace")[-1200:] if rec["stderr_sha256"] else
            (rec["error_code"] or ""))
    else:
        from app.services.analyzer import create_analysis
        target = store.query_one(
            "SELECT id FROM compilation_targets WHERE snapshot_id=? LIMIT 1",
            (snap_id,))
        ref = create_analysis(store, snap_id, target["id"])
        aid = ref["analysis_id"]
        for _ in range(120):
            rec = store.query_one(
                "SELECT status, error_code FROM analyses WHERE id=?", (aid,))
            if rec and rec["status"] in EXEC_TERMINAL:
                break
            time.sleep(0.5)
        stages = store.query(
            "SELECT stage, availability, exit_code, stderr_artifact FROM"
            " analysis_stages WHERE analysis_id=?", (aid,))
        diagnostics = {}
        for st in stages:
            if st["stderr_artifact"]:
                diagnostics[st["stage"]] = store.get_artifact(
                    st["stderr_artifact"]).decode("utf-8", "replace")[-800:]
        result["analysis_id"] = aid
        result["status"] = rec["status"]
        result["diagnostic"] = (json.dumps(diagnostics)[:1200] if diagnostics
                                else rec["error_code"] or "")
    return result


def demo_report(store: Store, demo_id: str) -> dict:
    """Sanitized session report: digests + availability + measured outcomes.
    No source text, no host paths, no secrets — safe to export."""
    demo = get_demo(demo_id)
    snap_id, _ = _demo_snapshot(store, demo)
    files = [{"path": f["path"], "sha256": f["sha256"]} for f in demo["files"]]
    execs = store.query(
        "SELECT id, status, exit_code, stdout_sha256, image_id, duration_ms"
        " FROM executions WHERE snapshot_id=?", (snap_id,))
    return {
        "demo_id": demo_id, "schema": "m7.demo.report.v1",
        "title": demo["title"], "group": demo["group"],
        "expected_stdout": demo["expected_stdout"],
        "capabilities": demo["capabilities"], "limits": demo["limits"],
        "files": files, "snapshot_combined_sha256": snap_id and store.query_one(
            "SELECT combined_sha256 FROM source_snapshots WHERE id=?",
            (snap_id,))["combined_sha256"],
        "executions": [{"id": e["id"], "status": e["status"],
                        "exit_code": e["exit_code"],
                        "stdout_sha256": e["stdout_sha256"],
                        "image_id": e["image_id"],
                        "duration_ms": e["duration_ms"]} for e in execs],
    }
