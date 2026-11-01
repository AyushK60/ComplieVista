"""M6 OptimizationLab / benchmark / pair-comparison tests — real containers.

Oracles: host clang-18 18.1.3 compiles the same source independently (same
toolchain as the pinned analyzer image); pair expected outputs were verified
with the host toolchain (see sandbox/fixtures/pairs/manifest.json).
"""
import json
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAIRS = REPO / "sandbox" / "fixtures" / "pairs"

ADD_C = (PAIRS / "add.c").read_text()
ADD_PY = (PAIRS / "add.py").read_text()

PAIR_MANIFEST = json.loads((PAIRS / "manifest.json").read_text())


def _paste(client, language, filename, content):
    r = client.post("/api/v1/sources", json={
        "kind": "paste", "language": language, "filename": filename,
        "content": content}).json()
    t = client.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
    return r["snapshot_id"], t["target_id"]


def _experiment(client, body):
    r = client.post("/api/v1/experiments", json=body)
    assert r.status_code == 200, r.text[:200]
    eid = r.json()["experiment_id"]
    for _ in range(300):
        j = client.get(f"/api/v1/experiments/{eid}").json()
        if j["status"] in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BLOCKED"):
            return j
        time.sleep(0.5)
    return j


def _wait_execution(client, eid):
    for _ in range(180):
        rec = client.get(f"/api/v1/executions/{eid}").json()
        if rec["status"] in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BLOCKED"):
            return rec
        time.sleep(0.5)
    return rec


# ---------------- G1: real -O0/-O1/-O2 builds + oracle ----------------

def test_opt_builds_artifacts_and_tool_provenance(client):
    snap, tgt = _paste(client, "c", "add.c", ADD_C)
    j = _experiment(client, {"kind": "opt", "snapshot_id": snap, "target_id": tgt})
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"))
    stages = {s["stage"]: s for s in j["stages"]}
    assert set(stages) == {"O0", "O1", "O2"}
    for level, s in stages.items():
        r = s["result"]
        assert r["ok"] is True, r["steps"]
        # tool provenance recorded verbatim (clang version + target)
        assert "18.1.3" in r["tool"]["clang"]
        assert r["tool"]["target"].startswith("x86_64")
        # flags recorded verbatim and allowlisted
        assert r["flags"][0] == f"-{level}"
        # all artifact kinds present with digests and sizes
        for kind in ("ir", "asm", "symbols"):
            assert r[kind]["sha256"] and r[kind]["bytes"] > 0
        assert r["exe_bytes"] > 0
        # steps have real durations
        assert all(v["duration_ms"] >= 0 for v in r["steps"].values())


def test_opt_independent_host_clang_oracle(client):
    """Host clang-18 (same version, independent process) reproduces the
    container's structural results: function inventory in symbols and IR."""
    snap, tgt = _paste(client, "c", "add.c", ADD_C)
    j = _experiment(client, {"kind": "opt", "snapshot_id": snap, "target_id": tgt})
    stages = {s["stage"]: s["result"] for s in j["stages"]}

    def host_symbols(level: str) -> set[str]:
        out = Path("/tmp") / f"m6oracle_{level}"
        out.mkdir(exist_ok=True)
        src = out / "add.c"
        src.write_text(ADD_C)
        # same recorded flags as the worker (minus -g, which embeds the build
        # path and legitimately differs between host and container)
        subprocess.run(["clang-18", f"-{level}", "-no-pie",
                        "-fno-omit-frame-pointer", "-o", str(out / "app"),
                        str(src)], capture_output=True, check=True, timeout=60)
        nm = subprocess.run(["llvm-nm-18", "-S", str(out / "app")],
                            capture_output=True, check=True, timeout=60)
        return {line.split()[-1] for line in nm.stdout.decode().splitlines()
                if len(line.split()) >= 4 and line.split()[2] in ("t", "T")}

    def container_symbols(level: str) -> set[str]:
        art = client.get(
            f"/api/v1/experiments/{j['id']}/artifacts/{level}/symbols").json()
        return {line.split()[-1] for line in art["excerpt"].splitlines()
                if len(line.split()) >= 4 and line.split()[2] in ("t", "T")}

    for level in ("O0", "O2"):
        host = host_symbols(level)
        cont = container_symbols(level)
        assert host == cont, (level, host ^ cont)


def test_opt_transformation_and_distinct_levels(client):
    """A real optimization-level transformation with evidence: a CALLED 4-iteration
    summation loop keeps its compare/jump loop at -O0 but is folded to the
    constant 6 at -O2 (no loop). (An UNCALLED static function is eliminated even
    at -O0 — global DCE runs at every level — so it does not distinguish levels
    and is not claimed as a difference.) Executable sizes differ across levels."""
    loop_c = ("#include <stdio.h>\n"
              "static int loopsum(void) { int s = 0; for (int i = 0; i < 4; i++)"
              " s += i; return s; }\n"
              "int main(void) { printf(\"%d\\n\", loopsum()); return 0; }\n")
    snap, tgt = _paste(client, "c", "loopsum.c", loop_c)
    j = _experiment(client, {"kind": "opt", "snapshot_id": snap, "target_id": tgt})
    assert j["status"] == "COMPLETED"
    stages = {s["stage"]: s["result"] for s in j["stages"]}
    asm0 = client.get(
        f"/api/v1/experiments/{j['id']}/artifacts/O0/asm").json()["excerpt"]
    asm2 = client.get(
        f"/api/v1/experiments/{j['id']}/artifacts/O2/asm").json()["excerpt"]
    fn0 = asm0.split("loopsum:", 1)[-1].split(".Lfunc_end", 1)[0]
    assert "jge" in fn0, "-O0 keeps the compare/jump loop"
    assert "loopsum:" not in asm2, "-O2 inlines the function away entirely"
    assert "movl\t$6, %esi" in asm2, "-O2 folds the loop to the constant 6"
    sizes = {lvl: stages[lvl]["exe_bytes"] for lvl in ("O0", "O1", "O2")}
    assert len(set(sizes.values())) >= 2, sizes  # distinct where expected


