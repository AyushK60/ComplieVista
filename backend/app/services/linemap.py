"""Source <-> LLVM IR <-> assembly line linking for C (Stage C).

Everything here is DERIVED from real compiler output; nothing is guessed:

* IR:  an instruction ending in ``!dbg !N`` is linked to the source line recorded in
  metadata node ``!N = !DILocation(line: L, ...)``. Line 0 means "no line" and is not linked.
* ASM: ``.loc <file> <line> <col> ...`` directives attribute the instructions that follow
  them (until the next ``.loc``) to ``<line>`` - only when ``<file>`` is the primary source.

Both inputs must come from a build with ``-g`` (the optimization worker uses it). Without
debug info the result is simply empty and ``has_debug_info`` is false: availability is
reported, never fabricated. Pure text processing: no analyzed code is executed.
"""
from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Any

_DILOC = re.compile(r"^!(\d+)\s*=\s*(?:distinct\s+)?!DILocation\(([^)]*)\)")
_LINE_FIELD = re.compile(r"\bline:\s*(\d+)")
_INLINED = re.compile(r"\binlinedAt:")
_DBG_REF = re.compile(r"!dbg\s+!(\d+)\s*$")
_FILE_DIR = re.compile(r'^\s*\.file\s+(\d+)\s+((?:"[^"]*"\s*)+)')
_FILE_OLD = re.compile(r'^\s*\.file\s+"([^"]*)"\s*$')
_LOC = re.compile(r"^\s*\.loc\s+(\d+)\s+(\d+)\s+(\d+)")
_INSTR = re.compile(r"^\s+[A-Za-z]")          # indented, starts with a mnemonic
_DIRECTIVE = re.compile(r"^\s+\.")             # .p2align, .cfi_*, .loc ...
_IR_INSTR = re.compile(r"^\s+(?:%[\w.]+\s*=\s*)?[a-z]")


def _quoted(s: str) -> list[str]:
    return re.findall(r'"([^"]*)"', s)


def parse_ir(ir_text: str) -> dict[int, dict[str, Any]]:
    """Map 1-based IR line number -> {"line": src_line, "inlined": bool}."""
    lines = ir_text.splitlines()
    nodes: dict[int, tuple[int, bool]] = {}
    for raw in lines:
        m = _DILOC.match(raw)
        if m:
            lf = _LINE_FIELD.search(m.group(2))
            line = int(lf.group(1)) if lf else 0
            nodes[int(m.group(1))] = (line, bool(_INLINED.search(m.group(2))))
    out: dict[int, dict[str, Any]] = {}
    for i, raw in enumerate(lines, start=1):
        if raw.lstrip().startswith(("!", ";", "declare", "attributes", "source_filename",
                                    "target", "@")):
            continue
        # strip any trailing ", !tbaa !5" style metadata AFTER !dbg: find !dbg anywhere
        m = re.search(r"!dbg\s+!(\d+)", raw)
        if not m:
            continue
        node = nodes.get(int(m.group(1)))
        if node and node[0] > 0 and _IR_INSTR.match(raw):
            out[i] = {"line": node[0], "inlined": node[1]}
    return out


def parse_asm(asm_text: str, primary_name: str) -> dict[int, int]:
    """Map 1-based asm line number of an INSTRUCTION -> source line of the primary file."""
    base = os.path.basename(primary_name)
    primary_idx: set[int] = set()
    for raw in asm_text.splitlines():
        m = _FILE_DIR.match(raw)
        if m:
            parts = _quoted(m.group(2))
            if any(os.path.basename(p) == base for p in parts):
                primary_idx.add(int(m.group(1)))
    current: int | None = None
    out: dict[int, int] = {}
    for i, raw in enumerate(asm_text.splitlines(), start=1):
        m = _LOC.match(raw)
        if m:
            fidx, line = int(m.group(1)), int(m.group(2))
            current = line if (fidx in primary_idx and line > 0) else None
            continue
        if raw.lstrip().startswith(("#", ".")) or raw.rstrip().endswith(":"):
            continue
        if _INSTR.match(raw) and current is not None:
            out[i] = current
    return out


