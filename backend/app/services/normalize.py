"""M2-B/C/D normalization: worker outputs → typed stage records with capped items.

Raw artifacts are content-addressed (the audit trail); normalized items are capped
and carry per-item mapping_confidence (EXACT only where the tool reports positions;
IR/assembly relations are DERIVED; source→IR/asm mapping is UNAVAILABLE in M2).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.store.db import Store, new_id

MAX_ITEMS = 500
_DIAG_RE = re.compile(r"^(.+?):(\d+):(\d+):\s*(error|warning|note):\s*(.*)$")
# Full-coverage token parser: bracket flag group is OPTIONAL because clang omits it
# for tokens coming from included headers (the M0 main-file parser keeps its format).
_TOK_RE = re.compile(r"^(\S+)\s+'(.*)'\s+(?:\[.*?\]\s+)?Loc=<([^:>]+):(\d+):(\d+)>?(?:\s.*)?$")


def parse_dump_tokens_full(text: str, max_tokens: int = 8000) -> list[dict]:
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


def _clang_ast_nodes(ast_json: dict) -> list[dict]:
    nodes: list[dict] = []

    def walk(node: dict, parent: str | None) -> None:
        nid = f"n{len(nodes)}"
        loc = node.get("loc", {})
        rng = node.get("range", {})
        nodes.append({
            "id": nid, "parent": parent, "kind": node.get("kind", "?"),
            "name": node.get("name"),
            "line": loc.get("line"), "col": loc.get("col"),
            "offset": loc.get("offset"),
            "end_offset": rng.get("end", {}).get("offset"),
            "children": [],
            "mapping_confidence": "EXACT" if loc else "UNAVAILABLE",
        })
        for child in node.get("inner", []) or []:
            if len(nodes) < 5000:
                nodes[-1]["children"].append(walk(child, nid))
        return nid

    for decl in ast_json.get("inner", []) or []:
        if len(nodes) >= 5000:
            break
        walk(decl, None)
    return nodes


def _ir_summary(ir_text: str) -> dict:
    """Functions, blocks and REAL terminator-derived edges (DERIVED confidence).
    The entry block has no label line in LLVM IR — represented as '<entry>'."""
    functions = []
    cur: dict | None = None
    block: dict | None = None
    for line in ir_text.splitlines():
        m = re.match(r"^define\s+.*@([\w.$-]+)", line)
        if m:
            cur = {"name": m.group(1), "blocks": [], "mapping_confidence": "DERIVED"}
            block = {"label": "<entry>", "terminators": [], "successors": []}
            cur["blocks"].append(block)
            functions.append(cur)
            continue
        if cur is None:
            continue
        bm = re.match(r"^([\w.$-]+):\s*(?:;.*)?$", line)
        if bm:
            block = {"label": bm.group(1), "terminators": [], "successors": []}
            cur["blocks"].append(block)
            continue
        tm = re.match(r"^\s*(br|switch|ret|unreachable|invoke|callbr)\b", line)
        if tm and block is not None:
            op = tm.group(1)
            block["terminators"].append(op)
            for lbl in re.findall(r"label\s+%([\w.$-]+)", line):
                block["successors"].append(lbl)
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
    "c:ir_o0": ["Source→IR mapping is UNAVAILABLE in M2 (no verified instruction links); "
                "CFG edges derived from terminators (DERIVED)."],
    "c:ir_o2": ["Optimized IR from an independent -O2 build; source mapping UNAVAILABLE; "
                "interactive diff/explanations deferred to M6."],
    "c:assembly": ["Mnemonics are not machine-code bytes; source mapping UNAVAILABLE."],
    "c:object": ["Object file bytes are stored hashed; binary itself is not served."],
    "c:symbols": ["Symbol table from llvm-readelf (DERIVED parsing)."],
    "c:disassembly": ["Instruction bytes are object-level, not runtime evidence."],
    "python:tokens": ["CPython 3.12 tokenize; positions EXACT incl. Unicode offsets."],
    "python:ast": ["ast/symtable data from CPython 3.12; spans EXACT; no type inference invented."],
    "python:code_object": ["Code-object metadata is version-pinned 3.12.3."],
    "python:bytecode": ["Static disassembly; NOT runtime coverage (P5 is M4)."],
    "python:diagnostics": ["Verbatim SyntaxError fields from CPython."],
}


def ingest_stage_records(store: Store, analysis_id: str, out_dir: Path, language: str) -> int:
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
                items, truncated = _capped(toks)
                counts["tokens"] = len(toks)
                main_file = {t["file"] for t in toks}
                counts["token_files"] = len(main_file)
            elif stage == "ast" and "ast.json" in artifacts:
                try:
                    nodes = _clang_ast_nodes(json.loads(artifacts["ast.json"]))
                    items, truncated = _capped(nodes)
                    counts["ast_nodes"] = len(nodes)
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
                items, truncated = _capped(payload.get("tokens", payload.get("nodes",
                                           payload.get("instructions",
                                           payload.get("code_objects",
                                           payload.get("scopes", []))))))
                counts = payload.get("counts", counts)
                summary = {k: v for k, v in payload.items()
                           if k in ("node_kind_counts", "error_type", "msg", "lineno",
                                    "offset", "text")}
                if "error_type" in payload:
                    counts = {"syntax_errors": 1}
            if "py_bytecode_raw.txt" in artifacts:
                raw_ref = store.put_artifact(artifacts["py_bytecode_raw.txt"])
        if rec.get("stderr") is not None:
            stderr_ref = store.put_artifact(stderr_text.encode())  # empty stderr is provenance too

        store.execute(
            "INSERT OR REPLACE INTO analysis_stages (id, analysis_id, stage, availability,"
            " observation_class, exit_code, counts_json, items_json, limitations_json,"
            " raw_artifact, stderr_artifact, truncated, duration_ms)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (new_id(), analysis_id, stage, availability, "TOOL_OUTPUT", exit_code,
             json.dumps(counts), json.dumps(items),
             json.dumps(_STAGE_LIMITS.get(f"{language}:{stage}", [])), raw_ref, stderr_ref,
             int(truncated or any(a.get("truncated") for a in rec.get("artifacts", []))),
             rec.get("duration_ms", 0)))
        count += 1
    return count
