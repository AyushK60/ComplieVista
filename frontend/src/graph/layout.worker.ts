/// <reference lib="webworker" />
// M3-C layout worker — deterministic layered layout (longest-path layering by
// edge direction, ordered within layers). Runs off the main thread.
// ADR-0006: elkjs bundled spawns a nested Worker inside a module worker
// ("_Worker is not a constructor"); this dependency-free layering replaces it.
self.onmessage = (e: MessageEvent) => {
  const { id, nodes, edges } = e.data;
  const t0 = performance.now();
  try {
    const ids = new Set(nodes.map((n: any) => n.id));
    const adj = new Map<string, string[]>();
    const indeg = new Map<string, number>();
    for (const n of nodes) { indeg.set(n.id, 0); }
    for (const edge of edges) {
      if (!ids.has(edge.source) || !ids.has(edge.target)) continue;
      if (!adj.has(edge.source)) adj.set(edge.source, []);
      adj.get(edge.source)!.push(edge.target);
      indeg.set(edge.target, (indeg.get(edge.target) ?? 0) + 1);
    }
    // longest-path layering via Kahn layers
    const layer = new Map<string, number>();
    const queue: string[] = [];
    for (const [id, d] of indeg) {
      if (d === 0) { queue.push(id); layer.set(id, 0); }
    }
    while (queue.length) {
      const cur = queue.shift()!;
      for (const t of adj.get(cur) ?? []) {
        layer.set(t, Math.max(layer.get(t) ?? 0, (layer.get(cur) ?? 0) + 1));
        const d = (indeg.get(t) ?? 0) - 1;
        indeg.set(t, d);
        if (d === 0) queue.push(t);
      }
    }
    // any node unreachable (cycles) gets its own layer after max
    let maxLayer = 0;
    for (const l of layer.values()) maxLayer = Math.max(maxLayer, l);
    for (const n of nodes) {
      if (!layer.has(n.id)) layer.set(n.id, ++maxLayer);
    }
    const byLayer = new Map<number, string[]>();
    for (const n of nodes) {
      const l = layer.get(n.id) ?? 0;
      if (!byLayer.has(l)) byLayer.set(l, []);
      byLayer.get(l)!.push(n.id);
    }
    const positions: Record<string, { x: number; y: number }> = {};
    const W = 210;
    const H = 64;
    for (const [l, ids] of [...byLayer.entries()].sort((a, b) => a[0] - b[0])) {
      ids.forEach((nid, idx) => {
        positions[nid] = { x: l * W, y: idx * H };
      });
    }
    (self as any).postMessage({
      id, positions, layoutMs: Math.round(performance.now() - t0), error: null,
    });
  } catch (err: any) {
    (self as any).postMessage({ id, positions: {}, layoutMs: 0, error: String(err) });
  }
};
