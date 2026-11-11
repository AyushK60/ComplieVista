/// <reference lib="webworker" />
// Stage 8 Part-2 layout engine. Two strategies, chosen by the caller:
//
//  1. "tree" (syntax trees): Reingold–Tilford-style tidy tree over CONTAINMENT
//     edges only. Children keep source order (line, col, id - stable sibling
//     ordering); each parent is centered over its children; subtrees are packed
//     so nothing overlaps. This replaces the old layer-column layout that made
//     ASTs read as unrelated columns of labels.
//
//  2. "layered" (CFGs): SCC-condensed DAG layered TOP-DOWN (control flow reads
//     downward), members of a cycle stacked at the component position, layers
//     ordered by predecessor barycenter to reduce edge crossings. Kept from
//     Stage 3.5 (CV-06) but rotated vertical and re-ordered.
//
// Positions only; no node is invented or dropped here.
type Pos = { x: number; y: number };
type NodeRec = { id: string; [k: string]: unknown };
type EdgeRec = { source: string; target: string; kind?: string; [k: string]: unknown };

interface LayoutOpts {
  strategy: "tree" | "layered";
  /** tree only: "LR" lays depth out left-to-right (broad, shallow code trees fit a wide canvas) */
  direction: "TB" | "LR";
  nodeWidth: number;
  nodeHeight: number;
  siblingGap: number;
  subtreeGap: number;
  levelGap: number;
}

const DEFAULTS: LayoutOpts = {
  strategy: "tree",
  direction: "TB",
  nodeWidth: 190,
  nodeHeight: 46,
  siblingGap: 10,
  subtreeGap: 24,
  levelGap: 86,
};

self.onmessage = (e: MessageEvent) => {
  const { id, nodes, edges, options } = e.data as {
    id: number; nodes: NodeRec[]; edges: EdgeRec[]; options?: Partial<LayoutOpts>;
  };
  const t0 = performance.now();
  const opt = { ...DEFAULTS, ...(options ?? {}) };
  try {
    const positions = opt.strategy === "layered"
      ? layered(nodes, edges, opt)
      : tree(nodes, edges, opt);
    (self as unknown as { postMessage: (m: unknown) => void }).postMessage({
      id, positions, layoutMs: Math.round(performance.now() - t0), error: null,
    });
  } catch (err) {
    (self as unknown as { postMessage: (m: unknown) => void }).postMessage({
      id, positions: {}, layoutMs: 0, error: String(err),
    });
  }
};

// ---------------------------------------------------------------- tree -----
function tree(nodes: NodeRec[], edges: EdgeRec[], o: LayoutOpts): Record<string, Pos> {
  const childrenOf = new Map<string, string[]>();
  const hasParent = new Set<string>();
  const idset = new Set(nodes.map((n) => n.id));
  for (const e of edges) {
    if (e.kind !== "containment") continue;
    if (!idset.has(e.source) || !idset.has(e.target) || e.source === e.target) continue;
    if (!childrenOf.has(e.source)) childrenOf.set(e.source, []);
    childrenOf.get(e.source)!.push(e.target);
    hasParent.add(e.target);
  }
  // stable sibling order: by (line, col, id) so the layout mirrors the source
  for (const [, kids] of childrenOf) {
    kids.sort((a, b) => {
      const ka = keyOf(a), kb = keyOf(b);
      return ka < kb ? -1 : ka > kb ? 1 : 0;
    });
  }
  function keyOf(id: string): string {
    return id; // ids are n<index> from the builder: already stable + source order
  }

  const roots = nodes.filter((n) => !hasParent.has(n.id)).map((n) => n.id);
  const positions: Record<string, Pos> = {};

  // Cross-axis extent: node width for top-down, node height for left-to-right.
  const LR = o.direction === "LR";
  const cross = LR ? o.nodeHeight : o.nodeWidth;
  const levelStep = LR ? o.nodeWidth + o.levelGap : o.levelGap;
  const put = (c: number, depth: number): Pos => (LR ? { x: depth * levelStep, y: c } : { x: c, y: depth * levelStep });

  // Subtree width = max(own width, packed children width); memoized
  const widthCache = new Map<string, number>();
  function subtreeWidth(id: string): number {
    const hit = widthCache.get(id);
    if (hit != null) return hit;
    const kids = childrenOf.get(id) ?? [];
    let w = cross;
    if (kids.length) {
      let cw = 0;
      for (let i = 0; i < kids.length; i++) {
        if (i > 0) cw += o.siblingGap;
        cw += subtreeWidth(kids[i]);
      }
      w = Math.max(cross, cw);
    }
    widthCache.set(id, w);
    return w;
  }

  function placeTree(id: string, xLeft: number, depth: number) {
    if (positions[id]) return; // cycle/re-entry guard
    positions[id] = put(xLeft + (subtreeWidth(id) - cross) / 2, depth);
    const kids = childrenOf.get(id) ?? [];
    let cx = xLeft;
    for (const k of kids) {
      placeTree(k, cx, depth + 1);
      cx += subtreeWidth(k) + o.siblingGap;
    }
  }

  let cursor = 0;
  for (const r of roots) {
    if (positions[r]) continue; // cycle guard
    placeTree(r, cursor, 0);
    cursor += subtreeWidth(r) + o.subtreeGap;
  }
  // safety: any node unreachable via containment (e.g. cap orphans) - stack below
  const maxMain = Math.max(0, ...Object.values(positions).map((p) => (LR ? p.x : p.y)));
  for (const n of nodes) {
    if (!positions[n.id]) positions[n.id] = LR ? { x: maxMain + levelStep, y: 0 } : { x: 0, y: maxMain + levelStep };
  }
  return positions;
}

