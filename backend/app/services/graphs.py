"""M3-A graph adapters: typed, versioned graph views derived ONLY from stored
M2.5 normalized stage items (which themselves derive from real tool outputs).

Graph schema m3.graph.v1. Nothing here invents nodes/edges: AST containment edges
mirror the captured parent/child structure (EXACT), CFG successor edges mirror real
terminator data (DERIVED), bytecode jump edges mirror real jump targets (DERIVED).
Source→IR/assembly mapping remains UNAVAILABLE — no such edges are ever produced.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.core.config import LIMITS
from app.store.db import Store

SCHEMA_VERSION = "m3.graph.v1"
MAX_NODES = 2000
MAX_EDGES = 4000

_JUMP_OPS = ("JUMP", "POP_JUMP_IF", "JUMP_IF", "SEND",)  # CPython 3.12 branch family


class GraphError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _capped(nodes: list, edges: list) -> tuple[list, list, bool, bool]:
    return (nodes[:MAX_NODES], edges[:MAX_EDGES],
            len(nodes) > MAX_NODES, len(edges) > MAX_EDGES)


def _ast_graph(items: list[dict], analysis_id: str, stage: str) -> tuple[list, list]:
    """AST containment graph from normalized clang/CPython AST items."""
    nodes, edges = [], []
    seen_pairs: set[tuple[str, str]] = set()
    for n in items:
        nodes.append({
            "id": f"{analysis_id}:{stage}:{n['id']}",
            "kind": n.get("kind"), "name": n.get("name"),
            "line": n.get("line"), "col": n.get("col"),
            "offset": n.get("offset"),
            "confidence": n.get("mapping_confidence", "UNAVAILABLE"),
            "group": "ast",
        })
    index = {n["id"]: n for n in nodes}

    def add_edge(src: str, dst: str, confidence: str) -> None:
        if src in index and dst in index and (src, dst) not in seen_pairs:
            seen_pairs.add((src, dst))
            edges.append({"source": src, "target": dst, "kind": "containment",
                          "confidence": confidence})

    for n in items:
        target = f"{analysis_id}:{stage}:{n['id']}"
        parent = n.get("parent")
        if parent is not None:
            add_edge(f"{analysis_id}:{stage}:{parent}", target,
                     n.get("mapping_confidence", "UNAVAILABLE"))
        for child_id in n.get("children") or []:
            add_edge(target, f"{analysis_id}:{stage}:{child_id}",
                     n.get("mapping_confidence", "UNAVAILABLE"))
    return nodes, edges


def _cfg_graph(items: list[dict], analysis_id: str, stage: str) -> tuple[list, list]:
    """LLVM function/basic-block CFG graph from real terminator successors."""
    nodes, edges = [], []
    for fn in items:
        fid = f"{analysis_id}:{stage}:fn:{fn['name']}"
        nodes.append({"id": fid, "kind": "function", "name": fn["name"],
                      "confidence": "DERIVED", "group": "cfg"})
        for b in fn.get("blocks", []):
            bid = f"{analysis_id}:{stage}:bb:{fn['name']}:{b['label']}"
            nodes.append({"id": bid, "kind": "basic_block", "name": b["label"],
                          "function": fn["name"],
                          "terminators": b.get("terminators", []),
                          "confidence": "DERIVED", "group": "cfg"})
            edges.append({"source": fid, "target": bid, "kind": "containment",
                          "confidence": "DERIVED"})
        seen_pairs = set()
        for b in fn.get("blocks", []):
            bid = f"{analysis_id}:{stage}:bb:{fn['name']}:{b['label']}"
            for succ in b.get("successors", []):
                sid = f"{analysis_id}:{stage}:bb:{fn['name']}:{succ}"
                pair = (bid, sid)
                if sid not in {n["id"] for n in nodes} or pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                edges.append({"source": bid, "target": sid, "kind": "cfg_branch",
                              "confidence": "DERIVED"})
    return nodes, edges


def _bytecode_graph(items: list[dict], analysis_id: str, stage: str) -> tuple[list, list]:
    """Code-object/instruction map; jump edges only from real jump targets (DERIVED)."""
    nodes, edges = [], []
    offsets: dict[tuple[str, int], str] = {}
    for ins in items:
        cid = ins.get("code_object_id") or ins.get("code_object")
        key = (cid, ins.get("offset"))
        offsets[key] = f"{analysis_id}:{stage}:ins:{cid}:{ins.get('offset')}"
    code_nodes: dict[str, dict] = {}
    for ins in items:
        cid = ins.get("code_object_id") or ins.get("code_object")
        if cid not in code_nodes:
            code_nodes[cid] = {
                "id": f"{analysis_id}:{stage}:co:{cid}", "kind": "code_object",
                "name": cid, "confidence": "EXACT", "group": "bytecode"}
            nodes.append(code_nodes[cid])
        nid = f"{analysis_id}:{stage}:ins:{cid}:{ins.get('offset')}"
        nodes.append({"id": nid, "kind": "instruction",
                      "name": f"{ins.get('offset')} {ins.get('opname')}",
                      "opname": ins.get("opname"), "argval": str(ins.get("argval")),
                      "line": (ins.get("positions") or [None])[0]
                      if ins.get("positions") else ins.get("starts_line"),
                      "confidence": "EXACT" if ins.get("positions") else "UNAVAILABLE",
                      "group": "bytecode"})
        edges.append({"source": f"{analysis_id}:{stage}:co:{cid}", "target": nid,
                      "kind": "containment", "confidence": "EXACT"})
    for ins in items:
        opname = ins.get("opname", "")
        if "JUMP" not in opname:
            continue
        target_off = ins.get("argval")
        if isinstance(target_off, str) and target_off.isdigit():
            target_off = int(target_off)
        if not isinstance(target_off, int):
            continue
        cid = ins.get("code_object_id") or ins.get("code_object")
        src = f"{analysis_id}:{stage}:ins:{cid}:{ins.get('offset')}"
        dst = offsets.get((cid, target_off))
        if dst:
            edges.append({"source": src, "target": dst, "kind": "bytecode_branch",
                          "confidence": "DERIVED"})
    return nodes, edges


def build_graph(store: Store, analysis_id: str, stage: str) -> dict:
    job = store.query_one("SELECT * FROM analyses WHERE id=?", (analysis_id,))
    if not job:
        raise GraphError("NOT_FOUND", "unknown analysis id", 404)
    rec = store.query_one("SELECT * FROM analysis_stages WHERE analysis_id=? AND stage=?",
                          (analysis_id, stage))
    if not rec:
        raise GraphError("NOT_FOUND", f"stage {stage!r} not present for this analysis", 404)

    graphable = {"ast": "ast", "ir_o0": "cfg", "ir_o2": "cfg", "bytecode": "bytecode"}
    if stage not in graphable:
        raise GraphError("GRAPH_UNSUPPORTED",
                         f"stage {stage!r} has no graph representation "
                         "(table/raw views remain available)")

    items = json.loads(rec["items_json"] or "[]")
    language = job["language"]
    if stage == "ast":
        nodes, edges = _ast_graph(items, analysis_id, stage)
    elif stage.startswith("ir_"):
        nodes, edges = _cfg_graph(items, analysis_id, stage)
    else:
        nodes, edges = _bytecode_graph(items, analysis_id, stage)

    nodes, edges, nodes_trunc, edges_trunc = _capped(nodes, edges)
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_id": analysis_id,
        "stage": stage,
        "language": job["language"],
        "availability": rec["availability"],
        "counts": {**json.loads(rec["counts_json"] or "{}"),
                   "graph_nodes": len(nodes), "graph_edges": len(edges)},
        "nodes": nodes,
        "edges": edges,
        "truncated": {"nodes": nodes_trunc, "edges": edges_trunc,
                      "stage_items": bool(rec["truncated"])},
        "provenance": {
            "raw_artifact_sha256": rec["raw_artifact"],
            "stderr_artifact_sha256": rec["stderr_artifact"],
            "invocation": json.loads(rec["invocation_json"] or "{}"),
            "source_combined_sha256": job["source_combined_sha256"],
        },
    }
