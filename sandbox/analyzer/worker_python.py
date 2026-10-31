#!/usr/bin/env python3
"""M2 trusted CPython analyzer worker — runs INSIDE the pinned, network-less container.

Static inspection ONLY via tokenize/ast/symtable/compile/dis. Never imports or
executes analyzed source; compile() does not run top-level code. Writes
already-normalized JSON artifacts plus raw disassembly to /out.
"""
from __future__ import annotations

import argparse
import ast
import dis
import hashlib
import json
import os
import platform
import symtable
import time
import tokenize
import io

manifest: dict = {"worker": "worker_python.py", "stages": [], "tool_versions": {
    "cpython": platform.python_version()}}


def save(out: str, name: str, text: str, cap: int = 8 * 1024 * 1024) -> dict:
    data = text.encode("utf-8")
    with open(os.path.join(out, name), "wb") as f:
        f.write(data[:cap])
    return {"file": name, "sha256": hashlib.sha256(data[:cap]).hexdigest(),
            "bytes": min(len(data), cap), "truncated": len(data) > cap}


def stage(out: str, name: str, payload: dict, raw: str | None = None) -> None:
    rec = {"stage": name, "exit_code": 0 if "error" not in payload else 1,
           "artifacts": [save(out, f"py_{name}.json", json.dumps(payload, indent=1))],
           "counts": payload.get("counts", {}), "duration_ms": payload.pop("duration_ms", 0)}
    if raw is not None:
        rec["artifacts"].append(save(out, f"py_{name}_raw.txt", raw))
    manifest["stages"].append(rec)
    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    src_path = os.path.join("/work", args.file)
    with open(src_path, "rb") as f:
        src = f.read()
    # PEP 263: honor the declared source encoding so AST/tokens agree with what
    # compile() sees for non-UTF-8 sources (CV-07). Falls back to utf-8/replace
    # for undecodable content; invalid encoding cookies land in diagnostics.
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(src).readline)
    except SyntaxError as e:
        stage(args.out, "diagnostics",
              {"error_type": "SyntaxError", "msg": str(e), "lineno": 1, "offset": None,
               "text": None, "mapping_confidence": "UNAVAILABLE",
               "counts": {"encoding_errors": 1}})
        return
    text = src.decode(encoding, "replace")
    manifest["source_encoding"] = encoding

    # P1 tokens (tokenize itself can raise on broken source — record it, never crash)
    t0 = time.perf_counter()
    toks = []
    tok_error = None
    try:
        for tok in tokenize.tokenize(io.BytesIO(src).readline):
            toks.append({"type": tokenize.tok_name[tok.type], "text": tok.string,
                         "start": list(tok.start), "end": list(tok.end),
                         "mapping_confidence": "EXACT"})
    except (tokenize.TokenError, SyntaxError, IndentationError) as e:
        tok_error = f"{type(e).__name__}: {e}"
    stage(args.out, "tokens",
          {"tokens": toks,
           "tokenize_error": tok_error,
           "counts": {"tokens": len(toks)},
           "duration_ms": int((time.perf_counter() - t0) * 1000)})

    # P2/P3 parse + AST + symtable
    t0 = time.perf_counter()
    tree = None
    try:
        tree = ast.parse(text, filename=os.path.basename(args.file))
        nodes = []

        def walk(node, parent):
            nid = f"n{len(nodes)}"
            rec = {"id": nid, "parent": parent,
                   "kind": type(node).__name__,
                   "line": getattr(node, "lineno", None),
                   "end_line": getattr(node, "end_lineno", None),
                   "col": getattr(node, "col_offset", None),
                   "name": getattr(node, "name", None) if isinstance(
                       node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else None,
                   "children": [],
                   "mapping_confidence": "EXACT" if hasattr(node, "lineno") else "UNAVAILABLE"}
            nodes.append(rec)
            for child in ast.iter_child_nodes(node):
                rec["children"].append(walk(child, nid))
            return nid

        walk(tree, None)
        kinds: dict[str, int] = {}
        for n in nodes:
            kinds[n["kind"]] = kinds.get(n["kind"], 0) + 1
        scopes = []
        try:
            st = symtable.symtable(text, os.path.basename(args.file), "exec")

            def walk_scope(t, depth=0):
                scopes.append({"name": t.get_name(), "type": t.get_type(),
                               "depth": depth,
                               "symbols": [{"name": s.get_name(),
                                            "global": s.is_global(),
                                            "local": s.is_local(),
                                            "free": s.is_free(),
                                            "referenced": s.is_referenced()}
                                           for s in t.get_symbols()][:200]})
                for c in t.get_children():
                    if depth < 6:
                        walk_scope(c, depth + 1)

            walk_scope(st)
        except Exception as e:  # symtable can fail where ast.parse succeeded (rare)
            scopes.append({"error": str(e)[:200]})
        stage(args.out, "ast",
              {"nodes": nodes, "node_kind_counts": kinds,
               "scopes": scopes,
               "counts": {"nodes": len(nodes), "distinct_kinds": len(kinds),
                          "scopes": len(scopes)},
               "duration_ms": int((time.perf_counter() - t0) * 1000)},
              raw=ast.dump(tree, indent=2, include_attributes=True) if tree else None)
    except SyntaxError as e:
        stage(args.out, "diagnostics",
              {"error_type": "SyntaxError", "msg": e.msg, "lineno": e.lineno,
               "offset": e.offset, "end_lineno": e.end_lineno, "end_offset": e.end_offset,
               "text": (e.text or "").rstrip("\n"), "mapping_confidence": "EXACT",
               "counts": {"syntax_errors": 1}})
        with open(os.path.join(args.out, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=1)
        return

    # P4 code objects + bytecode (compile only; nothing is executed)
    t0 = time.perf_counter()
    code = compile(src, os.path.basename(args.file), "exec", dont_inherit=True)
    code_recs, instrs, raw = [], [], io.StringIO()
    code_ids: dict[int, str] = {}

    def walk_code(co, depth=0):
        # Unique identity per code object: co_name alone collapses distinct nested
        # scopes with the same name (CV-08). qualname + path index is stable here.
        cid = f"co{len(code_recs)}:{co.co_qualname}"
        code_ids[id(co)] = cid
        code_recs.append({"id": cid, "name": co.co_name, "qualname": co.co_qualname,
                          "argcount": co.co_argcount, "varnames": list(co.co_varnames),
                          "names": list(co.co_names),
                          "consts_noncode": [repr(c) for c in co.co_consts
                                             if not isinstance(c, type(co))],
                          "depth": depth})
        # Version-pinned branch semantics (M3.5 CV-03): targets come from
        # dis.hasjabs/hasjrel of the RUNNING interpreter (3.12), never substring
        # matching. Conditional branches, FOR_ITER and SEND also fall through.
        ins_list = list(dis.get_instructions(co, show_caches=False))
        next_offset = {ins_list[k].offset: (ins_list[k + 1].offset if k + 1 < len(ins_list)
                                            else None)
                       for k in range(len(ins_list))}
        for ins in ins_list:
            branch_targets, fallthrough = [], None
            if ins.opcode in dis.hasjabs or ins.opcode in dis.hasjrel:
                branch_targets.append(ins.argval)
                if not ins.opname.startswith("JUMP_"):
                    fallthrough = next_offset.get(ins.offset)
            instrs.append({"code_object_id": cid,
                           "code_object": co.co_name, "offset": ins.offset,
                           "opname": ins.opname, "arg": ins.arg,
                           "argval": str(ins.argval) if not isinstance(ins.argval, type(co))
                           else f"<code {ins.argval.co_name}>",
                           "branch_targets": branch_targets,
                           "fallthrough": fallthrough,
                           "starts_line": ins.starts_line,
                           "positions": list(ins.positions) if ins.positions else None,
                           "mapping_confidence": "EXACT" if ins.positions else "UNAVAILABLE"})
        for c in co.co_consts:
            if isinstance(c, type(co)):
                walk_code(c, depth + 1)

    walk_code(code)
    dis.dis(code, file=raw, depth=None)
    stage(args.out, "code_object",
          {"code_objects": code_recs, "counts": {"code_objects": len(code_recs)},
           "duration_ms": 0})
    stage(args.out, "bytecode",
          {"instructions": instrs,
           "counts": {"instructions": len(instrs),
                      "code_objects": len({i["code_object_id"] for i in instrs})},
           "duration_ms": int((time.perf_counter() - t0) * 1000)},
          raw=raw.getvalue())
    with open(os.path.join(args.out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)


if __name__ == "__main__":
    main()
