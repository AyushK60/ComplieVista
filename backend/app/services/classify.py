"""M1-D discovery & capability classification.

Bounded static inspection only: `ast.parse` on size-capped text and lexical
checks. Classification statuses distinguish "detected candidate" from
"actually verified" via a `verified` flag on every reason. Nothing here is an
execution authorization: READY_FOR_CONTROLLED_EXECUTION is never emitted in M1
(the M4 security gate governs it).
"""
from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from pathlib import Path

from app.core.config import LIMITS
from app.store.db import Store, file_id_for, new_id, now_utc, reasons_to_json

MAIN_RE = re.compile(rb"\bmain\s*\(")
MAIN_GUARD = "__main__"


def _reason(code: str, detail: str, verified: bool) -> dict:
    return {"code": code, "detail": detail[:300], "verified": verified}


def classify_files(store: Store, snapshot_id: str, files: dict[str, bytes]) -> None:
    by_lang: dict[str, list[str]] = {"python": [], "c": [], "other": []}
    for path, data in files.items():
        lang = "python" if path.endswith(".py") else ("c" if path.endswith((".c", ".h")) else "other")
        by_lang[lang].append(path)

    diagnostics: list[tuple[str, str, str]] = []
    targets: list[dict] = []

    for path in sorted(by_lang["python"]):
        t = _classify_python(path, files[path], diagnostics)
        targets.append(t)
    c_files = sorted(by_lang["c"])
    for path in c_files:
        targets.append(_classify_c(path, files[path], c_files))

    for t in targets:
        store.execute(
            "INSERT INTO compilation_targets (id, snapshot_id, kind, primary_file, status,"
            " reasons_json, created_utc) VALUES (?,?,?,?,?,?,?)",
            (f"{snapshot_id}:{t['kind']}:{file_id_for(t['primary_file'])}", snapshot_id,
             t["kind"], t["primary_file"], t["status"], reasons_to_json(t["reasons"]),
             now_utc()))
    for path, code, detail in diagnostics:
        store.execute(
            "INSERT INTO snapshot_diagnostics (id, snapshot_id, file_path, severity, code, detail)"
            " VALUES (?,?,?,?,?,?)",
            (new_id(), snapshot_id, path[:300], "warning", code, detail[:300]))


def _classify_python(path: str, data: bytes, diagnostics: list) -> dict:
    limits = LIMITS
    reasons: list[dict] = []
    text = data.decode("utf-8", "replace")
    has_main_guard = False
    imports: list[str] = []
    syntax_ok = True
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError as e:
        syntax_ok = False
        diagnostics.append((path, "PY_SYNTAX_INVALID", f"line {e.lineno}: {e.msg}"))
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".")[0])
            elif (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                  and isinstance(node.test.left, ast.Name)
                  and node.test.left.id == "__name__"):
                has_main_guard = True
        non_stdlib = sorted({m for m in imports
                             if m not in getattr(sys, "stdlib_module_names", frozenset())
                             and m not in ("__future__",)})
    else:
        non_stdlib = []

    kind = "python_script"
    if path.endswith(("__main__.py",)):
        kind = "python_package_entry"
        reasons.append(_reason("package-entry-detected",
                               "__main__.py is a package entry point", verified=True))
    reasons.append(_reason("static-analyzable",
                           "CPython tokenize/ast/dis stages can run on this file as bounded data",
                           verified=True))
    if not syntax_ok:
        reasons.append(_reason("syntax-invalid",
                               "file does not parse; diagnostics stages apply", verified=True))
    if has_main_guard:
        reasons.append(_reason("entry-guard-detected",
                               "__name__ == '__main__' guard detected lexically via AST; "
                               "this is detection, not verified runnability", verified=False))
    if non_stdlib:
        reasons.append(_reason("unverified-dependencies",
                               f"non-stdlib imports present: {', '.join(non_stdlib[:8])}; "
                               "execution-classification withheld", verified=False))
    if syntax_ok and has_main_guard and not non_stdlib:
        reasons.append(_reason("stdlib-only-entry",
                               "entry guard + stdlib-only imports: bounded execution "
                               "candidate AFTER the M4 sandbox gate", verified=False))
        status = "EXECUTABLE_CANDIDATE"
    else:
        status = "STATIC_ANALYZABLE"
    if len(data) > limits["paste_max_bytes"]:
        reasons.append(_reason("large-file", "file is large; analysis stages may be partial",
                               verified=True))
    return {"kind": kind, "primary_file": path, "status": status, "reasons": reasons}


def _classify_c(path: str, data: bytes, c_files: list[str]) -> dict:
    reasons: list[dict] = []
    if path.endswith(".h"):
        reasons.append(_reason("header", "C header: analyzable as bounded data; not compiled standalone",
                               verified=True))
        reasons.append(_reason("static-analyzable",
                               "preprocess/AST stages apply in the context of a translation unit",
                               verified=False))
        return {"kind": "c_header", "primary_file": path, "status": "STATIC_ANALYZABLE",
                "reasons": reasons}
    has_main = bool(MAIN_RE.search(data))
    reasons.append(_reason("static-analyzable",
                           "Clang preprocess/tokens/AST stages can run on this file as bounded data",
                           verified=True))
    if has_main:
        reasons.append(_reason("main-detected",
                               "a 'main(' token was found lexically; this is detection, not "
                               "verified compilability or linkability", verified=False))
        reasons.append(_reason("link-deps-unknown",
                               "headers/link dependencies not verified; multi-file context "
                               "requires real toolchain checks (M2+)", verified=False))
        status = "COMPILATION_CANDIDATE"
    else:
        reasons.append(_reason("no-main-detected",
                               "no main( token: translation unit without entry point", verified=True))
        status = "STATIC_ANALYZABLE"
    multi = [p for p in c_files if p.endswith(".c")]
    if len(multi) > 1:
        reasons.append(_reason("multi-file-context",
                               f"snapshot contains {len(multi)} .c files; a linked multi-file "
                               "build needs explicit target selection", verified=True))
    return {"kind": "c_translation_unit", "primary_file": path, "status": status,
            "reasons": reasons}


def classify_multi_file_hint(store: Store, snapshot_id: str, files: dict[str, bytes]) -> None:
    """Called by ingest for snapshots with several .c files (multi-file target hint)."""
    c_files = sorted(p for p in files if p.endswith(".c"))
    if len(c_files) < 2:
        return
    primary = next((p for p in c_files if MAIN_RE.search(files[p])), c_files[0])
    reasons = [_reason("multi-file-hint",
                       f"{len(c_files)} translation units: linked build target requires "
                       "user-selected file set and real toolchain checks (M2+)", verified=True)]
    store.execute(
        "INSERT INTO compilation_targets (id, snapshot_id, kind, primary_file, status,"
        " reasons_json, created_utc) VALUES (?,?,?,?,?,?,?)",
        (f"{snapshot_id}:c_multi_file:{file_id_for(primary)}", snapshot_id, "c_multi_file",
         primary, "COMPILATION_CANDIDATE", reasons_to_json(reasons), now_utc()))


def tokenize_probe(text: str) -> int:
    """Bounded token count probe used by tests to show safe static parsing."""
    try:
        return len(list(tokenize.generate_tokens(io.StringIO(text).readline)))
    except Exception:
        return -1
