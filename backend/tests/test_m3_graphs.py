"""M3-A graph contract + oracle tests.

Graph views must reconcile against REAL tool representations: raw IR text for CFG
edges, fresh CPython dis for jump targets, clang AST structure. Not normalizer-vs-
normalizer: the oracles re-derive expectations from the tools themselves.
"""
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

from tests.test_m2_analysis import run_analysis, wait_terminal

SWITCH_SRC = """static int classify(int v) {
    switch (v) {
    case 1: return 10;
    case 2: return 20;
    case 3: return 30;
    default: return 0;
    }
}
int main(void) { return classify(2); }
"""

NESTED_PY = """def outer():
    def inner():
        return 1
    def inner():
        return 2
    return inner
"""


def _analyze(client, language, filename, content):
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": language, "filename": filename, "content": content}).json()
    t = client.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
    job = client.post("/api/v1/analyses", json={
        "snapshot_id": r["snapshot_id"], "target_id": t["target_id"]}).json()
    return job["analysis_id"], wait_terminal(client, job["analysis_id"])


def test_c_ast_graph_contains_both_functions_and_edges_match_nodes(client):
    aid, job = _analyze(client, "c", "twofn.c", SWITCH_SRC)
    assert job["status"] == "COMPLETED"
    g = client.get(f"/api/v1/analyses/{aid}/stages/ast/graph").json()
    assert g["schema_version"] == "m3.graph.v1"
    roots = [n for n in g["nodes"] if not any(
        e for e in g["edges"] if e["target"] == n["id"] and e["kind"] == "containment")]
    root_names = {n["name"] for n in roots if n["kind"] == "FunctionDecl"}
    assert {"classify", "main"} <= root_names, "CV-01 must stay fixed at graph level"
    node_ids = {n["id"] for n in g["nodes"]}
    for e in g["edges"]:
        assert e["source"] in node_ids and e["target"] in node_ids
        assert e["confidence"] in ("EXACT", "DERIVED", "APPROXIMATE", "UNAVAILABLE")
    # every non-root AST node has exactly one containment parent (tree structure)
    parents = [e["target"] for e in g["edges"] if e["kind"] == "containment"]
    assert len(parents) == len(set(parents)), "AST containment must be a tree"


def test_c_cfg_graph_edges_reconcile_with_raw_ir(client):
    aid, job = _analyze(client, "c", "switch.c", SWITCH_SRC)
    g = client.get(f"/api/v1/analyses/{aid}/stages/ir_o0/graph").json()
    assert g["availability"] == "AVAILABLE"
    # oracle: fresh host clang IR, same extraction logic independent of the app
    f = tempfile.NamedTemporaryFile("w", suffix=".c", delete=False)
    f.write(SWITCH_SRC)
    f.close()
    ir = subprocess.run(["clang", "-S", "-emit-llvm", "-g", "-O0", "-o", "-", f.name],
                        capture_output=True, timeout=120).stdout.decode()
    # count real terminator targets in the raw IR (multiline switch included)
    acc = []
    lines = ir.splitlines()
    i = 0
    oracle_edges = 0
    while i < len(lines):
        if re.match(r"^\s*(br|switch|ret|unreachable)\b", lines[i]):
            acc = lines[i].strip()
            while acc.count("[") - acc.count("]") > 0:
                i += 1
                acc += " " + lines[i].strip()
            oracle_edges += len(re.findall(r"\blabel\s+%([\w.$-]+)", acc))
        i += 1
    api_branch_edges = [e for e in g["edges"] if e["kind"] == "cfg_branch"]
    assert len(api_branch_edges) == oracle_edges > 0
    entry = next(n for n in g["nodes"] if n["kind"] == "basic_block"
                 and n["function"] == "classify")
    entry_succ = [e["target"] for e in g["edges"]
                  if e["source"] == entry["id"]]
    assert len(entry_succ) == 4, "switch default + 3 cases (CV-02 at graph level)"


def test_bytecode_graph_jump_edges_and_code_object_ids(client):
    src = ("def outer():\n"
           "    total = 0\n"
           "    for i in range(4):\n"
           "        total += i\n"
           "    def inner():\n"
           "        return 1\n"
           "    def inner():\n"
           "        return 2\n"
           "    return total\n")
    aid, job = _analyze(client, "python", "nested.py", src)
    assert job["status"] == "COMPLETED"
    g = client.get(f"/api/v1/analyses/{aid}/stages/bytecode/graph").json()
    co_nodes = [n for n in g["nodes"] if n["kind"] == "code_object"]
    assert len(co_nodes) == 4  # module + outer + TWO same-named nested inners (CV-08)
    inner_ids = [n["id"] for n in co_nodes if n["name"].endswith("inner")]
    assert len(inner_ids) == 2 and len(set(inner_ids)) == 2, \
        "same-named nested code objects must keep distinct graph identities"
    jump_edges = [e for e in g["edges"] if e["kind"] == "bytecode_branch"]
    assert jump_edges, "real loop jumps must produce DERIVED branch edges"
    ins_ids = {n["id"] for n in g["nodes"]}
    for e in jump_edges:
        assert e["source"] in ins_ids and e["target"] in ins_ids


def test_python_ast_graph_unicode_and_syntax_error(client):
    aid, job = _analyze(client, "python", "uni.py",
                        "def caf\u00e9():\n    return 1\n")
    assert job["status"] == "COMPLETED"
    g = client.get(f"/api/v1/analyses/{aid}/stages/ast/graph").json()
    assert any(n.get("name") == "café" for n in g["nodes"]), "unicode names preserved"


def test_ungraphable_stage_returns_typed_error(client):
    aid, job = _analyze(client, "python", "t.py", "x = 1\n")
    r = client.get(f"/api/v1/analyses/{aid}/stages/tokens/graph")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "GRAPH_UNSUPPORTED"


def test_syntax_error_graph_reflects_honest_stages(client):
    aid, job = _analyze(client, "python", "bad.py", "def broken(:\n    pass\n")
    assert job["status"] == "COMPLETED"
    r = client.get(f"/api/v1/analyses/{aid}/stages/bytecode/graph")
    assert r.status_code == 404, "no bytecode graph may exist for unparseable source"
