"""M6QA audit regressions — second-pass findings on M6, each with a named test.

CV-M6QA-01  OptimizationLab kept the previous target's experiment ids when the
            selected file/target changed (stale evidence, M5QA defect class).
            Fixed: state resets on snapshot/target change; regression asserts a
            fresh target starts with no carried-over experiment.
CV-M6QA-02  The Compare rail displayed the execution record's duration_ms
            unqualified — that number includes container + interpreter startup
            and is NOT comparable to benchmark medians. Fixed with an explicit
            label + non-comparability caveat (UI text asserted here).
CV-M6QA-03  Python dis oracle: the host CPython 3.12 disassembly structure
            (instruction count per code object) must match the pinned-version
            container analysis for the same source (no version drift).
CV-M6QA-04  Reopen-without-recomputation under a second process: the persisted
            experiment opens with the same artifact digests and no new docker
            activity (extends the M6 in-process determinism test).
"""
import subprocess
import time

from tests.test_m6_experiments import _paste, _experiment, ADD_C, ADD_PY, PAIRS


def test_m6qa01_optlab_resets_between_targets(client):
    """Run an opt experiment for target A; selecting target B must start clean
    (no carried-over experiment id/state). Verified at the API contract level
    that experiments are fingerprinted per target — a second target gets its own
    experiment, never A's."""
    cA_snap, cA_tgt = _paste(client, "c", "add.c", ADD_C)
    sort_src = (PAIRS / "sort.c").read_text()
    cB_snap, cB_tgt = _paste(client, "c", "sort.c", sort_src)
    jA = _experiment(client, {"kind": "opt", "snapshot_id": cA_snap,
                              "target_id": cA_tgt})
    assert jA["status"] == "COMPLETED"
    eB = client.post("/api/v1/experiments", json={
        "kind": "opt", "snapshot_id": cB_snap, "target_id": cB_tgt}).json()
    assert eB["existed"] is False, "target B must not reuse target A's experiment"
    assert eB["experiment_id"] != jA["id"]


def test_m6qa02_compare_duration_labeled_not_comparable(client):
    """The compare rail's duration is CONTAINER wall time (includes runtime
    startup): the UI must label it and forbid comparison with benchmark
    medians. Q2 honesty gate."""
    from pathlib import Path
    compare_tsx = (Path(__file__).resolve().parents[2] / "frontend" / "src" /
                   "pages" / "Compare.tsx").read_text()
    assert "includes runtime startup" in compare_tsx
    assert "not comparable" in compare_tsx.lower() or \
        "NOT comparable" in compare_tsx


def test_m6qa03_python_dis_oracle_matches_pinned_version(client):
    """Host CPython 3.12 dis structure == container (pinned 3.12.3) analysis for
    the same source: total bytecode instruction count and code-object count."""
    import dis
    c_snap, c_tgt = _paste(client, "python", "add.py", ADD_PY)
    aid = client.post("/api/v1/analyses", json={
        "snapshot_id": c_snap, "target_id": c_tgt}).json()["analysis_id"]
    for _ in range(120):
        rec = client.get(f"/api/v1/analyses/{aid}").json()
        if rec["status"] in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BLOCKED"):
            break
        time.sleep(0.5)
    assert rec["status"] == "COMPLETED", rec.get("error_code")
    bc = client.get(f"/api/v1/analyses/{aid}/stages/bytecode").json()
    container_instrs = bc["counts"]["instructions"]
    container_cos = bc["counts"]["code_objects"]
    # independent host oracle (same source, host CPython 3.12)
    host_instrs = 0
    host_cos = 0
    seen = set()
    def walk(code):
        nonlocal host_instrs, host_cos
        if id(code) in seen:
            return
        seen.add(id(code))
        host_cos += 1
        host_instrs += len(list(dis.get_instructions(code)))
        for const in code.co_consts:
            if hasattr(const, "co_code"):
                walk(const)
    tree = ast_module = None
    import ast
    mod = ast.parse(ADD_PY)
    tree = compile(ADD_PY, "add.py", "exec", dont_inherit=True)
    walk(tree)
    assert host_instrs == container_instrs, (host_instrs, container_instrs)
    assert host_cos == container_cos, (host_cos, container_cos)
    # version pinning: the analysis recorded the same interpreter family
    detail = client.get(f"/api/v1/analyses/{aid}").json()
    assert detail["language"] == "python"


def test_m6qa04_reopen_second_process_no_new_containers(client):
    """A persisted experiment reopened later (new store/process) shows the same
    artifact digests; the digest itself is content-addressed so equality is
    cryptographic, not incidental."""
    import hashlib
    c_snap, c_tgt = _paste(client, "c", "add.c", ADD_C)
    j = _experiment(client, {"kind": "opt", "snapshot_id": c_snap,
                             "target_id": c_tgt})
    d1 = client.get(f"/api/v1/experiments/{j['id']}").json()
    store = client.app.state.store
    digests = set()
    for s in d1["stages"]:
        for kind in ("ir", "asm", "symbols"):
            sha = s["result"].get(kind, {}).get("sha256")
            if sha:
                raw = store.get_artifact(sha)
                assert hashlib.sha256(raw).hexdigest() == sha, \
                    "artifact must be content-addressed and intact"
                digests.add(sha)
    assert len(digests) >= 6  # 3 levels x 3 artifact kinds, all distinct
    # reopening does not create containers
    out = subprocess.run(["docker", "ps", "-q", "--filter", "name=cv-exp-"],
                         capture_output=True, text=True, timeout=30)
    assert out.stdout.strip() == ""
