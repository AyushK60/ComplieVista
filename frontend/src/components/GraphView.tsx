import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background, Controls, Handle, MiniMap, Position, ReactFlow, ReactFlowProvider,
  useEdgesState, useNodesState, useStore, type Edge, type Node,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

/**
 * M8 Part-2 graph engine. Layout: tidy tree for syntax trees (worker, over
 * containment edges), top-down layered CFG for IR. All data comes from
 * /graph endpoints (m3.graph.v1) — no invented nodes/edges.
 *
 * Framing contract: the default view frames a readable, meaningful region
 * (structural Level 2), never the whole tree squeezed to illegibility; the
 * full-tree overview is an explicit action. Selection shows its ancestry path;
 * unselected regions recede slightly but stay legible.
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

// ---- node categories (restrained, semantic — never a rainbow) ----
export function nodeCategory(raw: Record<string, unknown>): string {
  const k = String(raw.kind ?? "");
  if (raw.group === "cfg") return k === "function" ? "cat-decl" : "cat-block";
  if (/^Implicit/.test(k)) return "cat-synthetic";
  if (/Decl$/.test(k) || k === "Module" || k === "FunctionDef" || k === "ClassDef") return "cat-decl";
  if (/Literal$/.test(k) || k === "Constant" || k === "JoinedStr") return "cat-literal";
  if (k === "Name" || k === "arg" || k === "Load" || k === "Store" || k === "DeclRefExpr"
      || k === "Global" || k === "NonLocalDecl") return "cat-name";
  if (/Operator$/.test(k) || /^(BinOp|UnaryOp|Compare|BoolOp|Add|Sub|Mult|Div|Mod|Lt|Gt|LtE|GtE|Eq|NotEq|Is|In|Not|And|Or|UAdd|USub|Invert)$/.test(k))
    return "cat-op";
  if (/Stmt$/.test(k) || /^(If|For|While|Return|Assign|AugAssign|AnnAssign|Try|With|Raise|Break|Continue|Pass|Assert|Delete)$/.test(k))
    return "cat-stmt";
  if (/Expr$/.test(k) || k === "Call" || k === "Comprehension" || k === "arguments"
      || k === "keyword" || k === "Starred" || k === "Slice") return "cat-expr";
  return "cat-expr";
}

const SYNTHETIC_KINDS = /^Implicit/;

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
  return [0, 1, 2, 999][level];                                   // AST: fn -> stmts -> all (default = readable)
}

const NODE_W = 172;
const NODE_H = 46;

function semanticLabel(n: Record<string, unknown>): { kind: string; value: string; line: number | null } {
  const kind = String(n.kind ?? "?");
  const name = n.name ? String(n.name) : "";
  const text = n.text != null && String(n.text).length ? String(n.text).slice(0, 18) : "";
  const value = name || text;
  return { kind, value, line: typeof n.line === "number" ? n.line : null };
}

export default function GraphView({
  analysisId, stage, onSelectNode, onSelectLine, focusLine, guided, onNavigateStage, fullscreen,
}: {
  analysisId: string;
  stage: string;
  onSelectNode: (sel: GraphSelection) => void;
  onSelectLine: (line: number | null) => void;
  /** source line clicked in the Source Dock — focuses the shallowest AST node there */
  focusLine?: number | null;
  guided?: boolean;
  onNavigateStage?: (stage: string) => void;
  fullscreen?: boolean;
}) {
  const [payload, setPayload] = useState<GraphPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [layoutMs, setLayoutMs] = useState<number | null>(null);
  const [zoom, setZoom] = useState(1);
  const [search, setSearch] = useState("");
  const [searchHits, setSearchHits] = useState<string[]>([]);
  const [hiddenSubtrees, setHiddenSubtrees] = useState<Set<string>>(new Set());
  const [structuralLevel, setStructuralLevel] = useState(2);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hideSynthetic, setHideSynthetic] = useState(false);
  const [guidedStep, setGuidedStep] = useState(0);
  const [metrics, setMetrics] = useState<{ total: number; visible: number; edges: number; layoutMs: number; initialZoom: number } | null>(null);
  const [layoutTick, setLayoutTick] = useState(0);
  const nodesRef = useRef<Node[]>([]);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const pendingFitRef = useRef(false);
  const initialFrameDoneRef = useRef(false);
  const payloadRef = useRef<GraphPayload | null>(null);
  payloadRef.current = payload;

  /** frame the laid-out region: zoom clamped to [0.5, 1.05] so text stays
   * legible and small graphs never blow up. Computed from layout bounds —
   * xyflow's fitView raced measurement and ignored the floor. */
  // Legibility floor: 11px mono at zoom 0.7 is the smallest readable size.
  // When the framed region needs less, keep it centered; when it needs more,
  // anchor on the region's top (the selected function header stays visible).
  const MIN_READ_ZOOM = 0.66; // below this, 11px labels blur; near-misses prefer fitting over clipping
  const applyFrame = useCallback((ids?: Set<string>, anchorId?: string) => {
    const flow = flowRef.current;
    const nds = nodesRef.current;
    if (!flow || !nds.length) return;
    const subset = ids ? nds.filter((n) => ids.has(n.id)) : nds;
    if (!subset.length) return;
    const el = document.querySelector<HTMLElement>(".graphwrap");
    const vw = (el?.clientWidth ?? 900) - 24, vh = (el?.clientHeight ?? 500) - 24;
    const x1 = Math.min(...subset.map((n) => n.position.x));
    const y1 = Math.min(...subset.map((n) => n.position.y));
    const x2 = Math.max(...subset.map((n) => n.position.x)) + NODE_W;
    const y2 = Math.max(...subset.map((n) => n.position.y)) + NODE_H;
    const w = x2 - x1, h = y2 - y1;
    const raw = Math.min(vw / w, vh / h, 1.05);
    const zoom = Math.max(MIN_READ_ZOOM, raw);
    // when the region fits, center it; otherwise keep the SELECTED node in
    // view (never clipped) and let the rest pan
    const anchor = anchorId ? nds.find((n) => n.id === anchorId) : undefined;
    const cx = raw < MIN_READ_ZOOM && anchor ? anchor.position.x + NODE_W / 2 : x1 + w / 2;
    const cy = raw < MIN_READ_ZOOM && anchor ? anchor.position.y + NODE_H / 2
      : h * zoom > vh ? y1 + 70 : y1 + h / 2;
    flow.setViewport({
      x: vw / 2 - cx * zoom,
      y: vh / 2 - cy * zoom,
      zoom,
    }, { duration: 220 });
  }, []);
  const seqRef = useRef(0);
  const fetchAbortRef = useRef(0);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const flowRef = useRef<any>(null);
  const postedRef = useRef<{ nodes: Array<Record<string, unknown>>; edges: Array<Record<string, unknown>> }>({ nodes: [], edges: [] });
  const initialZoomRef = useRef(0);
  const fitRequestRef = useRef<(() => void) | null>(null);

  const isTreeStage = stage === "ast";

  // ---- visible subgraph: hidden subtrees + synthetic filter + depth limit ----
  const visible = useMemo(() => {
    if (!payload) return { nodes: [], edges: [] };
    let keepNodes = payload.nodes;
    let keepEdges = payload.edges;
    if (hideSynthetic) {
      const off = new Set(payload.nodes
        .filter((n) => SYNTHETIC_KINDS.test(String(n.kind ?? "")))
        .map((n) => n.id as string));
      keepNodes = keepNodes.filter((n) => !off.has(n.id as string));
      keepEdges = keepEdges.filter((e) => !off.has(e.source as string) && !off.has(e.target as string));
    }
    const hidden = g_descendants(keepEdges, hiddenSubtrees);
    keepNodes = keepNodes.filter((n) => !hidden.has(n.id as string));
    keepEdges = keepEdges.filter((e) => !hidden.has(e.source as string)
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
  }, [payload, hiddenSubtrees, structuralLevel, hideSynthetic]);

  // ancestry helpers (containment edges of the FULL payload)
  const parentOf = useMemo(() => {
    const m = new Map<string, string>();
    for (const e of payload?.edges ?? []) {
      if (e.kind === "containment") m.set(e.target as string, e.source as string);
    }
    return m;
  }, [payload]);
  const childCount = useMemo(() => {
    const m = new Map<string, number>();
    for (const e of payload?.edges ?? []) {
      if (e.kind === "containment") m.set(e.source as string, (m.get(e.source as string) ?? 0) + 1);
    }
    return m;
  }, [payload]);
  const descendantCount = useMemo(() => {
    const adj = new Map<string, string[]>();
    for (const e of payload?.edges ?? []) {
      if (e.kind !== "containment") continue;
      if (!adj.has(e.source as string)) adj.set(e.source as string, []);
      adj.get(e.source as string)!.push(e.target as string);
    }
    const memo = new Map<string, number>();
    const count = (id: string, seen: Set<string>): number => {
      if (memo.has(id)) return memo.get(id)!;
      if (seen.has(id)) return 0;
      seen.add(id);
      let n = 0;
      for (const c of adj.get(id) ?? []) n += 1 + count(c, seen);
      memo.set(id, n);
      return n;
    };
    for (const nd of payload?.nodes ?? []) count(nd.id as string, new Set());
    return memo;
  }, [payload]);

  const ancestryPath = useMemo(() => {
    const path = new Set<string>();
    let cur = selectedId;
    while (cur) { path.add(cur); cur = parentOf.get(cur) ?? null; }
    return path;
  }, [selectedId, parentOf]);

  // ---- data fetch with stale-result guard ----
  useEffect(() => {
    const seq = ++seqRef.current;
    setPayload(null);
    setError(null);
    setHiddenSubtrees(new Set());
    setSearchHits([]);
    setSelectedId(null);
    setHideSynthetic(false);
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
  nodesRef.current = nodes;
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
      const visibleNodes = postedRef.current.nodes;
      const visibleEdges = postedRef.current.edges;
      const rfNodes: Node[] = visibleNodes.map((n: Record<string, unknown>) => ({
        id: n.id as string,
        position: pos[n.id as string] ?? { x: 0, y: 0 },
        data: { raw: n, childCount: childCount.get(n.id as string) ?? 0,
                collapsedCount: hiddenSubtrees.has(n.id as string)
                  ? (descendantCount.get(n.id as string) ?? 0) : 0 },
        type: "cv",
      }));
      const rfEdges: Edge[] = visibleEdges.map((e: Record<string, unknown>, i: number) => ({
        id: `e${i}`, source: e.source as string, target: e.target as string,
        className: e.kind === "containment" ? "edge-containment" : "edge-branch",
        animated: (e.kind as string) !== "containment",
      })) as Edge[];
      setNodes(rfNodes);
      setEdges(rfEdges);
      // fit runs in a post-commit effect (layoutTick) — a rAF here raced the
      // React commit and fitted against the previous (empty) node set
      setMetrics({
        total: payload.nodes.length,
        visible: visibleNodes.length,
        edges: visibleEdges.length,
        layoutMs: e.data.layoutMs,
        initialZoom: initialZoomRef.current,
      });
      setLayoutTick((t) => t + 1);
    };
    postedRef.current = { nodes: visible.nodes, edges: visible.edges };
    worker.postMessage({
      id: reqId, nodes: visible.nodes, edges: visible.edges,
      options: {
        strategy: isTreeStage ? "tree" : "layered",
        nodeWidth: NODE_W, nodeHeight: NODE_H,
      },
    });
  }, [payload, hiddenSubtrees, structuralLevel, hideSynthetic, isTreeStage, childCount, descendantCount]);

  // Default framing, run once per payload: frame the program's first function
  // (its source meaning) and select it, or the whole visible graph when the
  // payload is small. Idempotent so the post-commit effect and the onInit
  // pending-fit path can both call it without double work.
  const frameInitial = useCallback(() => {
    try {
    if (initialFrameDoneRef.current || !flowRef.current) return;
    initialFrameDoneRef.current = true;
    const nds = nodesRef.current;
    if (!nds.length) { initialFrameDoneRef.current = false; return; }
    const visibleIds = new Set(nds.map((n) => n.id as string));
    const fnRoots = nds.filter((n) => /^(FunctionDecl|FunctionDef)$/.test(String((n.data as { raw?: Record<string, unknown> })?.raw?.kind ?? "")));
    if ((payloadRef.current?.nodes.length ?? 0) > 20 && fnRoots.length) {
      const sorted = [...fnRoots].sort((a, b) =>
        Number(((a.data as { raw?: Record<string, unknown> })?.raw?.line) ?? 0)
        - Number(((b.data as { raw?: Record<string, unknown> })?.raw?.line) ?? 0));
      const pick = sorted[0].id as string;
      const sub = new Set([pick, ...g_descendants(payloadRef.current?.edges ?? [], new Set([pick]))]
        .filter((id) => visibleIds.has(id)));
      applyFrame(sub, pick);
      selectNode(pick);
      return;
    }
    applyFrame();
    } catch (err) {
      ((window as unknown as Record<string, unknown>).__fitErr = String(err));
      initialFrameDoneRef.current = false;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applyFrame]);

  // frame the freshly laid-out region once the nodes are committed. If the
  // ReactFlow instance is not initialized yet (layout can beat onInit), the
  // fit is marked pending and applied by onInit.
  useEffect(() => {
    if (!layoutTick) return;
    let cancelled = false;
    let tries = 0;
    const tryFit = () => {
      if (cancelled) return;
      if (!flowRef.current) {
        if (++tries > 90) return; // ~1.5s of frames, then give up honestly
        requestAnimationFrame(tryFit);
        return;
      }
      try {
        frameInitial();
        requestAnimationFrame(() => {
          initialZoomRef.current = flowRef.current?.getZoom() ?? 0;
          setMetrics((m) => (m ? { ...m, initialZoom: initialZoomRef.current } : m));
        });
      } catch (err) {
        ((window as unknown as Record<string, unknown>).__fitErr = String(err));
      }
    };
    const id = requestAnimationFrame(tryFit);
    return () => { cancelled = true; cancelAnimationFrame(id); };
  }, [layoutTick, frameInitial]);

  // re-frame when the canvas expands to full screen (container size changes)
  useEffect(() => {
    if (!fullscreen) return;
    const id = requestAnimationFrame(() => applyFrame());
    return () => cancelAnimationFrame(id);
  }, [fullscreen, applyFrame]);

  // re-frame when the container is resized (dock drag, window resize) so the
  // graph never disappears or misframes after layout changes
  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    let t: number | undefined;
    const ro = new ResizeObserver(() => {
      window.clearTimeout(t);
      t = window.setTimeout(() => applyFrame(), 180);
    });
    ro.observe(el);
    return () => { ro.disconnect(); window.clearTimeout(t); };
  }, [applyFrame]);

  // ---- collapse: mark root; its descendants (excluding the root) are hidden ----
  const toggleCollapse = useCallback((nodeId: string) => {
    setHiddenSubtrees((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }, []);

  const labelLevel = zoom < 0.35 ? 0 : zoom < 0.7 ? 1 : 2;

  const nodeTypes = useMemo(() => ({
    cv: function CvNode({ data, selected }: { data: { raw: Record<string, unknown>; childCount: number; collapsedCount: number }; selected?: boolean }) {
      const raw = data.raw;
      const { kind, value, line } = semanticLabel(raw);
      const cat = nodeCategory(raw);
      const collapsed = false; // rendered by outer map via className; badge via data
      void collapsed;
      return (
        <div className={`cvnode ${cat} ${selected ? "selected" : ""}`}
             title={`kind=${kind} line=${line ?? "—"} confidence=${raw.confidence ?? "—"}`}>
          <span className="cvnode-kind">{kind}</span>
          {value && <span className="cvnode-value">{value}</span>}
          {line != null && <span className="cvnode-line">:{line}</span>}
          {data.childCount > 0 && (
            <button className="cvnode-toggle" tabIndex={-1}
                    title="collapse / expand subtree"
                    onClick={(ev) => { ev.stopPropagation(); toggleCollapse(raw.id as string); }}>
              ⌄
            </button>
          )}
          {data.collapsedCount > 0 && <span className="cvnode-badge">+{data.collapsedCount}</span>}
          <Handle type="target" position={Position.Top} style={{ width: 7, height: 7, background: "rgba(216,230,230,0.85)", border: "none" }} isConnectable={false} />
          <Handle type="source" position={Position.Bottom} style={{ width: 7, height: 7, background: "rgba(216,230,230,0.85)", border: "none" }} isConnectable={false} />
        </div>
      );
    },
  }), [toggleCollapse]);

  // ---- selection ----
  // reads payload/nodes/props through refs: framing helpers are memoized once
  // and must never act on a stale first-render closure
  const propsRef = useRef({ onSelectNode, onSelectLine });
  propsRef.current = { onSelectNode, onSelectLine };
  const selectNode = useCallback((nodeId: string | null, center = false) => {
    setSelectedId(nodeId);
    const pl = payloadRef.current;
    if (!pl || !nodeId) return;
    const raw = pl.nodes.find((n) => n.id === nodeId);
    if (!raw) return;
    const incoming = (pl.edges ?? []).filter((e) => e.target === nodeId);
    const outgoing = (pl.edges ?? []).filter((e) => e.source === nodeId);
    propsRef.current.onSelectNode({ node: raw, incoming, outgoing });
    const line = raw.line as number | null;
    propsRef.current.onSelectLine(typeof line === "number" ? line : null);
    if (center) {
      const nd = nodesRef.current.find((n) => n.id === nodeId);
      if (nd && flowRef.current) {
        flowRef.current.setCenter(nd.position.x + NODE_W / 2, nd.position.y + NODE_H / 2,
          { zoom: Math.max(flowRef.current.getZoom(), 0.9), duration: 260 });
      }
    }
  }, []);

  const onNodeClick = useCallback((_e: unknown, node: Node) => {
    selectNode(node.id);
  }, [selectNode]);

  // keyboard navigation: parent / first child / siblings
  const onKeyDown = useCallback((ev: React.KeyboardEvent) => {
    if (!payload || !selectedId) return;
    const kids = (payload.edges ?? [])
      .filter((e) => e.kind === "containment" && e.source === selectedId)
      .map((e) => e.target as string);
    const parent = parentOf.get(selectedId) ?? null;
    const siblings = parent
      ? (payload.edges ?? []).filter((e) => e.kind === "containment" && e.source === parent)
        .map((e) => e.target as string)
      : [];
    let next: string | null = null;
    if (ev.key === "ArrowUp" && parent) next = parent;
    else if (ev.key === "ArrowDown" && kids.length) next = kids[0];
    else if ((ev.key === "ArrowLeft" || ev.key === "ArrowRight") && siblings.length > 1) {
      const i = siblings.indexOf(selectedId);
      next = siblings[(i + (ev.key === "ArrowRight" ? 1 : siblings.length - 1)) % siblings.length];
    } else if (ev.key === "Escape") { selectNode(null); ev.preventDefault(); return; }
    if (next) { selectNode(next, true); ev.preventDefault(); }
  }, [payload, selectedId, parentOf, selectNode]);

  // source-dock line click → focus the shallowest node on that line
  const focusLineApplied = useRef<number | null>(null);
  useEffect(() => {
    if (focusLine == null || !payload) return;
    if (focusLineApplied.current === focusLine) return;
    focusLineApplied.current = focusLine;
    const depth = node_depths(payload.nodes, payload.edges);
    const candidates = payload.nodes
      .filter((n) => n.line === focusLine)
      .sort((a, b) => (depth.get(a.id as string) ?? 99) - (depth.get(b.id as string) ?? 99));
    if (candidates.length) selectNode(candidates[0].id as string, true);
  }, [focusLine, payload, selectNode]);

  // guided journey: steps drive framing/selection themselves
  useEffect(() => {
    if (!guided || !payload) return;
    const fnRoots = payload.nodes
      .filter((n) => /^(FunctionDecl|FunctionDef)$/.test(String(n.kind ?? "")))
      .sort((a, b) => (descendantCount.get(b.id as string) ?? 0) - (descendantCount.get(a.id as string) ?? 0));
    const firstFn = fnRoots[0]?.id as string | undefined;
    if (guidedStep === 0) { setHiddenSubtrees(new Set()); setStructuralLevel(1); selectNode(null); }
    if (guidedStep === 1 && firstFn) {
      const others = fnRoots.filter((f) => f.id !== firstFn).map((f) => f.id as string);
      setHiddenSubtrees(new Set(others));
      setStructuralLevel(1);
      selectNode(firstFn, true);
    }
    if (guidedStep === 2 && firstFn) { setStructuralLevel(2); selectNode(firstFn, true); }
    if (guidedStep === 3 && firstFn) { setStructuralLevel(3); selectNode(firstFn, true); }
    if (guidedStep === 4) { setHiddenSubtrees(new Set()); setStructuralLevel(2); selectNode(null); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guidedStep, guided, payload]);

  // ---- search ----
  const runSearch = () => {
    if (!payload || !search.trim()) { setSearchHits([]); return; }
    const q = search.trim().toLowerCase();
    const hits = payload.nodes
      .filter((n) => JSON.stringify({ k: n.kind, n: n.name, t: n.text ?? "" })
        .toLowerCase().includes(q))
      .map((n) => n.id as string);
    setSearchHits(hits);
    if (hits.length) selectNode(hits[0], true);
  };

  const fitSelectionSubtree = () => {
    if (!selectedId || !flowRef.current) return;
    const sub = new Set([selectedId, ...g_descendants(payload?.edges ?? [], new Set([selectedId]))]);
    const nds = nodes.filter((n) => sub.has(n.id));
    if (!nds.length) return;
    const xs = nds.map((n) => n.position.x), ys = nds.map((n) => n.position.y);
    const x1 = Math.min(...xs), x2 = Math.max(...xs) + NODE_W;
    const y1 = Math.min(...ys), y2 = Math.max(...ys) + NODE_H;
    const w = x2 - x1, h = y2 - y1;
    const el = document.querySelector<HTMLElement>(".graphwrap");
    const vw = (el?.clientWidth ?? 900) - 40, vh = (el?.clientHeight ?? 500) - 40;
    flowRef.current.setViewport({
      x: -x1 * Math.min(vw / w, vh / h, 1.1) + (vw - w * Math.min(vw / w, vh / h, 1.1)) / 2,
      y: -y1 * Math.min(vw / w, vh / h, 1.1) + (vh - h * Math.min(vw / w, vh / h, 1.1)) / 2,
      zoom: Math.min(vw / w, vh / h, 1.1),
    }, { duration: 260 });
  };

  if (error) {
    return <div className="graphwrap"><p className="err">{error}</p>
      <p className="muted">Table and raw views remain available for this stage.</p></div>;
  }
  if (!payload) return <p className="muted">Laying out graph…</p>;
  if (!payload.nodes.length) {
    return <p className="muted">This stage produced no graph nodes — use the table/raw views.</p>;
  }

  const hitSet = new Set(searchHits);
  const syntheticAvailable = payload.nodes.some((n) => SYNTHETIC_KINDS.test(String(n.kind ?? "")));
  const showMinimap = visible.nodes.length > 40;
  const GUIDED_STEPS = [
    "The parser turns the whole token stream into one tree. Each card is a real node the parser built.",
    "Start inside one function — the tree under its declaration is that function's meaning.",
    "One level down: the statements. Each keeps its exact source line.",
    "All the way down: nested expressions. This reveal order is conceptual — the parser builds the tree in its own order.",
    "Zoom back out: every function's tree hangs under the module root.",
  ];

  return (
    <div ref={wrapRef} className={"graphwrap" + (fullscreen ? " graphwrap-fs" : "")}
         data-metrics={JSON.stringify({
           nodes_total: metrics?.total ?? payload.nodes.length,
           nodes_visible: metrics?.visible ?? visible.nodes.length,
           edges_visible: metrics?.edges ?? visible.edges.length,
           layout_ms: metrics?.layoutMs ?? layoutMs,
           initial_zoom: metrics?.initialZoom ?? null,
           strategy: isTreeStage ? "tidy-tree" : "layered-cfg",
         })}
         tabIndex={0} onKeyDown={onKeyDown} aria-label={`${stage} graph`}>
      <div className="graphtoolbar">
        <input className="search" placeholder="Search nodes…"
               value={search} onChange={(e) => setSearch(e.target.value)}
               onKeyDown={(e) => { if (e.key === "Enter") runSearch(); }}
               aria-label="search graph nodes" />
        <button className="tab" onClick={runSearch}>Search</button>
        <span className="detaillevels" role="group" aria-label="structural detail level">
          {["Roots", "Level 1", "Level 2", "Full"].map((label, lv) => (
            <button key={label} role="button"
                    aria-pressed={structuralLevel === lv}
                    className={structuralLevel === lv ? "tab active" : "tab"}
                    onClick={() => setStructuralLevel(lv as 0 | 1 | 2 | 3)}>{label}</button>
          ))}
        </span>
        {syntheticAvailable && (
          <button className="tab" aria-pressed={hideSynthetic}
                  title="ImplicitCastExpr and other compiler-inserted nodes, honestly labeled"
                  onClick={() => setHideSynthetic((v) => !v)}>
            {hideSynthetic ? "▸ compiler nodes hidden" : "▾ compiler nodes shown"}
          </button>
        )}
        {selectedId && <button className="tab" onClick={fitSelectionSubtree}>Fit subtree</button>}
        <span className="spacer" />
        <span className="muted">
          {searchHits.length > 0 && `${searchHits.length} hit(s) · `}
          {visible.nodes.length}/{payload.nodes.length} nodes
          {(payload.truncated.nodes || payload.truncated.edges) && " · TRUNCATED"}
        </span>
      </div>

      {guided && (
        <div className="tf-guided graph-guided" role="note" aria-live="polite">
          <div className="tf-guided-h"><span>guided · syntax tree · step {guidedStep + 1}/5</span></div>
          <p className="tf-guided-step">{GUIDED_STEPS[guidedStep]}</p>
          <div className="tf-guided-actions">
            <button className="btn ghost" onClick={() => setGuidedStep((s) => Math.max(0, s - 1))} disabled={guidedStep === 0}>← back</button>
            {guidedStep < GUIDED_STEPS.length - 1
              ? <button className="btn primary" onClick={() => setGuidedStep((s) => s + 1)}>reveal more →</button>
              : <button className="btn primary" onClick={() => onNavigateStage?.("code_object")}>continue →</button>}
            <div className="tf-guided-dots" aria-hidden>
              {GUIDED_STEPS.map((_, i) => <span key={i} className={i === guidedStep ? "on" : ""} />)}
            </div>
          </div>
        </div>
      )}

      <ReactFlowProvider>
        <ReactFlow
          onInit={(instance) => {
            flowRef.current = instance;
            setTimeout(() => { initialZoomRef.current = instance.getZoom(); }, 400);
            if (pendingFitRef.current) {
              pendingFitRef.current = false;
              requestAnimationFrame(() => frameInitial());
            }
          }}
          nodes={nodes.map((n) => ({
            ...n,
            selected: n.id === selectedId,
            className: [
              hiddenSubtrees.has(n.id) ? "collapsed-root" : "",
              hitSet.size && !hitSet.has(n.id) ? "dimmed" : "",
              selectedId && !ancestryPath.has(n.id) ? "receded" : "",
            ].join(" "),
          }))}
          edges={edges.map((e) => ({
            ...e,
            className: (e.className ?? "") +
              (ancestryPath.has(e.target) && ancestryPath.has(e.source) &&
                parentOf.get(e.target) === e.source ? " on-path" : ""),
          }))}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          onNodeDoubleClick={(_e, node) => toggleCollapse(node.id)}
          minZoom={0.08}
          maxZoom={2.2}
          proOptions={{ hideAttribution: true }}
          nodesDraggable
        >
          <ZoomReporter onZoom={setZoom} />
          <Background gap={18} color="#172126" />
          <Controls showInteractive={false} position="bottom-left" />
          {showMinimap && (
            <MiniMap pannable zoomable
                     nodeColor={(n) => {
                       const raw = (n.data as { raw?: Record<string, unknown> })?.raw;
                       const cat = raw ? nodeCategory(raw) : "cat-expr";
                       return ({ "cat-decl": "#b9a8d8", "cat-stmt": "#84989e",
                                 "cat-expr": "#6fc3b8", "cat-op": "#6fc3b8",
                                 "cat-name": "#4e7a75", "cat-literal": "#e6a87e",
                                 "cat-synthetic": "#4a5a62", "cat-block": "#e6a87e",
                               } as Record<string, string>)[cat] ?? "#4e7a75";
                     }}
                     nodeStrokeWidth={0}
                     maskColor="rgba(23, 33, 38, 0.78)"
                     style={{ background: "#1d292f", border: "1px solid rgba(216,230,230,0.14)", borderRadius: 8 }}
                     className="cv-minimap" />
          )}
        </ReactFlow>
      </ReactFlowProvider>
      <div className="graph-legend explore-only">
        <span><i className="lg-dot cat-decl" />declarations</span>
        <span><i className="lg-dot cat-stmt" />statements</span>
        <span><i className="lg-dot cat-expr" />expressions &amp; operators</span>
        <span><i className="lg-dot cat-name" />names</span>
        <span><i className="lg-dot cat-literal" />literals</span>
        {payload.stage.startsWith("ir_") && <span><i className="lg-dot cat-block" />basic blocks</span>}
        {syntheticAvailable && <span><i className="lg-dot cat-synthetic" />compiler-inserted</span>}
      </div>
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