def build_linemap(source_text: str, primary_name: str, ir_text: str | None,
                  asm_text: str | None) -> dict[str, Any]:
    """Bidirectional line map for one build level."""
    ir_map = parse_ir(ir_text) if ir_text else {}
    asm_map = parse_asm(asm_text, primary_name) if asm_text else {}
    n = len(source_text.splitlines())
    by_src: dict[int, dict[str, list[int]]] = defaultdict(lambda: {"ir": [], "asm": []})
    for ln, rec in ir_map.items():
        by_src[rec["line"]]["ir"].append(ln)
    for ln, src in asm_map.items():
        by_src[src]["asm"].append(ln)
    return {
        "has_debug_info": bool(ir_map or asm_map),
        "source_lines": n,
        "ir_to_source": {str(k): v["line"] for k, v in ir_map.items()},
        "ir_inlined": sorted(k for k, v in ir_map.items() if v["inlined"]),
        "asm_to_source": {str(k): v for k, v in asm_map.items()},
        "by_source": {str(k): v for k, v in sorted(by_src.items()) if 1 <= k <= max(n, 1)},
        "counts": {"ir_instructions_linked": len(ir_map),
                   "asm_instructions_linked": len(asm_map)},
    }


def compare_levels(lo: dict[str, Any], hi: dict[str, Any]) -> dict[str, Any]:
    """What -O2 did to each source line relative to -O0, from the two real line maps.

    ``removed``: lines with code at the low level and none at the high level (folded,
    inlined away or eliminated). ``grown``: more asm instructions at the high level
    (unrolling/vectorisation/inlining). ``new``: lines with code only at the high level.
    Counts are instruction counts straight from the maps; no interpretation of *why*.
    """
    def counts(m: dict[str, Any], kind: str) -> dict[int, int]:
        return {int(k): len(v[kind]) for k, v in m["by_source"].items() if v[kind]}

    lo_a, hi_a = counts(lo, "asm"), counts(hi, "asm")
    lo_i, hi_i = counts(lo, "ir"), counts(hi, "ir")
    rows = []
    for line in sorted(set(lo_a) | set(hi_a) | set(lo_i) | set(hi_i)):
        rows.append({"line": line,
                     "ir": [lo_i.get(line, 0), hi_i.get(line, 0)],
                     "asm": [lo_a.get(line, 0), hi_a.get(line, 0)]})
    return {
        "rows": rows,
        "removed": [r["line"] for r in rows if r["asm"][0] > 0 and r["asm"][1] == 0],
        "grown": [r["line"] for r in rows if r["asm"][1] > r["asm"][0] > 0],
        "shrunk": [r["line"] for r in rows if 0 < r["asm"][1] < r["asm"][0]],
        "new": [r["line"] for r in rows if r["asm"][0] == 0 and r["asm"][1] > 0],
        "totals": {"asm": [sum(lo_a.values()), sum(hi_a.values())],
                   "ir": [sum(lo_i.values()), sum(hi_i.values())]},
    }


def experiment_linemap(store, experiment_id: str) -> dict[str, Any] | None:
    """Line maps (+ O0-vs-O2 comparison) for a finished 'opt' experiment, or None if the
    experiment/snapshot is unknown. Uses the stored full artifacts; reports truncation."""
    import json
    job = store.query_one("SELECT snapshot_id, target_id, kind FROM experiments WHERE id=?",
                          (experiment_id,))
    if not job or job["kind"] != "opt":
        return None
    tgt = store.query_one("SELECT primary_file FROM compilation_targets WHERE id=?",
                          (job["target_id"],))
    src_row = store.query_one(
        "SELECT content_sha256 FROM source_files WHERE snapshot_id=? AND rel_path=?",
        (job["snapshot_id"], tgt["primary_file"])) if tgt else None
    if not src_row:
        return None
    source = store.get_artifact(src_row["content_sha256"]).decode("utf-8", "replace")
    levels: dict[str, Any] = {}
    for st in store.query("SELECT stage, availability, result_json FROM experiment_stages"
                          " WHERE experiment_id=? ORDER BY stage", (experiment_id,)):
        if st["availability"] != "AVAILABLE":
            continue
        res = json.loads(st["result_json"])
        texts: dict[str, str | None] = {}
        truncated = False
        for kind in ("ir", "asm"):
            art = res.get(kind)
            if isinstance(art, dict) and "sha256" in art:
                texts[kind] = store.get_artifact(art["sha256"]).decode("utf-8", "replace")
                truncated = truncated or bool(art.get("truncated"))
            else:
                texts[kind] = None
        m = build_linemap(source, tgt["primary_file"], texts["ir"], texts["asm"])
        m["artifacts_truncated"] = truncated
        levels[st["stage"]] = m
    out: dict[str, Any] = {"experiment_id": experiment_id, "primary_file": tgt["primary_file"],
                           "source": source, "levels": levels}
    if "O0" in levels and "O2" in levels:
        out["compare_O0_O2"] = compare_levels(levels["O0"], levels["O2"])
    return out
