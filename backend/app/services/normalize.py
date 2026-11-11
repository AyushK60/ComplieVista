"""Stage 2-B/C/D normalization: worker outputs → typed stage records with capped items.

Raw artifacts are content-addressed (the audit trail); normalized items are capped
and carry per-item mapping_confidence (EXACT only where the tool reports positions;
IR/assembly relations are DERIVED; source→IR/asm mapping is UNAVAILABLE in stage 2).
"""
from __future__ import annotations

import bisect
import json
import re
from pathlib import Path

from app.core.config import ANALYSIS_POLICY_VERSION
from app.store.db import Store, new_id

MAX_ITEMS = 500
_DIAG_RE = re.compile(r"^(.+?):(\d+):(\d+):\s*(error|warning|note):\s*(.*)$")
# Full-coverage token parser: bracket flag group is OPTIONAL because clang omits it
# for tokens coming from included headers (the stage 0 main-file parser keeps its format).
_TOK_RE = re.compile(r"^(\S+)\s+'(.*)'\s+(?:\[.*?\]\s+)?Loc=<([^:>]+):(\d+):(\d+)>?(?:\s.*)?$")


# The dump lists included headers first and the user's own file last, so a small cap here silently
# dropped every token of header-heavy programs (stdio.h and stdlib.h alone exceed 8000). The API
# still returns at most MAX_ITEMS items, own-file first; this bound is only a memory safety net.
MAX_PARSED_TOKENS = 2_000_000


def parse_dump_tokens_full(text: str, max_tokens: int = MAX_PARSED_TOKENS) -> list[dict]:
    toks = []
    for line in text.splitlines():
        m = _TOK_RE.match(line)
        if m:
            toks.append({
                "kind": m.group(1), "text": m.group(2), "file": m.group(3),
                "line": int(m.group(4)), "col": int(m.group(5)),
                "mapping_confidence": "EXACT",
            })
            if len(toks) >= max_tokens:
                break
    return toks


def _capped(seq: list, cap: int = MAX_ITEMS) -> tuple[list, bool]:
    return seq[:cap], len(seq) > cap


def _clang_ast_nodes(ast_json: dict, primary_basename: str | None = None,
                     line_of_offset=None) -> list[dict]:
    """Walk the clang JSON AST. Node ids are session-local. When primary_basename is
    given, top-level declarations from that file become the tree roots (header
    declarations stay counted but don't drown the user's code).

    Clang emits `loc.file` only when the file CHANGES in declaration order; nodes
    without it belong to the current implicit file context (CV-01). Context is
    therefore propagated sequentially across top-level declarations.
    """
    total = {"n": 0}
    nodes: list[dict] = []

    def walk(node: dict, parent: str | None) -> str:
        nid = f"n{total['n']}"
        total["n"] += 1
        loc = node.get("loc", {})
        rng = node.get("range", {})
        offset = loc.get("offset") or (rng.get("begin") or {}).get("offset")
        line, col = loc.get("line"), loc.get("col")
        confidence = "EXACT" if line is not None else "UNAVAILABLE"
        if line is None:
            # Clang places brace-delimited statements' position in range.end only
            # (no loc.line, no range.begin.line). Chain: range.end.line (EXACT),
            # then a DERIVED line computed from the exact tool-reported offset.
            eb = rng.get("end") or {}
            bb = rng.get("begin") or {}
            line, col = eb.get("line"), eb.get("col")
            if line is not None:
                confidence = "EXACT"
            elif offset is not None and line_of_offset is not None:
                line, col = line_of_offset(offset), bb.get("col")
                confidence = "DERIVED"
        nodes.append({
            "id": nid, "parent": parent, "kind": node.get("kind", "?"),
            "name": node.get("name"),
            "file": loc.get("file") or (rng.get("begin") or {}).get("file"),
            "line": line, "col": col,
            "offset": offset,
            "end_offset": (rng.get("end") or {}).get("offset"),
            "children": [],
            "mapping_confidence": confidence,
        })
        parent_index = len(nodes) - 1  # capture BEFORE walking children (Stage 3 tree fix)
        for child in node.get("inner", []) or []:
            nodes[parent_index]["children"].append(walk(child, nid))
        return nid

    def basename_str(f: str | None) -> str | None:
        return f.rsplit("/", 1)[-1] if isinstance(f, str) else None

    roots = ast_json.get("inner", []) or []
    cur_file: str | None = None
    for decl in roots:
        marker = decl.get("loc", {}).get("file")
        if isinstance(marker, str):
            cur_file = marker
        effective = marker or cur_file
        if primary_basename and basename_str(effective) != primary_basename:
            # Count header subtrees without emitting them into the tree:
            def count_all(d: dict) -> None:
                total["n"] += 1
                for c in d.get("inner", []) or []:
                    count_all(c)
            count_all(decl)
            continue
        walk(decl, None)
    return nodes, total["n"]


