#!/usr/bin/env python3
"""Artifact-fidelity study: does CompileVista show what the real toolchain produces?

For each single-file program in sandbox/fixtures (demos + pairs) the app analyzes it inside
the pinned container (in-process API, temporary store). The SAME source is then processed
again by the *host* toolchain (WSL: clang-18, CPython 3.12) and the quantities are compared.

Metrics (app value vs independently recomputed value):
  python: token count (tokenize), AST node count (ast.walk), bytecode instruction count and
          code-object count (dis, recursive, no caches)
  c:      token count (clang -Xclang -dump-tokens), IR function count at -O0 and -O2
          (`define` lines), assembly line count (clang -S -g -O0)

Run (from repo root, inside WSL, Docker running):
    backend/.venv/bin/python eval/fidelity_study.py
Writes eval/results/fidelity.json and fidelity.md. Exit code 1 if any metric differs.
Multi-file programs (C-05) are listed as skipped, never silently dropped.
"""
from __future__ import annotations

import ast
import dis
import io
import json
import re
import subprocess
import sys
import tempfile
import time
import tokenize
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402
from app.store.db import Store  # noqa: E402

CLANG = "clang-18"
TOKEN_CAP = 8000   # the app deliberately displays at most this many tokens


def programs() -> list[tuple[str, str, Path]]:
    out = []
    for p in sorted((REPO / "sandbox/fixtures/demos").iterdir()):
        if p.is_file() and p.suffix in (".c", ".py"):
            out.append((p.stem, "c" if p.suffix == ".c" else "python", p))
    for p in sorted((REPO / "sandbox/fixtures/pairs").iterdir()):
        if p.is_file() and p.suffix in (".c", ".py"):
            out.append(("pair-" + p.name, "c" if p.suffix == ".c" else "python", p))
    return out


def clang(args: list[str], src: Path) -> str:
    # cwd "/" mirrors the container (cwd "/", file under /work) so DWARF .file lines have the
    # same shape; line counts are then comparable.
    r = subprocess.run([CLANG, *args, str(src.resolve())], capture_output=True, timeout=120,
                       cwd="/")
    return (r.stdout or b"").decode("utf-8", "replace") + (
        r.stderr.decode("utf-8", "replace") if "-dump-tokens" in " ".join(args) else "")


def oracle_python(src: Path) -> dict:
    text = src.read_text(encoding="utf-8")
    toks = len(list(tokenize.tokenize(io.BytesIO(text.encode()).readline)))
    nodes = sum(1 for _ in ast.walk(ast.parse(text)))
    code = compile(text, src.name, "exec", dont_inherit=True)  # not this script's __future__ flags
    n_ins, n_co, stack = 0, 0, [code]
    while stack:
        co = stack.pop()
        n_co += 1
        n_ins += len(list(dis.get_instructions(co, show_caches=False)))
        stack.extend(c for c in co.co_consts if isinstance(c, type(code)))
    return {"tokens": toks, "ast_nodes": nodes, "bytecode_instructions": n_ins,
            "code_objects": n_co}


def oracle_c(src: Path) -> dict:
    dump = clang(["-fsyntax-only", "-Xclang", "-dump-tokens"], src)
    tokens = sum(1 for line in dump.splitlines() if "Loc=<" in line)
    def defines(o: str) -> int:
        ir = clang(["-S", "-emit-llvm", "-g", o, "-o", "-"], src)
        return len(re.findall(r"^define\s", ir, re.M))
    asm = clang(["-S", "-g", "-O0", "-o", "-"], src)
    return {"tokens": tokens, "ir_o0_functions": defines("-O0"),
            "ir_o2_functions": defines("-O2"), "assembly_lines": len(asm.splitlines())}


