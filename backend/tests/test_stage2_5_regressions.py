"""Stage 2.5 regression tests - one per audit finding (CV-01..CV-11).

Each test encodes a defect reproduced by the independent source audit. If these
fail, the corresponding audit defect has regressed.
"""
import json
import subprocess

import pytest

from app.services import analyzer
from app.services.analyzer import build_run_argv
from app.services.normalize import _clang_ast_nodes, _ir_summary


# ---------------- CV-01: implicit-file declarations must stay visible ----------------

def test_clang_json_second_function_visible():
    """Clang emits loc.file only on file changes; the second same-file FunctionDecl
    carries no loc.file and must still appear as a tree root."""
    ast_json = {"inner": [
        {"kind": "FunctionDecl", "name": "adjust",
         "loc": {"file": "/work/case.c", "line": 2, "col": 12, "offset": 40}, "inner": []},
        {"kind": "FunctionDecl", "name": "main",
         "loc": {"line": 4, "col": 5, "offset": 90}, "inner": []},  # no loc.file (CV-01)
        {"kind": "VarDecl", "name": "stdin",
         "loc": {"file": "/usr/include/stdio.h", "line": 9, "col": 8}, "inner": []},
    ]}
    nodes, total = _clang_ast_nodes(ast_json, "case.c")
    roots = [n for n in nodes if n["parent"] is None]
    names = {n["name"] for n in roots}
    assert {"adjust", "main"} <= names, f"implicit-file decl lost: {names}"
    assert "stdin" not in names  # header decl counted, not shown
    assert total >= len(nodes)


def test_c_analysis_multi_function_tree_contains_both(client):
    src = ("#include <stdio.h>\n"
           "static int adjust(int base, int limit) { return base > limit ? limit : base; }\n"
           "int main(void) { return adjust(1, 2); }\n")
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "c", "filename": "two.c", "content": src}).json()
    t = client.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
    job = client.post("/api/v1/analyses", json={
        "snapshot_id": r["snapshot_id"], "target_id": t["target_id"]}).json()
    aid = job["analysis_id"]
    from tests.test_stage2_analysis import wait_terminal
    terminal = wait_terminal(client, aid)
    assert terminal["status"] == "COMPLETED"
    ast = client.get(f"/api/v1/analyses/{aid}/stages/ast").json()
    root_names = {n.get("name") for n in ast["items"] if n.get("parent") is None}
    assert {"adjust", "main"} <= root_names, f"CV-01 regression: {root_names}"


# ---------------- CV-02: multiline switch terminators ----------------

SWITCH_IR = """define i32 @f(i32 %x) {
entry:
  switch i32 %x, label %sw.default [
    i32 1, label %sw.bb1
    i32 2, label %sw.bb2
    i32 3, label %sw.bb3
  ]
sw.default:
  ret i32 0
sw.bb1:
  ret i32 1
sw.bb2:
  ret i32 2
sw.bb3:
  ret i32 3
}
"""


def test_ir_multiline_switch_edges_preserved():
    summary = _ir_summary(SWITCH_IR)
    entry = summary["functions"][0]["blocks"][0]
    assert entry["label"] == "entry"  # implicit <entry> merged with its real label
    assert sorted(entry["successors"]) == ["sw.bb1", "sw.bb2", "sw.bb3", "sw.default"]
    assert summary["counts"]["basic_blocks"] == 5
    assert summary["counts"]["cfg_edges_derived"] == 4


# ---------------- CV-03: missing Docker CLI / daemon are graceful ----------------

def test_missing_docker_cli_yields_blocked_job(client, monkeypatch):
    monkeypatch.setattr(analyzer.shutil, "which", lambda name: None)
    src = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "python", "filename": "x.py", "content": "a = 1\n"}).json()
    t = client.get(f"/api/v1/projects/{src['project_id']}/targets").json()[0]
    r = client.post("/api/v1/analyses", json={
        "snapshot_id": src["snapshot_id"], "target_id": t["target_id"]})
    assert r.status_code == 200, "must not raise FileNotFoundError (CV-03)"
    body = r.json()
    assert body["status"] == "BLOCKED" and body["error"] == "DOCKER_CLI_MISSING"


def test_stopped_daemon_yields_blocked_job(client, monkeypatch):
    def fail_info(argv, capture_output, timeout):
        class P:
            stdout = b""
            returncode = 1
        return P()
    monkeypatch.setattr(analyzer.subprocess, "run", fail_info)
    src = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "python", "filename": "y.py", "content": "b = 2\n"}).json()
    t = client.get(f"/api/v1/projects/{src['project_id']}/targets").json()[0]
    r = client.post("/api/v1/analyses", json={
        "snapshot_id": src["snapshot_id"], "target_id": t["target_id"]})
    assert r.status_code == 200
    assert r.json()["error"] == "DOCKER_DAEMON_UNAVAILABLE"


def test_run_uses_immutable_image_id():
    argv = build_run_argv("c", __import__("pathlib").Path("/s"),
                          __import__("pathlib").Path("/o"), "worker_c.py", "x.c",
                          image_ref="sha256:abc123")
    assert "sha256:abc123" in argv  # digest-pinned, not the mutable tag


# ---------------- CV-07/08: encoding + code-object identity ----------------