def _ir_summary(ir_text: str) -> dict:
    """Functions, blocks and REAL terminator-derived edges (DERIVED confidence).
    The entry block has no label line in LLVM IR - represented as '<entry>'.
    Terminators are accumulated across physical lines: LLVM prints switch case
    labels on continuation lines (CV-02). Per-block instruction text is
    extracted verbatim from the same .ll artifact (presentation extraction -
    the compilation engine is untouched); lines are whitespace-trimmed and
    capped per block with an honest truncated flag."""
    MAX_BLOCK_INSTRUCTIONS = 200
    functions = []
    cur: dict | None = None
    block: dict | None = None
    lines = ir_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^define\s+.*@([\w.$-]+)", line)
        if m:
            cur = {"name": m.group(1), "blocks": [], "mapping_confidence": "DERIVED"}
            block = {"label": "<entry>", "terminators": [], "successors": [],
                     "instructions": []}
            cur["blocks"].append(block)
            functions.append(cur)
            i += 1
            continue
        if cur is None:
            i += 1
            continue
        bm = re.match(r"^([\w.$-]+):\s*(?:;.*)?$", line)
        if bm:
            # LLVM's entry block is either unlabeled (implicit <entry>) or carries
            # the first label - merge, don't duplicate.
            if (block is not None and block["label"] == "<entry>"
                    and not block["terminators"] and not block["successors"]
                    and len(cur["blocks"]) == 1):
                block["label"] = bm.group(1)
            else:
                block = {"label": bm.group(1), "terminators": [], "successors": [],
                         "instructions": []}
                cur["blocks"].append(block)
            i += 1
            continue
        if line.startswith("}"):
            cur = None
            block = None
            i += 1
            continue
        tm = re.match(r"^\s*(br|switch|ret|unreachable|invoke|callbr)\b", line)
        if tm and block is not None:
            # Accumulate the full terminator statement: switch prints its case
            # labels inside [ ] across continuation lines without trailing commas.
            acc = line.strip()
            depth = acc.count("[") - acc.count("]")
            while (depth > 0 or acc.endswith(",")) and i + 1 < len(lines):
                i += 1
                acc += " " + lines[i].strip()
                depth = acc.count("[") - acc.count("]")
            block["terminators"].append(tm.group(1))
            if len(block["instructions"]) < MAX_BLOCK_INSTRUCTIONS:
                block["instructions"].append(acc)
            for lbl in re.findall(r"\blabel\s+%([\w.$-]+)", acc):
                block["successors"].append(lbl)
            i += 1
            continue
        if block is not None:
            stripped = line.strip()
            if stripped and not stripped.startswith(";"):
                if len(block["instructions"]) < MAX_BLOCK_INSTRUCTIONS:
                    block["instructions"].append(stripped)
                elif not block.get("instructions_truncated"):
                    block["instructions_truncated"] = True
        i += 1
    edges = sum(len(b["successors"]) for f in functions for b in f["blocks"])
    return {"functions": functions,
            "counts": {"functions": len(functions),
                       "basic_blocks": sum(len(f["blocks"]) for f in functions),
                       "cfg_edges_derived": edges}}