def app_values(client, aid: str, language: str) -> dict:
    def counts(stage: str) -> dict:
        return client.get(f"/api/v1/analyses/{aid}/stages/{stage}").json()["counts"]
    if language == "python":
        return {"tokens": counts("tokens")["tokens"], "ast_nodes": counts("ast")["nodes"],
                "bytecode_instructions": counts("bytecode")["instructions"],
                "code_objects": counts("bytecode")["code_objects"]}
    return {"tokens": counts("tokens")["tokens"],
            "ir_o0_functions": counts("ir_o0")["functions"],
            "ir_o2_functions": counts("ir_o2")["functions"],
            "assembly_lines": counts("assembly")["lines"]}


def analyze(client, language: str, path: Path) -> str:
    r = client.post("/api/v1/sources", json={"kind": "paste", "language": language,
                                              "filename": path.name,
                                              "content": path.read_text()}).json()
    t = client.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
    a = client.post("/api/v1/analyses", json={"snapshot_id": r["snapshot_id"],
                                              "target_id": t["target_id"]}).json()
    aid = a.get("analysis_id") or a.get("id")
    for _ in range(400):
        j = client.get(f"/api/v1/analyses/{aid}").json()
        if j["status"] in ("COMPLETED", "FAILED", "BLOCKED", "CANCELLED", "TIMEOUT"):
            if j["status"] != "COMPLETED":
                raise RuntimeError(f"analysis {j['status']}: {j.get('error_code')}")
            return aid
        time.sleep(0.5)
    raise RuntimeError("analysis timed out")


def main() -> int:
    client = TestClient(create_app(store=Store(data_dir=Path(tempfile.mkdtemp()) / "d")))
    rows, bad = [], 0
    for name, lang, path in programs():
        row = {"program": name, "language": lang, "metrics": {}, "error": None}
        try:
            aid = analyze(client, lang, path)
            app = app_values(client, aid, lang)
            ref = oracle_python(path) if lang == "python" else oracle_c(path)
            for k in ref:
                want = ref[k]
                if lang == "c" and k == "tokens" and want > TOKEN_CAP:
                    want = TOKEN_CAP   # documented display cap (normalize.parse_dump_tokens_full)
                    row.setdefault("notes", []).append(
                        f"tokens capped at {TOKEN_CAP} by design (clang emitted {ref[k]})")
                match = app.get(k) == want
                bad += 0 if match else 1
                row["metrics"][k] = {"app": app.get(k), "oracle": want, "match": match}
        except Exception as e:  # noqa: BLE001 - recorded, never hidden
            row["error"] = f"{type(e).__name__}: {e}"
            bad += 1
        rows.append(row)
        print(("OK  " if not row["error"] and all(m["match"] for m in row["metrics"].values())
               else "DIFF"), name, row["error"] or "")
    skipped = ["C-05 (multi-file program; not covered by this single-file study)"]
    outdir = REPO / "eval" / "results"
    outdir.mkdir(parents=True, exist_ok=True)
    ver = subprocess.run([CLANG, "--version"], capture_output=True).stdout.decode().splitlines()[0]
    meta = {"clang": ver, "python": sys.version.split()[0], "programs": len(rows),
            "mismatches": bad, "skipped": skipped}
    (outdir / "fidelity.json").write_text(json.dumps({"meta": meta, "rows": rows}, indent=1))
    lines = [f"# Artifact fidelity study\n", f"{meta['clang']} · CPython {meta['python']} · "
             f"{meta['programs']} programs · **{bad} mismatching metrics/errors**\n",
             "| program | lang | metric | app | oracle | match |", "|---|---|---|---|---|---|"]
    for r in rows:
        if r["error"]:
            lines.append(f"| {r['program']} | {r['language']} | ERROR | {r['error']} | | no |")
        for k, m in r["metrics"].items():
            lines.append(f"| {r['program']} | {r['language']} | {k} | {m['app']} | "
                         f"{m['oracle']} | {'yes' if m['match'] else 'NO'} |")
    notes = [f"{r['program']}: {n}" for r in rows for n in r.get("notes", [])]
    lines += ["", "Notes: " + ("; ".join(notes) if notes else "none"),
              "", "Skipped: " + "; ".join(skipped)]
    (outdir / "fidelity.md").write_text("\n".join(lines) + "\n")
    print(f"\n{len(rows)} programs, {bad} mismatching metrics/errors")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
