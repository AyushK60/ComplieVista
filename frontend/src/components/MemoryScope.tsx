import { useMemo } from "react";
import { ObservationChunk } from "../api";

/**
 * M5-E MemoryScope — recorded memory evidence synchronized with the replay
 * cursor. Every record carries its observed/derived/unavailable class; gaps are
 * explained, never faked. Python references are id()-based identities within the
 * run, NOT C pointers; C addresses are per-run (ASLR).
 */
export default function MemoryScope({
  stream, cursorSeq, onSelectLine,
}: {
  stream: { chunks: ObservationChunk[]; language: string; profile: string;
            limitations: string[]; total: number } | null;
  cursorSeq: number;
  onSelectLine: (line: number) => void;
}) {
  const chunks = useMemo(() => stream?.chunks ?? [], [stream]);

  // Replay not started (cursor 0) = final recorded state, labeled honestly.
  const atStart = cursorSeq === 0;
  const effSeq = atStart ? Number.MAX_SAFE_INTEGER : cursorSeq;

  const activeFrame = useMemo(() => {
    let best: { seq: number; payload: Record<string, unknown> } | null = null;
    for (const c of chunks) {
      const es = Number(c.payload.event_seq ?? 0);
      if (c.payload.kind === "frame_snapshot" && es <= effSeq
          && (!best || es >= Number(best.payload.event_seq ?? 0))) {
        best = c;
      }
    }
    return best;
  }, [chunks, effSeq]);

  const aliases = useMemo(() =>
    chunks.filter((c) => c.payload.kind === "alias"
      && Number(c.payload.event_seq ?? 0) <= effSeq).map((c) => c.payload),
  [chunks, effSeq]);

  const unavailable = chunks.filter((c) => c.payload.kind === "unavailable");
  const cAllocs = chunks.filter((c) => c.payload.kind === "alloc");
  const cFrees = chunks.filter((c) => c.payload.kind === "free");
  const debugStops = chunks.filter((c) => c.payload.kind === "debug_stop");
  const graph = chunks.find((c) => c.payload.kind === "object_graph")?.payload;
  const tracemalloc = chunks.find((c) => c.payload.kind === "tracemalloc")?.payload;
  const gc = chunks.find((c) => c.payload.kind === "gc")?.payload;
  const memMeta = chunks.find((c) => c.payload.kind === "mem_meta")?.payload;

  if (!stream) return <p className="muted">No memory evidence recorded.</p>;

  return (
    <div className="memoryscope" role="region" aria-label="MemoryScope">
      <p className="muted">
        schema m5.memory.v1 · profile {stream.profile} · {stream.total} records ·
        language {stream.language}. {" "}
        <span className="chip ok">observed</span> in-run evidence only;
        Python references are id()-based identities, not C pointers; C addresses
        are per-run (ASLR).
      </p>
      {unavailable.map((c, i) => (
        <p className="notice" key={`u${i}`}>
          <span className="chip blocked">unavailable</span>{" "}
          {String(c.payload.topic)}: {String(c.payload.reason)}
        </p>
      ))}

      {activeFrame && (
        <section aria-label="active frame">
          <h4>Active frame {atStart
            ? "(final recorded state — replay not started)"
            : "at cursor"} (frame_snapshot · observed)</h4>
          <p className="muted">
            <code>{String(activeFrame.payload.fn)}</code> :{String(activeFrame.payload.line)}{" "}
            · frame_id {String(activeFrame.payload.frame_id)}
          </p>
          <table className="grid locals">
            <tbody>
              {(activeFrame.payload.locals as Array<Record<string, unknown>> | undefined)
                ?.slice(0, 12).map((loc, i) => (
                  <tr key={i}>
                    <td>{String(loc.name)}{loc.redacted ? " 🔒" : ""}</td>
                    <td>{loc.kind === "object"
                      ? `${String(loc.type)}#${String(loc.obj_id)}`
                      : String((loc.preview as Record<string, unknown>)?.repr ?? "—")}</td>
                  </tr>
                ))}
            </tbody>
          </table>
          <button className="link" onClick={() => onSelectLine(Number(activeFrame.payload.line))}>
            show source line {String(activeFrame.payload.line)}
          </button>
        </section>
      )}
      {aliases.length > 0 && (
        <section aria-label="alias links">
          <h4>Reference aliases (derived from observed identity)</h4>
          <ul>{aliases.slice(0, 6).map((a, i) => (
            <li key={i}><code>{(a.names as string[]).join(" ≡ ")}</code></li>
          ))}</ul>
        </section>
      )}

      {debugStops.length > 0 && (
        <section aria-label="debugger observations">
          <h4>gdb stops (observed · curated debug profile)</h4>
          {debugStops.slice(0, 8).map((s, i) => (
            <details key={i} open={i === 0}>
              <summary><code>{String(s.payload.fn)}</code></summary>
              <pre className="excerpt">{[
                ...((s.payload.gdb_text as string[]) ?? []),
                ...((s.payload.inspect_raw as string[]) ?? []),
              ].join("\n").slice(0, 1200)}</pre>
            </details>
          ))}
        </section>
      )}

      {stream.language === "c" && (cAllocs.length > 0 || memMeta) && (
        <section aria-label="heap">
          <h4>Heap allocations (allocator interposition · observed)</h4>
          <table className="grid locals">
            <tbody>
              {cAllocs.slice(0, 8).map((c, i) => (
                <tr key={i}>
                  <td>0x{Number(c.payload.addr).toString(16)}</td>
                  <td>{String(c.payload.size)} B</td>
                </tr>
              ))}
            </tbody>
          </table>
          {memMeta && (
            <p className="muted">
              {String(memMeta.allocs)} allocs / {String(memMeta.frees)} frees ·
              outstanding {String(memMeta.outstanding)} ·{" "}
              {cAllocs.length >= 8 ? "list truncated in UI" : "complete"}
            </p>
          )}
        </section>
      )}

      {graph && (
        <section aria-label="object reference graph">
          <h4>Object reference graph (bounded reachable subgraph · observed)</h4>
          <ReferenceGraph graph={graph} />
        </section>
      )}
      {tracemalloc && (
        <section aria-label="tracemalloc">
          <h4>tracemalloc (observed, instrumented effect)</h4>
          <p className="muted">
            traced current {Number(tracemalloc.traced_current_bytes)} B · peak{" "}
            {Number(tracemalloc.traced_peak_bytes)} B
          </p>
          <p className="muted">{String(tracemalloc.caveat)}</p>
        </section>
      )}
      {gc && (
        <section aria-label="gc">
          <h4>gc activity (observed)</h4>
          <p className="muted">
            forced collect at exit collected {String(gc.collected_by_forced_collect)}{" "}
            objects · {String(gc.caveat)}
          </p>
        </section>
      )}
      <details>
        <summary className="muted">Evidence limitations</summary>
        <ul>{stream.limitations.map((l, i) => <li key={i} className="muted">{l}</li>)}</ul>
      </details>
    </div>
  );
}