// ------------------------------------------------------------- layered -----
function layered(nodes: NodeRec[], edges: EdgeRec[], o: LayoutOpts): Record<string, Pos> {
  const idset = new Set(nodes.map((n) => n.id));
  const adj = new Map<string, string[]>();
  const radj = new Map<string, string[]>();
  for (const n of nodes) { adj.set(n.id, []); radj.set(n.id, []); }
  for (const e of edges) {
    if (!idset.has(e.source) || !idset.has(e.target) || e.source === e.target) continue;
    adj.get(e.source)!.push(e.target);
    radj.get(e.target)!.push(e.source);
  }
  // Iterative Kosaraju SCC (loops become stacked components)
  const visited = new Set<string>();
  const order: string[] = [];
  for (const start of nodes.map((n) => n.id)) {
    if (visited.has(start)) continue;
    const stack: Array<[string, number]> = [[start, 0]];
    visited.add(start);
    while (stack.length) {
      const top = stack[stack.length - 1];
      const neighbors = adj.get(top[0]) ?? [];
      if (top[1] < neighbors.length) {
        const next = neighbors[top[1]];
        stack[stack.length - 1] = [top[0], top[1] + 1];
        if (!visited.has(next)) { visited.add(next); stack.push([next, 0]); }
      } else { order.push(top[0]); stack.pop(); }
    }
  }
  const comp = new Map<string, number>();
  const compMembers = new Map<number, string[]>();
  let comps = 0;
  for (const start of [...order].reverse()) {
    if (comp.has(start)) continue;
    const stack = [start];
    comp.set(start, comps);
    const members = [start];
    while (stack.length) {
      const cur = stack.pop()!;
      for (const prev of radj.get(cur) ?? []) {
        if (!comp.has(prev)) { comp.set(prev, comps); stack.push(prev); members.push(prev); }
      }
    }
    compMembers.set(comps, members);
    comps += 1;
  }
  // Condensation DAG layering (Kahn, longest path)
  const cadj = new Map<number, number[]>();
  const cindeg = new Map<number, number>();
  for (let i = 0; i < comps; i++) { cadj.set(i, []); cindeg.set(i, 0); }
  for (const [s, targets] of adj) {
    for (const t of targets) {
      const cs = comp.get(s)!; const ct = comp.get(t)!;
      if (cs !== ct) { cadj.get(cs)!.push(ct); cindeg.set(ct, cindeg.get(ct)! + 1); }
    }
  }
  const clayer = new Map<number, number>();
  const q: number[] = [];
  for (const [c, d] of cindeg) { if (d === 0) { q.push(c); clayer.set(c, 0); } }
  while (q.length) {
    const cur = q.shift()!;
    for (const t of cadj.get(cur) ?? []) {
      clayer.set(t, Math.max(clayer.get(t) ?? 0, (clayer.get(cur) ?? 0) + 1));
      const d = cindeg.get(t)! - 1;
      cindeg.set(t, d);
      if (d === 0) q.push(t);
    }
  }
  let maxL = 0;
  for (const l of clayer.values()) maxL = Math.max(maxL, l);
  for (let i = 0; i < comps; i++) if (!clayer.has(i)) clayer.set(i, ++maxL);

  // Barycenter ordering within each layer (2 downward passes) reduces crossings
  const layerComps = new Map<number, number[]>();
  for (let ci = 0; ci < comps; ci++) {
    const l = clayer.get(ci) ?? 0;
    if (!layerComps.has(l)) layerComps.set(l, []);
    layerComps.get(l)!.push(ci);
  }
  const compPos = new Map<number, number>(); // slot index in layer
  for (let pass = 0; pass < 2; pass++) {
    for (const [l, cs] of [...layerComps.entries()].sort((a, b) => a[0] - b[0])) {
      const bary = cs.map((ci) => {
        let sum = 0, n = 0;
        for (const m of compMembers.get(ci) ?? []) {
          for (const p of radj.get(m) ?? []) {
            const pc = comp.get(p)!;
            if (pc !== ci && compPos.has(pc)) { sum += compPos.get(pc)!; n += 1; }
          }
        }
        return n ? sum / n : Number.MAX_SAFE_INTEGER; // no preds → keep at end? push front
      });
      cs.sort((a, b) => bary[cs.indexOf(a)] - bary[cs.indexOf(b)]);
      cs.forEach((ci, i) => compPos.set(ci, i));
    }
  }

  // Position: TOP-DOWN (y = layer), slots sized proportionally to member count
  const positions: Record<string, Pos> = {};
  for (const [l, cs] of [...layerComps.entries()].sort((a, b) => a[0] - b[0])) {
    const totalSlots = cs.reduce((acc, ci) => acc + (compMembers.get(ci) ?? []).length, 0)
      + cs.length - 1;
    let slot = 0;
    for (const ci of cs) {
      const members = compMembers.get(ci) ?? [];
      members.forEach((nid, idx) => {
        positions[nid] = {
          x: slot * (o.nodeWidth + o.siblingGap),
          y: l * (o.nodeHeight + o.levelGap) + idx * (o.nodeHeight + 8),
        };
      });
      slot += members.length + 1;
    }
    void totalSlots;
  }
  return positions;
}
