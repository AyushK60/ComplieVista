import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background, Controls, MiniMap, ReactFlow, ReactFlowProvider,
  useEdgesState, useNodesState, useStore, type Edge, type Node,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

/**
 * M3-C interaction engine. SEMANTIC ZOOM changes visible information, not just scale:
 *   far (z<0.35): kind chips only; mid (z<0.8): +name; close (z<1.4): +line:col;
 *   very close: +offset/mapping confidence. Thresholds are deterministic.
 * All data comes from /graph endpoints (m3.graph.v1) — no invented nodes/edges.
 * Stale-result guard: every fetch carries a sequence token (M3-C race requirement).
 */

export type GraphPayload = {
  schema_version: string;
  analysis_id: string;
  stage: string;
  language: string;
  availability: string;
  counts: Record<string, unknown>;
  nodes: Array<Record<string, unknown>>;
  edges: Array<Record<string, unknown>>;
  truncated: { nodes: boolean; edges: boolean; stage_items: boolean;
    nodes_omitted?: number; edges_omitted_total?: number; edges_omitted_by_cap?: number };
  provenance: Record<string, unknown>;
};

function ZoomReporter({ onZoom }: { onZoom: (z: number) => void }) {
  const zoom = useStore((st) => st.transform[2]);
  useEffect(() => { onZoom(zoom); }, [zoom, onZoom]);
  return null;
}

export type GraphSelection = {
  node: Record<string, unknown>;
  incoming: Array<Record<string, unknown>>;
  outgoing: Array<Record<string, unknown>>;
} | null;


// ---- structural semantic zoom (M3.5 CV-05): depth-limited, artifact-backed ----
function node_depths(nodes: Array<Record<string, unknown>>,
                      edges: Array<Record<string, unknown>>): Map<string, number> {
  const incoming = new Map<string, number>();
  for (const n of nodes) incoming.set(n.id as string, 0);
  for (const e of edges) {
    if (e.kind === "containment") incoming.set(e.target as string, (incoming.get(e.target as string) ?? 0) + 1);
  }
  const depth = new Map<string, number>();
  const queue: Array<[string, number]> = [];
  for (const [id, d] of incoming) {
    if (d === 0) { depth.set(id, 0); queue.push([id, 0]); }
  }
  const adj = new Map<string, string[]>();
  for (const e of edges) {
    if (e.kind !== "containment") continue;
    if (!adj.has(e.source as string)) adj.set(e.source as string, []);
    adj.get(e.source as string)!.push(e.target as string);
  }
  while (queue.length) {
    const [id, d] = queue.shift()!;
    for (const t of adj.get(id) ?? []) {
      if (!depth.has(t) || depth.get(t)! < d + 1) {
        depth.set(t, d + 1);
        queue.push([t, d + 1]);
      }
    }
  }
  return depth;
}

function depth_limit(level: 0 | 1 | 2 | 3, language: string, stage: string): number {
  if (stage.startsWith("ir_")) return level === 0 ? 0 : 1;      // functions -> blocks
  if (stage === "bytecode") return level === 0 ? 0 : 1;          // code objects -> instructions
  return [0, 1, 3, 999][level];                                   // AST: fn -> branches -> stmts -> all
}

const NODE_W = 170;
const NODE_H = 44;

function detailLevel(zoom: number): 0 | 1 | 2 | 3 {
  if (zoom < 0.35) return 0;
  if (zoom < 0.8) return 1;
  if (zoom < 1.4) return 2;
  return 3;
}

function semanticLabel(n: Record<string, unknown>, level: number): string {
  const kind = String(n.kind ?? "?");
  const name = n.name ? String(n.name) : "";
  if (level === 0) return kind;
  if (level === 1) return name ? `${kind} · ${name}` : kind;
  if (level === 2) {
    const base = name ? `${kind} · ${name}` : kind;
    return n.line ? `${base} :${n.line}` : base;
  }
  const base = name ? `${kind} · ${name}` : kind;
  const bits = [n.line ? `:${n.line}:${n.col ?? "?"}` : null,
    n.confidence ? String(n.confidence) : null].filter(Boolean);
  return bits.length ? `${base} ${bits.join(" ")}` : base;
}