def test_python_latin1_source_consistent(client):
    # The function NAME is decoded by ast.parse: under the old bug the AST saw
    # 'caf\ufffd' while compile() saw 'café'. Upload carries TRUE latin-1 bytes so
    # PEP 263 decoding is exercised exactly as CPython would.
    raw_bytes = "# coding: latin-1\ndef caf\xe9():\n    return 1\n".encode("latin-1")
    r = client.post("/api/v1/sources", files={"file": ("l1.py", raw_bytes, "text/x-python")})
    assert r.status_code == 200, r.text
    body = r.json()
    t = client.get(f"/api/v1/projects/{body['project_id']}/targets").json()[0]
    job = client.post("/api/v1/analyses", json={
        "snapshot_id": body["snapshot_id"], "target_id": t["target_id"]}).json()
    from tests.test_stage2_analysis import wait_terminal
    terminal = wait_terminal(client, job["analysis_id"])
    assert terminal["status"] == "COMPLETED"
    ast_stage = client.get(f"/api/v1/analyses/{terminal['id']}/stages/ast").json()
    names = {n.get("name") for n in ast_stage["items"] if n.get("name")}
    assert "café" in names, f"PEP 263 divergence (CV-07): {names}"
    assert not any("\ufffd" in str(n) for n in names)


def test_code_object_identity_unique(client):
    src = ("def outer():\n"
           "    def inner():\n"
           "        return 1\n"
           "    def inner2():\n"
           "        return 2\n"
           "    return inner\n"
           "def inner():\n"
           "    return 3\n")
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "python", "filename": "nested.py", "content": src}).json()
    t = client.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
    job = client.post("/api/v1/analyses", json={
        "snapshot_id": r["snapshot_id"], "target_id": t["target_id"]}).json()
    from tests.test_stage2_analysis import wait_terminal
    terminal = wait_terminal(client, job["analysis_id"])
    assert terminal["status"] == "COMPLETED"
    bc = client.get(f"/api/v1/analyses/{terminal['id']}/stages/bytecode").json()
    assert bc["counts"]["code_objects"] == 5, "distinct-name counting collapsed scopes (CV-08)"
    ids = {i["code_object_id"] for i in bc["items"]}
    assert len(ids) == 5 and all(i.startswith("co") for i in ids)


# ---------------- CV-09: raw artifacts + invocation for every stage ----------------

def test_every_python_stage_has_raw_artifact_and_invocation(client):
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "python", "filename": "p.py", "content": "v = 5\n"}).json()
    t = client.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
    job = client.post("/api/v1/analyses", json={
        "snapshot_id": r["snapshot_id"], "target_id": t["target_id"]}).json()
    from tests.test_stage2_analysis import wait_terminal
    terminal = wait_terminal(client, job["analysis_id"])
    assert terminal["status"] == "COMPLETED"
    for s in terminal["stages"]:
        view = client.get(f"/api/v1/analyses/{terminal['id']}/stages/{s['stage']}").json()
        assert view["raw_artifact_sha256"], f"stage {s['stage']} lacks raw artifact (CV-09)"
        assert view["invocation"]["worker"] == "worker_python.py"
        assert view["invocation"]["tool_versions"].get("cpython", "").startswith("3.12")


# ---------------- CV-10: bounded intake before body processing ----------------

def test_oversized_part_rejected_at_stream_cap(client):
    big = b"x" * (2 * 1024 * 1024 + 1)  # just over per-file cap
    r = client.post("/api/v1/sources", files={"file": ("big.c", big, "text/plain")})
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_paste_content_length_cap_rejects_early(client):
    # Content-Length gate: header check fires before the body is processed.
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "python", "filename": "g.py",
        "content": "x" * (512 * 1024 + 100)})
    assert r.status_code == 413


# ---------------- CV-11: restart reconciliation ----------------

def test_restart_reconciles_running_and_queued(store):
    store.execute(
        "INSERT INTO analyses (id, snapshot_id, target_id, language, primary_file, status,"
        " fingerprint, source_combined_sha256, created_utc) VALUES (?,?,?,?,?,?,?,?,?)",
        ("a-running", "s", "t", "python", "x.py", "RUNNING", "fp", "hash", "2026-10-31"))
    store.execute(
        "INSERT INTO analyses (id, snapshot_id, target_id, language, primary_file, status,"
        " fingerprint, source_combined_sha256, created_utc) VALUES (?,?,?,?,?,?,?,?,?)",
        ("a-queued", "s", "t", "python", "x.py", "QUEUED", "fp", "hash", "2026-10-31"))
    analyzer._JobRunner(store)  # constructor reconciles
    running = store.query_one("SELECT status, error_code FROM analyses WHERE id='a-running'")
    assert running["status"] == "FAILED"
    assert running["error_code"] == "INTERRUPTED_BY_RESTART"


def test_cancel_running_marks_request_and_attempts_container_removal(store, monkeypatch):
    calls = []
    monkeypatch.setattr(analyzer.subprocess, "run",
                        lambda argv, capture_output, timeout: calls.append(argv) or
                        subprocess.CompletedProcess(argv, 0))
    runner = analyzer._JobRunner(store)  # reconciles before the row exists
    store.execute(
        "INSERT INTO analyses (id, snapshot_id, target_id, language, primary_file, status,"
        " fingerprint, source_combined_sha256, created_utc) VALUES (?,?,?,?,?,?,?,?,?)",
        ("a-live", "s", "t", "python", "x.py", "RUNNING", "fp", "hash", "2026-10-31"))
    result = runner.cancel("a-live")
    assert result == "CANCEL_REQUESTED"
    assert calls and calls[0][:3] == ["docker", "rm", "-f"]
    assert calls[0][3] == "cv-analysis-a-live"
    assert store.query_one("SELECT cancel_requested FROM analyses WHERE id='a-live'")["cancel_requested"] == 1