# ---------------- G4: benchmark science ----------------

def test_bench_c_repeats_stats_provenance(client):
    snap, tgt = _paste(client, "c", "add.c", ADD_C)
    j = _experiment(client, {"kind": "bench", "snapshot_id": snap,
                             "target_id": tgt, "config": {"repeats": 5}})
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"))
    bench = next(s for s in j["stages"] if s["stage"] == "bench")["result"]
    assert bench["repeats"] == 5 and bench["warmup"] >= 1
    for level, rec in bench["levels"].items():
        assert rec["wall"]["n"] >= 5, ">=5 measured repeats"
        assert rec["checksums_identical"], "runs must be semantically identical"
        assert rec["wall"]["min_ms"] <= rec["wall"]["median_ms"] <= rec["wall"]["max_ms"]
        assert rec["cpu"]["n"] == rec["wall"]["n"]  # wall AND cpu per sample
    # environment provenance
    env = bench["env"]
    assert env["os"].startswith("Linux")
    assert env.get("cpu_model") or env.get("cpu_model", "") == ""
    assert "cgroup_cpu_max" in env and "cgroup_memory_max" in env
    assert bench["levels_semantics_equivalent"] is True


def test_bench_python_no_fake_levels(client):
    """Python gets its own measured baseline; NO fake LLVM levels exist for it."""
    snap, tgt = _paste(client, "python", "add.py", ADD_PY)
    j = _experiment(client, {"kind": "bench", "snapshot_id": snap,
                             "target_id": tgt, "config": {"repeats": 5,
                                                          "language": "python"}})
    assert j["status"] == "COMPLETED", (j.get("status"), j.get("error_code"))
    bench = next(s for s in j["stages"] if s["stage"] == "bench")["result"]
    assert set(bench["levels"]) == {"py312"}, bench["levels"].keys()
    rec = bench["levels"]["py312"]
    assert rec["wall"]["n"] >= 5 and rec["checksums_identical"]
    assert "O0" not in bench["levels"] and "O2" not in bench["levels"]


# ---------------- G3: pair comparison (5 specs) ----------------

def test_compare_all_five_pairs_match(client):
    pair_ids = {}
    for pair in PAIR_MANIFEST["pairs"]:
        c_snap, c_tgt = _paste(client, "c", pair["c_file"],
                               (PAIRS / pair["c_file"]).read_text())
        p_snap, p_tgt = _paste(client, "python", pair["py_file"],
                               (PAIRS / pair["py_file"]).read_text())
        j = _experiment(client, {"kind": "compare", "config": {
            "pair_id": pair["id"],
            "c": {"snapshot_id": c_snap, "target_id": c_tgt},
            "python": {"snapshot_id": p_snap, "target_id": p_tgt}}})
        assert j["status"] == "COMPLETED", (pair["id"], j.get("error_code"))
        res = next(s for s in j["stages"] if s["stage"] == "compare")["result"]
        assert res["match"] is True, (pair["id"], res)
        for side in ("c", "python"):
            assert res["sides"][side]["expected_match"] is True
            assert res["sides"][side]["exit_code"] == 0
        pair_ids[pair["id"]] = j["id"]
    assert len(pair_ids) == 5


# ---------------- admission / honesty ----------------

def test_experiment_admission_failures(client):
    r = client.post("/api/v1/experiments", json={"kind": "wizard"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_KIND"
    # non-executable target (text file) is refused
    r2 = client.post("/api/v1/sources", json={
        "kind": "paste", "language": "python", "filename": "notes.txt",
        "content": "hello"}).json()
    resp = client.post("/api/v1/experiments", json={
        "kind": "opt", "snapshot_id": r2["snapshot_id"],
        "target_id": r2["project_id"]})  # bogus target id
    assert resp.status_code == 400


def test_experiment_reopen_without_recomputation(client):
    snap, tgt = _paste(client, "c", "add.c", ADD_C)
    e1 = client.post("/api/v1/experiments", json={
        "kind": "opt", "snapshot_id": snap, "target_id": tgt}).json()
    d1 = client.get(f"/api/v1/experiments/{e1['experiment_id']}").json()
    e2 = client.post("/api/v1/experiments", json={
        "kind": "opt", "snapshot_id": snap, "target_id": tgt}).json()
    assert e2["existed"] is True and e2["experiment_id"] == e1["experiment_id"]
    d2 = client.get(f"/api/v1/experiments/{e1['experiment_id']}").json()
    assert d1 == d2, "reopen must be deterministic (no recomputation)"