export default function GraphView({
  analysisId, stage, onSelectNode, onSelectLine,
}: {
  analysisId: string;
  stage: string;
  onSelectNode: (sel: GraphSelection) => void;
  onSelectLine: (line: number | null) => void;
}) {
  const [payload, setPayload] = useState<GraphPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [layoutMs, setLayoutMs] = useState<number | null>(null);
  const [zoom, setZoom] = useState(1);
  const labelLevel = detailLevel(zoom); // zoom drives label density only (M3.5)
  const [search, setSearch] = useState("");
  const [searchHits, setSearchHits] = useState<string[]>([]);
  const [hiddenSubtrees, setHiddenSubtrees] = useState<Set<string>>(new Set());
  const [firstRenderMs, setFirstRenderMs] = useState<number | null>(null);
  const [structuralLevel, setStructuralLevel] = useState(3);
  const level = detailLevel(zoom);
  const seqRef = useRef(0);
  const fetchAbortRef = useRef(0);
  const renderStartRef = useRef(0);
  const postedRef = useRef<{ nodes: Array<Record<string, unknown>>; edges: Array<Record<string, unknown>> }>({ nodes: [], edges: [] });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const flowRef = useRef<ReactFlowInstance<any> | null>(null);

  // Structural semantic zoom: depth-limited subgraph by zoom level (CV-05) —
  // far shows functions/roots, close shows statements/instructions. Honest:
  // nodes are hidden, never aggregated into invented parents.
  const visible = useMemo(() => {
    if (!payload) return { nodes: [], edges: [] };
    const hidden = g_descendants(payload.edges, hiddenSubtrees);
    const keepNodes = payload.nodes.filter((n) => !hidden.has(n.id as string));
    const keepEdges = payload.edges.filter((e) => !hidden.has(e.source as string)
      && !hidden.has(e.target as string));
    const limit = depth_limit(structuralLevel as 0 | 1 | 2 | 3, payload.language, payload.stage);
    if (limit >= 999) return { nodes: keepNodes, edges: keepEdges };
    const depth = node_depths(keepNodes, keepEdges);
    const inLimit = new Set(payload.nodes
      .filter((n) => (depth.get(n.id as string) ?? 0) <= limit)
      .map((n) => n.id as string));
    return {
      nodes: keepNodes.filter((n) => inLimit.has(n.id as string)),
      edges: keepEdges.filter((e) => inLimit.has(e.source as string)
        && inLimit.has(e.target as string)),
    };
  }, [payload, hiddenSubtrees, structuralLevel]);

  // ---- data fetch with stale-result guard (M3-C race requirement) ----
  useEffect(() => {
    const seq = ++seqRef.current;
    setPayload(null);
    setError(null);
    setHiddenSubtrees(new Set());
    setSearchHits([]);
    fetch(`/api/v1/analyses/${analysisId}/stages/${stage}/graph`)
      .then(async (r) => {
        if (!r.ok) {
          const j = await r.json().catch(() => ({}));
          throw new Error(j?.error?.code ?? `HTTP_${r.status}`);
        }
        return r.json();
      })
      .then((g) => { if (seq === seqRef.current) setPayload(g); })
      .catch((e) => { if (seq === seqRef.current) setError(String(e.message ?? e)); });
  }, [analysisId, stage]);

  // ---- layout in worker ----
  const [nodes, setNodes, onNodesChange] = useNodesState([] as Node[]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([] as Edge[]);
  const workerRef = useRef<Worker | null>(null);

  useEffect(() => {
    workerRef.current = new Worker(
      new URL("../graph/layout.worker.ts", import.meta.url), { type: "module" });
    return () => workerRef.current?.terminate();
  }, []);

  useEffect(() => {
    if (!payload) return;
    const worker = workerRef.current;
    if (!worker) return;
    const reqId = ++fetchAbortRef.current;
    worker.onmessage = (e: MessageEvent) => {
      if (e.data.id !== reqId) return; // stale layout result (race guard)
      setLayoutMs(e.data.layoutMs);
      if (e.data.error) { setError(`layout: ${e.data.error}`); return; }
      const pos = e.data.positions as Record<string, { x: number; y: number }>;
      // CV-01: render EXACTLY the visible subgraph that was laid out —
      // never the original full node list.
      const visibleNodes = postedRef.current.nodes;
      const visibleEdges = postedRef.current.edges;
      const rfNodes: Node[] = visibleNodes.map((n: Record<string, unknown>) => ({
        id: n.id as string,
        position: pos[n.id as string] ?? { x: 0, y: 0 },
        data: { raw: n },
        type: "cv",
      }));
      const rfEdges: Edge[] = visibleEdges.map((e: Record<string, unknown>, i: number) => ({
        id: `e${i}`, source: e.source as string, target: e.target as string,
        animated: (e.kind as string) !== "containment",
        style: {
          stroke: e.kind === "containment" ? "#3a4a5a"
            : e.kind === "cfg_branch" ? "#7fb3ff" : "#ffd479",
          strokeWidth: 1.4,
        },
      })) as Edge[];
      setNodes(rfNodes);
      setEdges(rfEdges);
      requestAnimationFrame(() => {
        setFirstRenderMs(Math.round(performance.now() - renderStartRef.current));
        // Re-fit after structural changes so the visible subgraph is on screen
        // (discrete levels: no oscillation risk with zoom-driven filtering).
        flowRef.current?.fitView({ padding: 0.12, duration: 200 });
      });
    };
    renderStartRef.current = performance.now();
    postedRef.current = { nodes: visible.nodes, edges: visible.edges };
    worker.postMessage({ id: reqId, nodes: visible.nodes, edges: visible.edges,
                         options: { nodeWidth: NODE_W, nodeHeight: NODE_H } });
  }, [payload, hiddenSubtrees, structuralLevel]);

  // ---- collapse: mark root; its descendants (excluding the root) are hidden ----
  const toggleCollapse = useCallback((nodeId: string) => {
    setHiddenSubtrees((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }, [payload]);

  const nodeTypes = useMemo(() => ({
    cv: function CvNode({ data }: { data: { raw: Record<string, unknown> } }) {
      const raw = data.raw;
      const label = semanticLabel(raw, labelLevel);
      const isSel = false;
      return (
        <div className={`cvnode group-${raw.group} conf-${String(raw.confidence ?? "").toLowerCase()}`}
             title={`kind=${raw.kind} line=${raw.line ?? "—"} confidence=${raw.confidence ?? "—"}`}
             style={{ width: NODE_W, minHeight: NODE_H }}>
          <span className="cvnode-label">{label}</span>
        </div>
      );
    },
  }), [labelLevel]);

  // ---- search ----
  const runSearch = () => {
    if (!payload || !search.trim()) { setSearchHits([]); return; }
    const q = search.trim().toLowerCase();
    const hits = payload.nodes
      .filter((n) => JSON.stringify({ k: n.kind, n: n.name, t: n.text ?? "" })
        .toLowerCase().includes(q))
      .map((n) => n.id as string);
    setSearchHits(hits);
  };

  const selectedRef = useRef<string | null>(null);
  const onNodeClick = useCallback((_e: unknown, node: Node) => {
    const raw = (node.data as { raw: Record<string, unknown> }).raw;
    selectedRef.current = node.id;
    const incoming = (payload?.edges ?? []).filter((e) => e.target === node.id);
    const outgoing = (payload?.edges ?? []).filter((e) => e.source === node.id);
    onSelectNode({ node: raw, incoming, outgoing });
    const line = raw.line as number | null;
    onSelectLine(typeof line === "number" ? line : null);
  }, [payload, onSelectNode, onSelectLine]);

  if (error) {
    return <div className="graphwrap"><p className="err">{error}</p>
      <p className="muted">Table and raw views remain available for this stage.</p></div>;
  }
  if (!payload) return <p className="muted">Laying out graph…</p>;
  if (!payload.nodes.length) {
    return <p className="muted">This stage produced no graph nodes — use the table/raw views.</p>;
  }

  const hitSet = new Set(searchHits);
  return (
    <div className="graphwrap" data-level={level}>
      <div className="graphtoolbar">
        <input className="search" placeholder="Search nodes (kind/name)…"
               value={search} onChange={(e) => setSearch(e.target.value)}
               onKeyDown={(e) => { if (e.key === "Enter") runSearch(); }}
               aria-label="search graph nodes" />
        <button onClick={runSearch}>Search</button>
        <span className="detaillevels" role="group" aria-label="structural detail level">
          {["Roots", "Level 1", "Level 2", "Full"].map((label, lv) => (
            <button key={label} role="button"
                    aria-pressed={structuralLevel === lv}
                    className={structuralLevel === lv ? "tab active" : "tab"}
                    onClick={() => setStructuralLevel(lv)}>{label}</button>
          ))}
        </span>
        <span className="muted">
          {searchHits.length > 0 && `${searchHits.length} hit(s) · `}
          {visible.nodes.length}/{payload.nodes.length} nodes · layout {layoutMs}ms
          {firstRenderMs != null && ` · first render ${firstRenderMs}ms`}
          {(payload.truncated.nodes || payload.truncated.edges) && " · TRUNCATED"}
          {(payload.truncated.nodes_omitted ?? 0) > 0 &&
            ` · ${payload.truncated.nodes_omitted} nodes omitted by cap`}
        </span>
      </div>
      <ReactFlowProvider>
        <ReactFlow
          onInit={(instance) => { flowRef.current = instance; }}
          nodes={nodes.map((n) => ({
            ...n,
            className: [
              hitSet.size && !hitSet.has(n.id) ? "dimmed" : "",
              hitSet.has(n.id) ? "hit" : "",
              hiddenSubtrees.has(n.id) ? "collapsed-root" : "",
            ].join(" "),
          }))}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          onNodeDoubleClick={(_e, node) => toggleCollapse(node.id)}
          fitView
          minZoom={0.05}
          maxZoom={4}
          onlyRenderVisibleElements
          proOptions={{ hideAttribution: true }}
          nodesDraggable
        >
          <ZoomReporter onZoom={setZoom} />
          <Background gap={18} color="#151b23" />
          <Controls showInteractive={false} />
          <MiniMap pannable zoomable nodeColor={() => "#2f5d8a"} />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}

// F01: subtree collapse follows CONTAINMENT edges only. CFG branch/fallthrough
// edges (which form cycles) must never pull the collapsed root or unrelated
// control flow into the hidden set.
function g_descendants(edges: Array<Record<string, unknown>>, roots: Set<string>): Set<string> {
  const adj = new Map<string, string[]>();
  for (const e of edges) {
    if (e.kind !== "containment") continue;
    const s = e.source as string;
    if (!adj.has(s)) adj.set(s, []);
    adj.get(s)!.push(e.target as string);
  }
  const out = new Set<string>();
  const stack = [...roots];
  while (stack.length) {
    const cur = stack.pop()!;
    for (const t of adj.get(cur) ?? []) {
      if (!out.has(t)) { out.add(t); stack.push(t); }
    }
  }
  return out; // strictly containment descendants; roots always stay visible
}


