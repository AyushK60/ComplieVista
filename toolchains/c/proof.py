#!/usr/bin/env python3
"""Stage 0 Deliverable B - genuine C toolchain proof (Clang/LLVM 18, Ubuntu 24.04).

Runs the real installed Clang against checked-in deterministic fixtures and writes
raw artifacts + normalized excerpts + manifest to evidence/m0/c/. Stdlib only.
Static analysis ONLY: nothing is linked into a runnable program here and no fixture
is executed. Diagnostics fixtures are never compiled past -fsyntax-only.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEMO = REPO / "demos" / "m0"
OUT = REPO / "evidence" / "m0" / "c"
TIMEOUT_S = 60


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def run(argv: list[str], cwd: Path | None = None) -> dict:
    t0 = time.perf_counter()
    proc = subprocess.run(argv, capture_output=True, timeout=TIMEOUT_S, cwd=cwd)
    ms = int((time.perf_counter() - t0) * 1000)
    return {
        "argv": argv,
        "exit_code": proc.returncode,
        "duration_ms": ms,
        "stdout_bytes": len(proc.stdout),
        "stderr_bytes": len(proc.stderr),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def tool_version(argv: list[str]) -> str:
    try:
        out = subprocess.run(argv, capture_output=True, timeout=30).stdout.decode(
            "utf-8", "replace"
        )
        return out.splitlines()[0].strip() if out else "unknown"
    except Exception as e:  # pragma: no cover - environment probe
        return f"unavailable: {e}"


def write_artifact(name: str, data: bytes) -> dict:
    p = OUT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return {"path": str(p.relative_to(REPO)).replace("\\", "/"), "sha256": sha256_bytes(data), "bytes": len(data)}


def stage_record(stage: str, inv: dict, artifacts: list[dict], counts: dict,
                 limits: list[str], obs_class: str = "TOOL_OUTPUT", stream_note: str | None = None) -> dict:
    rec = {
        "stage": stage,
        "availability": "AVAILABLE" if inv["exit_code"] == 0 else "ERROR",
        "observation_class": obs_class,
        "invocation": {k: inv[k] for k in ("argv", "exit_code", "duration_ms", "stdout_bytes", "stderr_bytes")},
        "invocation_stdout_sha256": sha256_bytes(inv["stdout"]),
        "invocation_stderr_sha256": sha256_bytes(inv["stderr"]),
        "stderr_excerpt": inv["stderr"].decode("utf-8", "replace")[:2000],
        "artifacts": artifacts,
        "counts": counts,
        "limitations": limits,
    }
    if stream_note:
        rec["stream_note"] = stream_note
    return rec


def parse_dump_tokens(text: str, max_tokens: int = 4000) -> list[dict]:
    """Parse clang -Xclang -dump-tokens lines: kind 'text'  Loc=<file:line:col>."""
    toks = []
    for line in text.splitlines():
        m = re.match(r"^(\S+)\s+'(.*)'\s+\[.*?\]\s+Loc=<([^:>]+):(\d+):(\d+)>", line)
        if m:
            toks.append({
                "kind": m.group(1),
                "text": m.group(2),
                "file": m.group(3),
                "line": int(m.group(4)),
                "col": int(m.group(5)),
                "mapping_confidence": "EXACT",
            })
            if len(toks) >= max_tokens:
                break
    return toks


def summarize_ast(ast_json: dict, max_nodes: int = 200) -> dict:
    kinds: dict[str, int] = {}

    def walk(node: dict) -> int:
        kind = node.get("kind", "?")
        kinds[kind] = kinds.get(kind, 0) + 1
        n = 1
        for k, v in node.items():
            if isinstance(v, dict) and "kind" in v:
                n += walk(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and "kind" in item:
                        n += walk(item)
        return n

    total = 0
    top = []
    inner = ast_json.get("inner", [])
    for decl in inner:
        total += walk(decl)
        rng = decl.get("range", {})
        top.append({
            "kind": decl.get("kind"),
            "name": decl.get("name"),
            "range_begin": rng.get("begin", {}).get("offset"),
            "range_end": rng.get("end", {}).get("offset"),
            "mapping_confidence": "EXACT" if rng else "UNAVAILABLE",
        })
        if len(top) >= max_nodes:
            break
    return {"node_kind_counts": dict(sorted(kinds.items(), key=lambda kv: -kv[1])),
            "total_nodes_walked": total, "top_level_declarations": top}


def summarize_ir(ir_text: str) -> dict:
    funcs = re.findall(r"^define\s+(?:[^@]*@)([\w.$-]+)", ir_text, re.M)
    blocks = re.findall(r"^([\w.$-]+):\s*(?:;.*)?$", ir_text, re.M)
    return {"functions": funcs, "function_count": len(funcs),
            "basic_block_labels": blocks[:200], "basic_block_count_derived": len(blocks),
            "mapping_confidence": "DERIVED"}


def summarize_asm(asm_text: str) -> dict:
    labels = re.findall(r"^([A-Za-z_][\w.$]*):\s*(?:#.*)?$", asm_text, re.M)
    bb = re.findall(r"^#\s*%bb\.(\d+):", asm_text, re.M)
    return {"function_labels": labels, "basic_block_comments_derived": len(bb),
            "line_count": len(asm_text.splitlines()),
            "mapping_confidence": "DERIVED"}


def find_obj_tool(basename: str) -> str:
    for cand in (f"llvm-{basename}-18", f"llvm-{basename}", basename):
        if shutil.which(cand):
            return cand
    raise FileNotFoundError(basename)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    fixture = DEMO / "c_fixture.c"
    src = fixture.read_bytes()
    clang_v = tool_version(["clang", "--version"])
    objdump = find_obj_tool("objdump")
    readelf = find_obj_tool("readelf")
    objdump_v = tool_version([objdump, "--version"])
    stages: list[dict] = []

    # Stage 1: preprocessing
    inv = run(["clang", "-E", str(fixture)])
    if inv["exit_code"] == 0:
        art = write_artifact("preprocess/preprocessed.i", inv["stdout"])
        counts = {"lines": len(inv["stdout"].decode("utf-8", "replace").splitlines())}
        stages.append(stage_record("preprocess", inv, [art], counts,
            ["Preprocessed output includes line markers; include-graph provenance not yet captured (README C1)."]))
    else:
        stages.append(stage_record("preprocess", inv, [], {}, ["clang -E failed"]))

    # Stage 2: tokens (dump may land on stdout or stderr depending on version - record which)
    inv = run(["clang", "-fsyntax-only", "-Xclang", "-dump-tokens", str(fixture)])
    dump_stream = "stdout" if inv["stdout"].strip() else ("stderr" if inv["stderr"].strip() else None)
    if dump_stream:
        dump_text = inv["stdout"] if dump_stream == "stdout" else inv["stderr"]
        art = write_artifact("tokens/dump_tokens.txt", dump_text)
        toks = parse_dump_tokens(dump_text.decode("utf-8", "replace"))
        norm = write_artifact("tokens/tokens.json",
                              json.dumps(toks, indent=1).encode())
        stages.append(stage_record("tokens", inv, [art, norm], {"tokens": len(toks)},
            ["Token dump format is clang-18-specific text; parsed fields are tool-reported (EXACT). "
             "Preprocessor-expanded token provenance not tracked."],
            stream_note=f"token dump captured on {dump_stream}"))
    else:
        stages.append(stage_record("tokens", inv, [], {}, ["no token dump produced"]))

    # Stage 3: AST JSON
    inv = run(["clang", "-fsyntax-only", "-Xclang", "-ast-dump=json", str(fixture)])
    if inv["exit_code"] == 0:
        art = write_artifact("ast/ast.json", inv["stdout"])
        try:
            summary = summarize_ast(json.loads(inv["stdout"]))
            norm = write_artifact("ast/ast_summary.json", json.dumps(summary, indent=1).encode())
            arts = [art, norm]
            counts = {"total_nodes_walked": summary["total_nodes_walked"],
                      "distinct_kinds": len(summary["node_kind_counts"])}
        except json.JSONDecodeError as e:
            arts, counts = [art], {"parse_error": str(e)}
        stages.append(stage_record("ast", inv, arts, counts,
            ["JSON AST is a clang -ast-dump serialization; node IDs/addresses are not stable "
             "semantic IDs across runs (README C3)."], ))
    else:
        stages.append(stage_record("ast", inv, [], {}, ["clang -ast-dump=json failed"]))

    # Stage 4: LLVM IR (O0)
    ir_path = OUT / "ir" / "ir_O0.ll"
    ir_path.parent.mkdir(parents=True, exist_ok=True)
    inv = run(["clang", "-S", "-emit-llvm", "-g", "-O0", "-o", str(ir_path), str(fixture)])
    if inv["exit_code"] == 0:
        ir_text = ir_path.read_text("utf-8", "replace")
        art = write_artifact("ir/ir_O0.ll", ir_path.read_bytes())
        summary = summarize_ir(ir_text)
        norm = write_artifact("ir/ir_summary.json", json.dumps(summary, indent=1).encode())
        stages.append(stage_record("ir", inv, [art, norm],
            {"functions": summary["function_count"], "basic_blocks_derived": summary["basic_block_count_derived"]},
            ["Source→IR mapping is partial even at -O0 (README C4); block inventory is "
             "text-derived (DERIVED), not a verified CFG."]))

    # Stage 5: assembly
    asm_path = OUT / "assembly" / "fixture_O0.s"
    asm_path.parent.mkdir(parents=True, exist_ok=True)
    inv = run(["clang", "-S", "-O0", "-o", str(asm_path), str(fixture)])
    if inv["exit_code"] == 0:
        asm_text = asm_path.read_text("utf-8", "replace")
        art = write_artifact("assembly/fixture_O0.s", asm_path.read_bytes())
        summary = summarize_asm(asm_text)
        norm = write_artifact("assembly/asm_summary.json", json.dumps(summary, indent=1).encode())
        stages.append(stage_record("assembly", inv, [art, norm],
            {"function_labels": len(summary["function_labels"]), "lines": summary["line_count"]},
            ["Mnemonics are not raw machine code bytes (README C6)."]))

    # Stage 6+7: object, disassembly, symbols (binary itself is gitignored; text evidence committed)
    obj_path = OUT / "object" / "c_fixture.o"
    obj_path.parent.mkdir(parents=True, exist_ok=True)
    inv = run(["clang", "-c", "-g", "-O0", "-o", str(obj_path), str(fixture)])
    if inv["exit_code"] == 0:
        obj_sha = sha256_file(obj_path)
        inv_d = run([objdump, "-d", str(obj_path)])
        art_d = write_artifact("object/disassembly.txt", inv_d["stdout"])
        inv_s = run([readelf, "-s", str(obj_path)])
        art_s = write_artifact("object/symbols.txt", inv_s["stdout"])
        text = inv_d["stdout"].decode("utf-8", "replace")
        insns = len([l for l in text.splitlines() if re.match(r"^\s+[0-9a-f]+:", l)])
        stages.append(stage_record("object", inv,
            [{"path": str(obj_path.relative_to(REPO)).replace("\\", "/"), "sha256": obj_sha,
              "bytes": obj_path.stat().st_size}, art_d, art_s],
            {"disassembled_instructions_derived": insns},
            ["Object binary excluded from git (regenerable); digest + disassembly text are the evidence.",
             f"Disassembly by {objdump} ({objdump_v}); symbols by {readelf}."]))
        stages[-1]["tool_disassembly_version"] = objdump_v

    # Stage 8: diagnostics for invalid fixtures (never compiled to binary)
    for name, kind in (("c_syntax_error.c", "syntax"), ("c_semantic_error.c", "semantic")):
        f = DEMO / name
        inv = run(["clang", "-fsyntax-only", str(f)])
        art = write_artifact(f"diagnostics/{kind}_error_stderr.txt", inv["stderr"])
        stages.append(stage_record(f"diagnostics_{kind}", inv, [art],
            {"expected_nonzero_exit": inv["exit_code"] != 0},
            [f"Diagnostic text preserved verbatim from clang stderr; fixture '{name}' is never "
             "executed or linked."]))
        # Non-zero clang exit is the EXPECTED outcome here: availability reflects that the
        # diagnostic was captured, not that compilation succeeded.
        stages[-1]["availability"] = "AVAILABLE" if inv["exit_code"] != 0 else "ERROR"
        stages[-1]["expected_exit_nonzero"] = True
        stages[-1]["diagnostic_verbatim"] = inv["stderr"].decode("utf-8", "replace")[:1500]

    manifest = {
        "schema_version": "m0.v1",
        "analysis_id": "m0-c",
        "language": "c",
        "source_snapshot": {
            "files": [{"path": str(fixture.relative_to(REPO)).replace("\\", "/"),
                        "sha256": sha256_bytes(src)}],
            "combined_sha256": sha256_bytes(src),
        },
        "tools": {"clang": clang_v, objdump: objdump_v, "readelf": tool_version([readelf, "--version"]),
                  "host": tool_version(["uname", "-sr"])},
        "stages": stages,
        "limitations_global": [
            "Static analysis only; no C execution in this deliverable (Docker feasibility is separate).",
            "No source→IR instruction mapping is claimed (UNAVAILABLE in stage 0).",
        ],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    ok = all(s["availability"] == "AVAILABLE" for s in stages
             if s["stage"].startswith(("preprocess", "tokens", "ast", "ir", "assembly", "object")))
    diag_ok = all(s["invocation"]["exit_code"] != 0 for s in stages if s["stage"].startswith("diagnostics"))
    print(f"C proof: stages={len(stages)} core_ok={ok} diagnostics_nonzero_exit={diag_ok}")
    for s in stages:
        print(f"  {s['stage']:22s} {s['availability']:9s} exit={s['invocation']['exit_code']}")
    return 0 if (ok and diag_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