/** Bounded SVG reference graph: nodes are object identities, edges observed
 * references. No decorative animation; positions are a simple deterministic
 * ring layout (derived rendering of observed edges, clearly labeled). */
function ReferenceGraph({ graph }: { graph: Record<string, unknown> }) {
  const nodes = (graph.nodes as Array<Record<string, unknown>>) ?? [];
  const edges = (graph.edges as Array<Record<string, unknown>>) ?? [];
  const W = 420, H = 260, R = Math.min(W, H) / 2 - 30;
  const pos = new Map<string, { x: number; y: number }>();
  nodes.forEach((n, i) => {
    const a = (2 * Math.PI * i) / Math.max(nodes.length, 1) - Math.PI / 2;
    pos.set(String(n.obj_id), {
      x: W / 2 + R * Math.cos(a), y: H / 2 + R * Math.sin(a),
    });
  });
  if (nodes.length === 0) return <p className="muted">no graph captured</p>;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img"
         aria-label={`reference graph with ${nodes.length} nodes, ${edges.length} edges`}
         style={{ maxHeight: 260, border: "1px solid #ddd", background: "#fafafa" }}>
      {edges.map((e, i) => {
        const a = pos.get(String(e.src)), b = pos.get(String(e.dst));
        if (!a || !b) return null;
        const self = String(e.src) === String(e.dst);
        return <line key={i} x1={a.x} y1={a.y} x2={self ? a.x + 1 : b.x}
                     y2={self ? a.y + 1 : b.y}
                     stroke={self ? "#c0392b" : "#888"} strokeWidth={1}
                     markerEnd="url(#arrow)" />;
      })}
      <defs>
        <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3"
                orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#888" /></marker>
      </defs>
      {nodes.map((n) => {
        const p = pos.get(String(n.obj_id));
        if (!p) return null;
        return (
          <g key={String(n.obj_id)}>
            <circle cx={p.x} cy={p.y} r={9} fill="#cfe3f7" stroke="#4a78a8" />
            <text x={p.x} y={p.y - 13} fontSize={9} textAnchor="middle"
                  fill="#333">{String(n.type)}#{String(n.obj_id)}</text>
          </g>
        );
      })}
    </svg>
  );
}
