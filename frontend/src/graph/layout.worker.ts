/// <reference lib="webworker" />
// M3.5 CV-06: SCC-aware layered layout. Strongly connected components (loops,
// reconvergence) are condensed, layered as a DAG, and their members stacked at
// the component position — backedges no longer stretch the layout arbitrarily.
self.onmessage = (e: MessageEvent) => {
  const { id, nodes, edges } = e.data;
  const t0 = performance.now();
  try {
    const ids = nodes.map((n: any) => n.id);
    const idset = new Set(ids);
    const adj = new Map<string, string[]>();
    const radj = new Map<string, string[]>();
    for (const n of nodes) { adj.set(n.id, []); radj.set(n.id, []); }
    for (const edge of edges) {
      if (!idset.has(edge.source) || !idset.has(edge.target)) continue;
      if (edge.source === edge.target) continue;
      adj.get(edge.source)!.push(edge.target);
      radj.get(edge.target)!.push(edge.source);
    }
    // Iterative Kosaraju SCC
    const visited = new Set<string>();
    const order: string[] = [];
    for (const start of ids) {
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
        } else {
          order.push(top[0]);
          stack.pop();
        }
      }
    }
    const comp = new Map<string, number>();
    let comps = 0;
    const compMembers = new Map<number, string[]>();
    for (const start of [...order].reverse()) {
      if (comp.has(start)) continue;
      const stack = [start];
      comp.set(start, comps);
      const members: string[] = [start];
      while (stack.length) {
        const cur = stack.pop()!;
        for (const prev of radj.get(cur) ?? []) {
          if (!comp.has(prev)) { comp.set(prev, comps); stack.push(prev); members.push(prev); }
        }
      }
      compMembers.set(comps, members);
      comps += 1;
    }
    // Condensation DAG layering (Kahn)
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
    // Position: SCC members stacked inside their layer slot
    const positions: Record<string, { x: number; y: number }> = {};
    const W = 230; const H = 56;
    const perLayerCol = new Map<number, number>();
    for (let ci = 0; ci < comps; ci++) {
      const l = clayer.get(ci) ?? 0;
      const col = perLayerCol.get(l) ?? 0;
      perLayerCol.set(l, col + 1);
      (compMembers.get(ci) ?? []).forEach((nid, idx) => {
        positions[nid] = { x: l * W, y: col * 320 + idx * H };
      });
    }
    (self as any).postMessage({
      id, positions, layoutMs: Math.round(performance.now() - t0),
      sccCount: comps, error: null,
    });
  } catch (err: any) {
    (self as any).postMessage({ id, positions: {}, layoutMs: 0, error: String(err) });
  }
};
