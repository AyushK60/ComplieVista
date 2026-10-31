#!/usr/bin/env python3
"""M0 Deliverable C — genuine CPython 3.12 proof (tokenize / ast / compile / dis).

Stdlib only. Static inspection ONLY: the fixture is parsed and compiled to a code
object for inspection, but never executed (no exec/eval/import; compile() does not
run top-level code). Writes raw artifacts + normalized records + manifest to
evidence/m0/python/.
"""
from __future__ import annotations

import ast
import dis
import hashlib
import io
import json
import platform
import subprocess
import sys
import time
import tokenize
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEMO = REPO / "demos" / "m0"
OUT = REPO / "evidence" / "m0" / "python"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def write_artifact(name: str, data: bytes) -> dict:
    p = OUT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return {"path": str(p.relative_to(REPO)).replace("\\", "/"), "sha256": sha256_bytes(data), "bytes": len(data)}


def stage_record(stage: str, artifacts: list[dict], counts: dict, limits: list[str],
                 obs_class: str = "TOOL_OUTPUT", extra: dict | None = None) -> dict:
    rec = {
        "stage": stage,
        "availability": "AVAILABLE",
        "observation_class": obs_class,
        "invocation": {"argv": [sys.executable, "-c", f"<CPython {platform.python_version()} stdlib {stage} collection>"],
                       "tool": "cpython", "version": platform.python_version(),
                       "exit_code": 0, "duration_ms": extra.get("duration_ms", 0) if extra else 0},
        "artifacts": artifacts,
        "counts": counts,
        "limitations": limits,
    }
    if extra:
        rec.update(extra)
    return rec


def collect_tokens(src: bytes) -> tuple[list[dict], dict]:
    t0 = time.perf_counter()
    toks = []
    for tok in tokenize.tokenize(io.BytesIO(src).readline):
        toks.append({
            "type": tokenize.tok_name[tok.type],
            "string": tok.string,
            "start": list(tok.start),
            "end": list(tok.end),
            "mapping_confidence": "EXACT",
        })
    raw = io.StringIO()
    for tok in tokenize.tokenize(io.BytesIO(src).readline):
        raw.write(f"{tokenize.tok_name[tok.type]:<12} {tok.string!r} {tok.start}-{tok.end}\n")
    art = write_artifact("tokens/tokens_raw.txt", raw.getvalue().encode())
    norm = write_artifact("tokens/tokens.json", json.dumps(toks, indent=1).encode())
    return toks, {"artifacts": [art, norm], "duration_ms": int((time.perf_counter() - t0) * 1000)}


def collect_ast(src: bytes) -> tuple[dict, dict]:
    t0 = time.perf_counter()
    tree = ast.parse(src.decode("utf-8"))
    raw = ast.dump(tree, indent=2, include_attributes=True)
    art = write_artifact("ast/ast_dump.txt", raw.encode())
    kinds: dict[str, int] = {}
    funcs = []
    for node in ast.walk(tree):
        kinds[type(node).__name__] = kinds.get(type(node).__name__, 0) + 1
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            funcs.append({"name": node.name, "kind": type(node).__name__,
                          "lineno": node.lineno, "end_lineno": node.end_lineno,
                          "col_offset": node.col_offset,
                          "mapping_confidence": "EXACT"})
    summary = {"node_kind_counts": dict(sorted(kinds.items(), key=lambda kv: -kv[1])),
               "definitions": funcs}
    norm = write_artifact("ast/ast_summary.json", json.dumps(summary, indent=1).encode())
    return summary, {"artifacts": [art, norm], "duration_ms": int((time.perf_counter() - t0) * 1000)}


def _code_records(code, depth: int = 0, max_depth: int = 4) -> list[dict]:
    recs = [{
        "name": code.co_name,
        "qualname": code.co_qualname,
        "argcount": code.co_argcount,
        "varnames": list(code.co_varnames),
        "names": list(code.co_names),
        "consts_noncode": [repr(c) for c in code.co_consts if not isinstance(c, type(code))],
        "nested_code_objects": [c.co_name for c in code.co_consts if isinstance(c, type(code))],
        "byte_len": len(code.co_code),
        "depth": depth,
    }]
    if depth < max_depth:
        for c in code.co_consts:
            if isinstance(c, type(code)):
                recs.extend(_code_records(c, depth + 1, max_depth))
    return recs


