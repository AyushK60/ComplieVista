"""M2-F independent oracle tests: real analysis jobs vs freshly-run host toolchain.

The oracle re-runs clang/CPython OUTSIDE the app's normalization code and compares
structural evidence (token counts, AST node counts, IR functions, bytecode offsets).
Raw digests are recorded per-run; byte-level comparison of preprocessed text is NOT
expected across environments because clang -E embeds the path it was given
(container /work/... vs host path) — structural identity is the honest oracle here.
"""
import json
import re
import subprocess
import time

import pytest

C_SRC = """#include <stdio.h>
#define M0_SCALE 3
static int scale(int base, int limit) {
    int scaled = base * M0_SCALE;
    if (scaled > limit) { return limit; }
    return scaled;
}
int main(void) {
    int values[4] = {1, 2, 3, 4};
    int total = 0;
    for (int i = 0; i < 4; i++) { total += scale(values[i], 10); }
    printf("total=%d\\n", total);
    return 0;
}
"""

PY_SRC = """def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


class Accumulator:
    def __init__(self):
        self.total = 0

    def add(self, value):
        self.total += value
        return self.total


def gen():
    yield from range(3)


if __name__ == "__main__":
    print(fib(10))
"""


def wait_terminal(client, analysis_id, tries=90):
    for _ in range(tries):
        job = client.get(f"/api/v1/analyses/{analysis_id}").json()
        if job["status"] in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BLOCKED"):
            return job
        time.sleep(0.5)
    return job


def run_analysis(client, language, filename, content):
    src = client.post("/api/v1/sources", json={
        "kind": "paste", "language": language, "filename": filename, "content": content}).json()
    targets = client.get(f"/api/v1/projects/{src['project_id']}/targets").json()
    target = next(t for t in targets if t["primary_file"] == filename)
    job = client.post("/api/v1/analyses", json={
        "snapshot_id": src["snapshot_id"], "target_id": target["target_id"]}).json()
    assert job["status"] in ("QUEUED", "RUNNING")
    return job["analysis_id"], wait_terminal(client, job["analysis_id"])


def test_c_analysis_full_pipeline_and_oracle(client, tmp_path):
    aid, job = run_analysis(client, "c", "oracle.c", C_SRC)
    assert job["status"] == "COMPLETED", job
    stage_names = {s["stage"] for s in job["stages"]}
    assert {"preprocess", "tokens", "ast", "ir_o0", "ir_o2", "assembly",
            "object", "symbols", "disassembly"} <= stage_names
    by = {s["stage"]: s for s in job["stages"]}
    core = ["preprocess", "ast", "ir_o0", "ir_o2", "assembly", "object"]
    assert all(by[s]["availability"] == "AVAILABLE" for s in core), by

    # --- independent host clang oracle ---
    f = tmp_path / "oracle.c"
    f.write_text(C_SRC)
    tokens = subprocess.run(["clang", "-fsyntax-only", "-Xclang", "-dump-tokens", str(f)],
                            capture_output=True, timeout=120)
    dump = (tokens.stdout or tokens.stderr).decode("utf-8", "replace")
    host_tokens = len([l for l in dump.splitlines() if "Loc=<" in l])
    ast = subprocess.run(["clang", "-fsyntax-only", "-Xclang", "-ast-dump=json", str(f)],
                         capture_output=True, timeout=120)

    def count_ast_nodes(payload: dict) -> int:
        n = 0

        def walk(d):
            nonlocal n
            if isinstance(d, dict) and "kind" in d:
                n += 1
            for child in (d.get("inner") or []) if isinstance(d, dict) else []:
                walk(child)

        for top in payload.get("inner") or []:
            walk(top)
        return n

    host_ast_nodes = count_ast_nodes(json.loads(ast.stdout))
    ir = subprocess.run(["clang", "-S", "-emit-llvm", "-g", "-O0", "-o", "-", str(f)],
                        capture_output=True, timeout=120).stdout.decode()
    host_funcs = sorted(set(re.findall(r"^define\s+.*@([\w.$-]+)", ir, re.M)))

    stage = client.get(f"/api/v1/analyses/{aid}/stages/tokens").json()
    assert stage["counts"]["tokens"] == host_tokens > 0
    assert all(t["mapping_confidence"] == "EXACT" for t in stage["items"][:10])
    ast_stage = client.get(f"/api/v1/analyses/{aid}/stages/ast").json()
    assert abs(ast_stage["counts"]["ast_nodes"] - host_ast_nodes) <= 2
    ir_stage = client.get(f"/api/v1/analyses/{aid}/stages/ir_o0").json()
    api_funcs = sorted(f["name"] for f in ir_stage["items"])
    assert api_funcs == host_funcs == ["main", "scale"]
    # terminator-derived CFG edges exist for the branch/loop
    total_edges = ir_stage["counts"]["cfg_edges_derived"]
    assert total_edges >= 4, "branch/loop CFG edges must be derived from terminators"
    assert ir_stage["counts"]["basic_blocks"] >= 5
    # O2 is a genuinely independent build (different artifact digest than O0)
    o0 = client.get(f"/api/v1/analyses/{aid}/stages/ir_o0").json()
    o2 = client.get(f"/api/v1/analyses/{aid}/stages/ir_o2").json()
    assert o0["raw_artifact_sha256"] != o2["raw_artifact_sha256"]
    assert o2["limitations"] and "UNAVAILABLE" in " ".join(o2["limitations"])
    # object evidence
    obj = client.get(f"/api/v1/analyses/{aid}/stages/object").json()
    assert obj["counts"]["bytes"] > 0 and obj["counts"]["object_sha256"]
    # provenance fields present
    for s in (stage, ast_stage, ir_stage):
        assert s["raw_artifact_sha256"] and s["stderr_artifact_sha256"]
        assert s["invocation"]["tool_versions"], "real tool versions must be recorded"
        assert s["invocation"]["worker"] == "worker_c.py"
        assert s["invocation"]["image_id"], "digest-pinned image id must be recorded"