def _asm_labels(asm_text: str) -> dict:
    labels = re.findall(r"^([A-Za-z_][\w.$]*):\s*(?:#.*)?$", asm_text, re.M)
    return {"function_labels": labels, "counts": {"function_labels": len(labels),
                                                  "lines": len(asm_text.splitlines())}}


def _symbols(sym_text: str) -> list[dict]:
    items = []
    for line in sym_text.splitlines():
        m = re.match(r"^\s*\d+:\s*[0-9a-f]+\s+(\d+)\s+(\w+)\s+(\w+)\s+\S+\s+\S+\s+(\S+)",
                     line)
        if m:
            items.append({"size": int(m.group(1)), "type": m.group(2),
                          "binding": m.group(3), "name": m.group(4),
                          "mapping_confidence": "DERIVED"})
    return items


def _disasm_summary(text: str) -> tuple[dict, list[dict]]:
    insns = []
    for line in text.splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\s*((?:[0-9a-f]{2} )+)\s*(\S+)\s*(.*)$", line)
        if m:
            insns.append({"addr": m.group(1), "bytes": m.group(2).strip(),
                          "mnemonic": m.group(3), "operands": m.group(4).strip()[:60],
                          "mapping_confidence": "UNAVAILABLE"})
    return {"counts": {"disassembled_instructions": len(insns)}}, insns


def _diagnostics_from_stderr(stderr_text: str, stage: str) -> list[dict]:
    items = []
    for line in stderr_text.splitlines():
        m = _DIAG_RE.match(line)
        if m:
            items.append({"file": Path(m.group(1)).name, "line": int(m.group(2)),
                          "col": int(m.group(3)), "severity": m.group(4),
                          "message": m.group(5), "stage": stage,
                          "raw": line[:300],
                          "mapping_confidence": "EXACT"})
    return items


_STAGE_LIMITS = {
    "c:preprocess": ["Preprocessed text is genuine clang -E output; include-graph "
                     "provenance is not yet tracked (README C1)."],
    "c:tokens": ["Token dump is clang-specific text on stderr; locations tool-reported (EXACT); "
                 "tokens from included headers are included in the dump; macro-expanded token "
                 "provenance is ambiguous and not claimed."],
    "c:ast": ["Clang -ast-dump JSON; internal node ids are NOT durable cross-run IDs "
              "(stable ids are session-local). Source ranges EXACT."],
    "c:ir_o0": ["Source→IR mapping is UNAVAILABLE in stage 2 (no verified instruction links); "
                "CFG edges derived from terminators (DERIVED)."],
    "c:ir_o2": ["Optimized IR from an independent -O2 build; source mapping UNAVAILABLE; "
                "interactive diff/explanations deferred to stage 6."],
    "c:assembly": ["Mnemonics are not machine-code bytes; source mapping UNAVAILABLE."],
    "c:object": ["Object file bytes are stored hashed; binary itself is not served."],
    "c:symbols": ["Symbol table from llvm-readelf (DERIVED parsing)."],
    "c:disassembly": ["Instruction bytes are object-level, not runtime evidence."],
    "python:tokens": ["CPython 3.12 tokenize; positions EXACT incl. Unicode offsets."],
    "python:ast": ["ast/symtable data from CPython 3.12; spans EXACT; no type inference invented."],
    "python:code_object": ["Code-object metadata is version-pinned 3.12.3."],
    "python:bytecode": ["Static disassembly; NOT runtime coverage (P5 is stage 4)."],
    "python:diagnostics": ["Verbatim SyntaxError fields from CPython."],
}