def collect_code_and_dis(src: bytes, filename: str) -> tuple[list[dict], list[dict], dict]:
    t0 = time.perf_counter()
    # dont_inherit=True: this collector module uses `from __future__ import annotations`;
    # compilation of user source must reflect default interpreter semantics, not ours.
    code = compile(src, filename, "exec", dont_inherit=True)  # inspection only; does NOT execute
    meta_art = write_artifact("code_object/code_objects.json",
                              json.dumps(_code_records(code), indent=1).encode())
    instrs = []
    raw = io.StringIO()

    def walk(co, depth=0):
        for ins in dis.get_instructions(co, show_caches=False):
            instrs.append({
                "code_object": co.co_name,
                "offset": ins.offset,
                "opname": ins.opname,
                "opcode": ins.opcode,
                "arg": ins.arg,
                "argval": str(ins.argval) if not isinstance(ins.argval, type(co)) else f"<code {ins.argval.co_name}>",
                "starts_line": ins.starts_line,
                "positions": list(ins.positions) if ins.positions else None,
                "mapping_confidence": "EXACT" if ins.positions else "UNAVAILABLE",
            })
        raw.write(f"\n=== code object: {co.co_name} ===\n")
        dis.dis(co, file=raw, depth=0)
        for c in co.co_consts:
            if isinstance(c, type(co)):
                walk(c, depth + 1)

    walk(code)
    dis_art = write_artifact("bytecode/dis.txt", raw.getvalue().encode())
    norm = write_artifact("bytecode/instructions.json", json.dumps(instrs, indent=1).encode())
    records = _code_records(code)
    return records, instrs, {"artifacts": [meta_art, dis_art, norm],
                             "duration_ms": int((time.perf_counter() - t0) * 1000)}


def collect_diagnostics(src: bytes, filename: str) -> dict:
    try:
        compile(src, filename, "exec")
    except SyntaxError as e:
        diag = {"error_type": "SyntaxError", "msg": e.msg, "lineno": e.lineno,
                "offset": e.offset, "end_lineno": e.end_lineno, "end_offset": e.end_offset,
                "text": (e.text or "").rstrip("\n"),
                "mapping_confidence": "EXACT"}
        art = write_artifact("diagnostics/syntax_error.json", json.dumps(diag, indent=1).encode())
        return {"diag": diag, "artifact": art}
    raise AssertionError("invalid fixture unexpectedly compiled")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    fixture = DEMO / "py_fixture.py"
    invalid = DEMO / "py_syntax_error.py"
    src = fixture.read_bytes()

    stages = []
    toks, tok_extra = collect_tokens(src)
    stages.append(stage_record("tokens", tok_extra["artifacts"], {"tokens": len(toks)},
        ["Token positions are tool-reported (EXACT); token stream is CPython-3.12-specific."],
        extra={"duration_ms": tok_extra["duration_ms"]}))

    ast_summary, ast_extra = collect_ast(src)
    stages.append(stage_record("ast", ast_extra["artifacts"],
        {"total_nodes": sum(ast_summary["node_kind_counts"].values()),
         "distinct_kinds": len(ast_summary["node_kind_counts"])},
        ["ast.dump is a debug serialization; it is genuine CPython AST data, not a public "
         "parse-tree contract (README P2). Position attributes are tool-reported (EXACT)."],
        extra={"duration_ms": ast_extra["duration_ms"]}))

    code_records, instrs, dis_extra = collect_code_and_dis(src, "py_fixture.py")
    stages.append(stage_record("code_object", dis_extra["artifacts"][:1],
        {"code_objects": len(code_records)},
        ["Code-object metadata reflects CPython 3.12.3 exactly; bytecode is NOT CPU machine "
         "code and is version-specific."],
        extra={"duration_ms": 0}))
    stages.append(stage_record("bytecode", dis_extra["artifacts"][1:],
        {"instructions": len(instrs),
         "code_objects": len({i["code_object"] for i in instrs})},
        ["dis output and instruction positions are CPython-3.12-specific; trace events are "
         "not assumed one-to-one with bytecode instructions (README P4/P5)."],
        extra={"duration_ms": dis_extra["duration_ms"]}))

    inv_src = invalid.read_bytes()
    diag = collect_diagnostics(inv_src, "py_syntax_error.py")
    stages.append(stage_record("diagnostics", [diag["artifact"]], {"syntax_error_captured": 1},
        ["Diagnostic fields (msg/lineno/offset/text) are exactly what CPython raised; fixture "
         "is never executed."],
        extra={"diagnostic": diag["diag"]}))

    git_v = "n/a"
    try:
        git_v = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                               cwd=REPO).stdout.decode().strip() or "n/a"
    except Exception:
        pass

    manifest = {
        "schema_version": "m0.v1",
        "analysis_id": "m0-python",
        "language": "python",
        "source_snapshot": {
            "files": [
                {"path": str(fixture.relative_to(REPO)).replace("\\", "/"), "sha256": sha256_bytes(src)},
                {"path": str(invalid.relative_to(REPO)).replace("\\", "/"), "sha256": sha256_bytes(inv_src)},
            ],
            "combined_sha256": sha256_bytes(src + b"\x00" + inv_src),
        },
        "tools": {"cpython": platform.python_version(),
                  "implementation": platform.python_implementation(),
                  "git_commit_at_collection": git_v},
        "stages": stages,
        "limitations_global": [
            "No top-level execution: tokenize/ast/compile/dis only; compile() does not run code.",
            "Python is not assigned LLVM or -O0/-O1/-O2 stages (README non-goals).",
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"Python proof: stages={len(stages)} tokens={len(toks)} "
          f"ast_nodes={sum(ast_summary['node_kind_counts'].values())} "
          f"instrs={len(instrs)} code_objects={len(code_records)} "
          f"diag={diag['diag']['msg']!r}@{diag['diag']['lineno']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