def test_python_analysis_pipeline_and_oracle(client, tmp_path):
    aid, job = run_analysis(client, "python", "oracle.py", PY_SRC)
    assert job["status"] == "COMPLETED", job
    stage_names = {s["stage"] for s in job["stages"]}
    assert {"tokens", "ast", "code_object", "bytecode"} <= stage_names
    by = {s["stage"]: s for s in job["stages"]}
    assert all(by[s]["availability"] == "AVAILABLE"
               for s in ("tokens", "ast", "code_object", "bytecode"))
    # nested code objects: module + fib + Accumulator + __init__ + add + gen
    assert by["bytecode"]["counts"]["code_objects"] >= 5

    # independent host CPython oracle
    f = tmp_path / "oracle.py"
    f.write_text(PY_SRC)
    import ast as ast_mod
    import dis as dis_mod
    host_tree = ast_mod.parse(PY_SRC)
    host_nodes = sum(1 for _ in ast_mod.walk(host_tree))
    host_instr = 0
    stack = [compile(PY_SRC, "oracle.py", "exec", dont_inherit=True)]
    while stack:
        co = stack.pop()
        host_instr += len(list(dis_mod.get_instructions(co, show_caches=False)))
        stack.extend(c for c in co.co_consts if isinstance(c, type(co)))
    ast_stage = client.get(f"/api/v1/analyses/{aid}/stages/ast").json()
    assert ast_stage["counts"]["nodes"] == host_nodes
    bc = client.get(f"/api/v1/analyses/{aid}/stages/bytecode").json()
    assert bc["counts"]["instructions"] == host_instr
    assert all(i["mapping_confidence"] in ("EXACT", "UNAVAILABLE") for i in bc["items"][:20])
    positions = [i for i in bc["items"] if i["positions"]]
    assert positions and all(len(i["positions"]) == 4 for i in positions[:5])
    # scopes: class and functions present
    ast_payload = ast_stage["counts"]
    assert ast_payload["scopes"] >= 4
    # no runtime claims
    assert client.get(f"/api/v1/analyses/{aid}").json()["ready_for_controlled_execution"] is False


def test_c_syntax_error_honest_stages(client):
    aid, job = run_analysis(client, "c", "broken.c", "int main(void){ return oops }\n")
    assert job["status"] == "COMPLETED"
    by = {s["stage"]: s for s in job["stages"]}
    # preprocessing succeeds; token/ast stages produce output WITH errors → PARTIAL
    assert by["preprocess"]["availability"] == "AVAILABLE"
    assert by["ast"]["availability"] in ("PARTIAL", "ERROR")
    ast_stage = client.get(f"/api/v1/analyses/{aid}/stages/ast").json()
    diags = [i for i in ast_stage["items"] if i.get("severity") == "error"]
    assert diags, "real compiler diagnostics must be present"
    assert all(d["raw"] and d["file"] == "broken.c" for d in diags[:3])
    assert any("expected" in d["message"].lower() or "undeclared" in d["message"].lower()
               for d in diags)
    # IR/assembly must NOT be shown as available when the compiler rejected the source
    for s in ("ir_o0", "ir_o2", "assembly", "object"):
        assert by[s]["availability"] in ("ERROR", "NOT_REQUESTED") or \
            by[s]["exit_code"] != 0, f"{s} must not be AVAILABLE on invalid source"


def test_python_side_effect_source_never_executed(client, tmp_path):
    marker = tmp_path / "PWNED_M2"
    evil = (f"import pathlib\npathlib.Path(r'{marker}').write_text('x')\n"
            "raise RuntimeError('bomb')\n")
    aid, job = run_analysis(client, "python", "bomb.py", evil)
    assert job["status"] == "COMPLETED"
    assert not marker.exists(), "static analysis executed the source!"


def test_m0_analysis_dispatch_still_works(client):
    r = client.get("/api/v1/analyses/m0-c").json()
    assert r["id"] == "m0-c" and any(s["stage"] == "ir" for s in r["stages"])
    r2 = client.get("/api/v1/analyses/m0-python/stages/py_tokens" if False
                    else "/api/v1/analyses/m0-python/stages/tokens").json()
    assert r2["counts"]["tokens"] > 0
