import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background, Controls, MiniMap, ReactFlow, ReactFlowProvider,
  useEdgesState, useNodesState, type Edge, type Node,
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
  truncated: { nodes: boolean; edges: boolean; stage_items: boolean };
  provenance: Record<string, unknown>;
};

export type GraphSelection = {
  node: Record<string, unknown>;
  incoming: Array<Record<string, unknown>>;
  outgoing: Array<Record<string, unknown>>;
} | null;

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
  const [search, setSearch] = useState("");
  const [searchHits, setSearchHits] = useState<string[]>([]);
  const [hiddenSubtrees, setHiddenSubtrees] = useState<Set<string>>(new Set());
  const seqRef = useRef(0);
  const fetchAbortRef = useRef(0);

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
    const t0 = performance.now();
    worker.onmessage = (e: MessageEvent) => {
      if (e.data.id !== reqId) return; // stale layout result (race guard)
      setLayoutMs(e.data.layoutMs);
      if (e.data.error) { setError(`layout: ${e.data.error}`); return; }
      const pos = e.data.positions as Record<string, { x: number; y: number }>;
      const g = payload;
      const rfNodes: Node[] = g.nodes.map((n) => ({
        id: n.id as string,
        position: pos[n.id as string] ?? { x: 0, y: 0 },
        data: { raw: n },
        type: "cv",
      }));
      const rfEdges: Edge[] = g.edges.map((e, i) => ({
        id: `e${i}`, source: e.source as string, target: e.target as string,
        animated: (e.kind as string) !== "containment",
        style: {
          stroke: e.kind === "containment" ? "#3a4a5a"
            : e.kind === "cfg_branch" ? "#7fb3ff" : "#ffd479",
          strokeWidth: 1.4,
        },
        label: e.kind === "containment" ? "" : String(e.kind),
        labelShow: undefined,
      })) as Edge[];
      setNodes(rfNodes);
      setEdges(rfEdges);
    };
    const visibleNodes = g_visible_nodes(payload, hiddenSubtrees);
    const visibleEdges = g_visible_edges(payload, hiddenSubtrees);
    worker.postMessage({ id: reqId, nodes: visibleNodes, edges: visibleEdges,
                         options: { nodeWidth: NODE_W, nodeHeight: NODE_H } });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [payload, hiddenSubtrees]);

  // ---- semantic zoom ----
  const level = detailLevel(zoom);

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
      const label = semanticLabel(raw, level);
      const isSel = false;
      return (
        <div className={`cvnode group-${raw.group} conf-${String(raw.confidence ?? "").toLowerCase()}`}
             title={`kind=${raw.kind} line=${raw.line ?? "—"} confidence=${raw.confidence ?? "—"}`}
             style={{ width: NODE_W, minHeight: NODE_H }}>
          <span className="cvnode-label">{label}</span>
        </div>
      );
    },
  }), [level]);

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
        <span className="muted">
          {searchHits.length > 0 && `${searchHits.length} hit(s) · `}
          zoom level {level} ({zoom.toFixed(2)}x) · layout {layoutMs}ms ·{" "}
          {payload.nodes.length} nodes / {payload.edges.length} edges
          {(payload.truncated.nodes || payload.truncated.edges) && " · TRUNCATED"}
        </span>
      </div>
      <ReactFlowProvider>
        <ReactFlow
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
          onMove={(_e, vp) => setZoom(vp.zoom)}
          fitView
          minZoom={0.05}
          maxZoom={4}
          onlyRenderVisibleElements
          proOptions={{ hideAttribution: true }}
          nodesDraggable
        >
          <Background gap={18} color="#151b23" />
          <Controls showInteractive={false} />
          <MiniMap pannable zoomable nodeColor={() => "#2f5d8a"} />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}

function g_descendants(edges: Array<Record<string, unknown>>, roots: Set<string>): Set<string> {
  const adj = new Map<string, string[]>();
  for (const e of edges) {
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
  return out; // strictly descendants; the collapsed root itself stays visible
}

function g_visible_nodes(payload: GraphPayload, hidden: Set<string>) {
  if (!hidden.size) return payload.nodes;
  const gone = g_descendants(payload.edges, hidden);
  return payload.nodes.filter((n) => !gone.has(n.id as string));
}

function g_visible_edges(payload: GraphPayload, hidden: Set<string>) {
  if (!hidden.size) return payload.edges;
  const gone = g_descendants(payload.edges, hidden);
  return payload.edges.filter((e) => !gone.has(e.source as string)
    && !gone.has(e.target as string));
}