def ingest_stage_records(store: Store, analysis_id: str, out_dir: Path, language: str,
                         primary_file: str = "", image_id: str = "") -> int:
    try:
        manifest = json.loads((out_dir / "manifest.json").read_text())
    except json.JSONDecodeError:
        raise  # orchestrator already treats a missing/invalid manifest as FAILED
    count = 0
    for rec in manifest.get("stages", []):
        stage = rec["stage"]
        artifacts = {}
        for a in rec.get("artifacts", []):
            p = out_dir / a["file"]
            if p.is_file():
                artifacts[a["file"]] = p.read_bytes()
        stderr_text = ""
        if "stderr" in rec:
            sp = out_dir / rec["stderr"]["file"]
            stderr_text = sp.read_text("utf-8", "replace") if sp.is_file() else ""

        exit_code = rec.get("exit_code", 1)
        has_output = bool(artifacts) or (language == "c" and stage == "tokens" and stderr_text)
        availability = "AVAILABLE" if exit_code == 0 else ("PARTIAL" if has_output else "ERROR")

        items: list[dict] = []
        summary: dict = {}
        truncated = False
        raw_ref = None
        stderr_ref = None
        counts = rec.get("counts", {})

        if language == "c":
            if stage == "tokens" and stderr_text:
                toks = parse_dump_tokens_full(stderr_text)
                counts["tokens"] = len(toks)
                counts["tokens_parse_capped"] = len(toks) >= MAX_PARSED_TOKENS
                files = {t["file"] for t in toks}
                counts["token_files"] = len(files)
                # Same policy as the AST walk (CV-01): the user's own file must
                # not be drowned by included-header tokens when the item cap
                # applies. Header tokens stay counted and follow their file's
                # dump order; positions are never rewritten.
                primary_base = Path(primary_file).name if primary_file else None
                if primary_base and len(files) > 1:
                    own = [t for t in toks if Path(t["file"]).name == primary_base]
                    rest = [t for t in toks if Path(t["file"]).name != primary_base]
                    counts["tokens_primary_file"] = len(own)
                    items, truncated = _capped(own + rest)
                else:
                    items, truncated = _capped(toks)
            elif stage == "ast" and "ast.json" in artifacts:
                try:
                    primary = Path(primary_file).name if primary_file else None
                    job_row = store.query_one(
                        "SELECT primary_file, snapshot_id FROM analyses WHERE id=?",
                        (analysis_id,))
                    src_bytes = b""
                    if job_row:
                        fr = store.query_one(
                            "SELECT content_sha256 FROM source_files WHERE snapshot_id=?"
                            " AND rel_path=?",
                            (job_row["snapshot_id"], job_row["primary_file"]))
                        if fr:
                            src_bytes = store.get_artifact(fr["content_sha256"])
                    nl = [i for i, byte in enumerate(src_bytes) if byte == 10]

                    def line_of_offset(off: int) -> int:
                        return bisect.bisect_right(nl, off) + 1

                    nodes, total_nodes = _clang_ast_nodes(
                        json.loads(artifacts["ast.json"]), primary, line_of_offset)
                    items, truncated = _capped(nodes)
                    counts["ast_nodes"] = total_nodes
                    counts["ast_nodes_primary_file"] = len(nodes)
                except json.JSONDecodeError:
                    # Truncated capture (huge header-heavy TU) or malformed dump:
                    # degrade THIS stage honestly, never the whole job.
                    availability = "ERROR"
                    items, truncated = [], True
                    counts["ast_nodes"] = 0
                    summary = {"parse_error": "ast.json invalid or truncated by capture cap"}
            elif stage.startswith("ir_") and any(f.startswith("ir_") for f in artifacts):
                key = next(f for f in artifacts if f.startswith("ir_"))
                summary = _ir_summary(artifacts[key].decode("utf-8", "replace"))
                counts = summary["counts"]
                items = summary["functions"]
            elif stage == "assembly" and "assembly_O0.s" in artifacts:
                summary = _asm_labels(artifacts["assembly_O0.s"].decode("utf-8", "replace"))
                counts = summary["counts"]
                items = [{"label": l, "mapping_confidence": "DERIVED"}
                         for l in summary["function_labels"]]
            elif stage == "object" and "object.bin" in artifacts:
                import hashlib as _hashlib
                obj_sha = _hashlib.sha256(artifacts["object.bin"]).hexdigest()
                summary = {"object_sha256": obj_sha, "bytes": len(artifacts["object.bin"])}
                counts = {"bytes": summary["bytes"], "object_sha256": obj_sha}
            elif stage == "symbols" and "symbols.txt" in artifacts:
                items, truncated = _capped(_symbols(
                    artifacts["symbols.txt"].decode("utf-8", "replace")))
                counts["symbols"] = len(items) if truncated else len(items)
            elif stage == "disassembly" and "disassembly.txt" in artifacts:
                summary, ins = _disasm_summary(
                    artifacts["disassembly.txt"].decode("utf-8", "replace"))
                items, truncated = _capped(ins)
                counts = summary["counts"]
            diag = _diagnostics_from_stderr(stderr_text, stage)
            if diag:
                counts["diagnostics"] = len(diag)
                items = (diag + [i for i in items if i.get("severity") not in
                                 ("error", "warning", "note")])[:MAX_ITEMS]
            raw_key = next(iter(artifacts), None)
            if raw_key:
                raw_ref = store.put_artifact(artifacts[raw_key])
            elif stage == "tokens" and stderr_text:
                raw_ref = store.put_artifact(stderr_text.encode())  # the dump IS the raw output
        else:
            key = next(iter(artifacts), None)
            if key and key.endswith(".json"):
                payload = json.loads(artifacts[key])
                if stage == "diagnostics" or "error_type" in payload:
                    items, truncated = [payload], False
                    counts = {"syntax_errors": 1}
                elif stage == "tokens":
                    # Unified token schema across languages: C dumps give line/col
                    # directly; CPython gives start=[line,col] pairs (CV-05).
                    toks = [{"kind": t.get("type"), "text": t.get("text"),
                             "line": (t.get("start") or [None])[0],
                             "col": (t.get("start") or [None, None])[1],
                             "mapping_confidence": "EXACT"}
                            for t in payload.get("tokens", [])]
                    items, truncated = _capped(toks)
                    counts = {"tokens": len(toks),
                              "tokenize_error": payload.get("tokenize_error")}
                else:
                    items, truncated = _capped(payload.get("nodes",
                                               payload.get("instructions",
                                               payload.get("code_objects",
                                               payload.get("scopes", [])))))
                    counts = payload.get("counts", counts)
                summary = {k: v for k, v in payload.items()
                           if k in ("node_kind_counts", "tokenize_error")}
            if "py_bytecode_raw.txt" in artifacts:
                raw_ref = store.put_artifact(artifacts["py_bytecode_raw.txt"])
            elif key:
                # Every Python stage's own JSON worker output is part of the raw
                # audit trail (CV-09) - persist it, not only the bytecode listing.
                raw_ref = store.put_artifact(artifacts[key])
        if rec.get("stderr") is not None:
            stderr_ref = store.put_artifact(stderr_text.encode())  # empty stderr is provenance too

        invocation = {
            "tool": rec.get("tool"),
            "argv_tail": rec.get("argv_tail"),
            "worker": manifest.get("worker"),
            "tool_versions": manifest.get("tool_versions", {}),
            "image_id": image_id,
            "policy_version": ANALYSIS_POLICY_VERSION,
        }

        store.execute(
            "INSERT OR REPLACE INTO analysis_stages (id, analysis_id, stage, availability,"
            " observation_class, exit_code, counts_json, items_json, limitations_json,"
            " raw_artifact, stderr_artifact, truncated, duration_ms, invocation_json)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (new_id(), analysis_id, stage, availability, "TOOL_OUTPUT", exit_code,
             json.dumps(counts), json.dumps(items),
             json.dumps(_STAGE_LIMITS.get(f"{language}:{stage}", [])), raw_ref, stderr_ref,
             int(truncated or any(a.get("truncated") for a in rec.get("artifacts", []))),
             rec.get("duration_ms", 0), json.dumps(invocation)))
        count += 1
    return count
