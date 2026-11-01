import { useEffect, useMemo, useState } from "react";
import { ObservationStream, executions } from "../../api";

/**
 * MemoryScope — recorded memory evidence, presented spatially.
 * Python: frame locals, alias groups, the bounded object graph, tracemalloc and
 * gc records. C: an allocation ladder showing each allocation's lifetime from
 * its alloc record to its matching free, plus mem_meta totals. gdb debug_stop
 * records appear only for the curated debug profile. Every record keeps its
 * honest observation class; gaps are explained, never faked.
 */

interface Chunk { seq: number; payload: Record<string, unknown>; sha256: string }

export default function MemoryPanel({ executionId, onSelectLine }: {
  executionId: string;
  onSelectLine: (line: number) => void;
}) {
  const [stream, setStream] = useState<ObservationStream | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setStream(null); setErr(null);
    (async () => {
      try {
        let acc: ObservationStream | null = null;
        let after = 0;
        for (let page = 0; page < 8; page++) {
          const s = await executions.memory(executionId, after, 500);
          acc = acc
            ? { ...s, chunks: [...acc.chunks, ...s.chunks] }
            : s;
          const next = (s as { next_after?: number | null }).next_after ?? null;
          if (next == null || next <= after) break;
          after = next;
        }
        if (alive && acc) setStream(acc);
      } catch (e) { if (alive) setErr(String(e)); }
    })();
    return () => { alive = false; };
  }, [executionId]);

  if (err) return <p className="err">MemoryScope: {err}</p>;
  if (!stream) return <p className="muted"><span className="spinner" /> loading memory records…</p>;

  const chunks = stream.chunks;
  const byKind = (k: string) => chunks.filter((c) => c.payload.kind === k).map((c) => c.payload);
  const unavailable = byKind("unavailable");
  const frameSnaps = byKind("frame_snapshot");
  const aliases = byKind("alias");
  const graph = byKind("object_graph")[0];
  const tracemalloc = byKind("tracemalloc")[0];
  const gc = byKind("gc")[0];
  const allocs = byKind("alloc");
  const frees = byKind("free");
  const reallocs = byKind("realloc");
  const memMeta = byKind("mem_meta")[0];
  const debugStops = byKind("debug_stop");

  const isC = stream.language === "c";

  return (
    <div className="memscope" role="region" aria-label="MemoryScope">
      <div className="memscope-stats">
        <span className="chip">{stream.total} records</span>
        <span className="chip">profile {stream.profile}</span>
        {isC
          ? <span className="chip">addresses are per-run (ASLR)</span>
          : <span className="chip">identities are id()-based within the run</span>}
        {unavailable.map((u, i) => (
          <span key={i} className="chip blocked" title={String(u.reason ?? "")}>
            {String(u.topic ?? "unavailable")}
          </span>
        ))}
      </div>

      {isC && (allocs.length > 0 || memMeta) ? (
        <AllocLadder allocs={allocs} frees={frees} reallocs={reallocs} meta={memMeta} />
      ) : null}

      {!isC && frameSnaps.length > 0 && (
        <section className="mem-frames">
          <h4>Frame observations <span className="badge exact">observed</span></h4>
          <p className="muted">{frameSnaps.length} frame snapshots were recorded
            (at call and return). Python cannot be sampled continuously without a debugger —
            these are the frames the cooperative tracer reported.</p>
          <div className="framegrid">
            {frameSnaps.slice(-8).reverse().map((f, i) => (
              <FrameCard key={i} f={f} onSelectLine={onSelectLine} />
            ))}
          </div>
        </section>
      )}

      {aliases.length > 0 && (
        <section>
          <h4>Alias groups <span className="badge exact">observed identity</span></h4>
          <div className="aliaswrap">
            {aliases.slice(0, 8).map((a, i) => (
              <span key={i} className="alias-chip">
                {(a.names as string[]).join(" ≡ ")}
                <span className="muted"> → id {String(a.obj_id)}</span>
              </span>
            ))}
          </div>
        </section>
      )}

      {graph && <ObjectGraph graph={graph} />}

      {tracemalloc && (
        <section>
          <h4>tracemalloc <span className="badge exact">observed · instrumented</span></h4>
          <div className="tm-row">
            <div>
              <b>{fmtBytes(Number(tracemalloc.traced_current_bytes))}</b>
              <span className="muted"> traced current</span>
            </div>
            <div>
              <b>{fmtBytes(Number(tracemalloc.traced_peak_bytes))}</b>
              <span className="muted"> traced peak</span>
            </div>
          </div>
          <div className="tm-bars">
            {((tracemalloc.top as Array<Record<string, unknown>>) ?? []).slice(0, 8).map((t, i) => {
              const max = Math.max(...((tracemalloc.top as Array<Record<string, unknown>>) ?? [])
                .map((x) => Number(x.size_bytes)), 1);
              return (
                <div key={i} className="tm-bar" title={`${t.file}:${t.line} — ${Number(t.size_bytes)} B in ${t.count} block(s)`}>
                  <span className="tm-label"><code>{String(t.file).split("/").pop()}:{String(t.line)}</code></span>
                  <span className="tm-fill" style={{ width: `${(Number(t.size_bytes) / max) * 100}%` }} />
                  <span className="tm-val">{fmtBytes(Number(t.size_bytes))}</span>
                </div>
              );
            })}
          </div>
          <p className="muted">{String(tracemalloc.caveat ?? "")}</p>
        </section>
      )}

      {gc && (
        <section>
          <h4>Garbage collection <span className="badge exact">observed</span></h4>
          <p className="muted">
            Forced collect at exit collected <b>{String(gc.collected_by_forced_collect)}</b> objects ·
            generation counts before {((gc.counts_before as number[]) ?? []).join("/")} ·
            after {((gc.counts_after as number[]) ?? []).join("/")}.
          </p>
          <p className="muted">{String(gc.caveat ?? "")}</p>
        </section>
      )}

      {debugStops.length > 0 && (
        <section>
          <h4>gdb stops <span className="badge exact">observed · curated debug profile</span></h4>
          {debugStops.slice(0, 6).map((s, i) => (
            <details key={i} open={i === 0}>
              <summary><code>{String(s.fn)}</code></summary>
              <pre className="excerpt">{[
                ...((s.gdb_text as string[]) ?? []),
                ...((s.inspect_raw as string[]) ?? []),
              ].join("\n").slice(0, 1200)}</pre>
            </details>
          ))}
        </section>
      )}

      <details className="tech-only">
        <summary className="muted">Evidence limitations ({stream.limitations.length})</summary>
        <ul className="limits">{stream.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>
      </details>
    </div>
  );
}

function FrameCard({ f, onSelectLine }: { f: Record<string, unknown>; onSelectLine: (l: number) => void }) {
  const locals = (f.locals as Array<Record<string, unknown>>) ?? [];
  return (
    <button className="framecard panel"
            onClick={() => onSelectLine(Number(f.line))}>
      <div className="fc-head">
        <code>{String(f.fn)}</code>
        <span className="muted">:{String(f.line)}</span>
        <span className="spacer" />
        <span className="chip">{String(f.event_seq)}</span>
      </div>
      {locals.length === 0
        ? <p className="muted">no locals recorded</p>
        : <table className="insp-fields">
            <tbody>
              {locals.slice(0, 8).map((l, i) => (
                <tr key={i}>
                  <td>{String(l.name)}{l.redacted ? " 🔒" : ""}</td>
                  <td><code>{l.kind === "object"
                    ? `${String(l.type)}#${String(l.obj_id)}${l.len != null ? ` len=${String(l.len)}` : ""}`
                    : String((l.preview as Record<string, unknown>)?.repr ?? "—")}</code></td>
                </tr>
              ))}
            </tbody>
          </table>}
    </button>
  );
}

/** C heap ladder: one bar per allocation, spanning alloc→free (or run end). */
function AllocLadder({ allocs, frees, reallocs, meta }: {
  allocs: Array<Record<string, unknown>>;
  frees: Array<Record<string, unknown>>;
  reallocs: Array<Record<string, unknown>>;
  meta: Record<string, unknown> | undefined;
}) {
  if (!allocs.length && !meta) return null;
  const freeByAddr = new Map<number, number>();
  frees.forEach((f) => freeByAddr.set(Number(f.addr), Number(f.seq)));
  const reallocByOld = new Map<number, number>();
  reallocs.forEach((r) => reallocByOld.set(Number(r.old), Number(r.addr)));
  const maxSeq = Math.max(...allocs.map((a) => Number(a.seq)),
    ...frees.map((f) => Number(f.seq)), 1);
  const shown = allocs.slice(0, 12);
  return (
    <section>
      <h4>Heap lifetimes <span className="badge exact">allocator interposition · observed</span></h4>
      {meta && (
        <div className="memscope-stats">
          <span className="chip">{String(meta.allocs)} allocs</span>
          <span className="chip">{String(meta.frees)} frees</span>
          <span className="chip">{String(meta.reallocs)} reallocs</span>
          <span className={`chip ${Number(meta.outstanding) > 0 ? "partial" : "ok"}`}>
            {String(meta.outstanding)} outstanding
          </span>
        </div>
      )}
      <div className="allocladder">
        {shown.map((a, i) => {
          const addr = Number(a.addr);
          const endSeq = freeByAddr.get(addr)
            ?? (reallocByOld.has(addr) ? reallocByOld.get(addr)! : maxSeq);
          const freed = freeByAddr.has(addr);
          const reallocated = reallocByOld.has(addr);
          const start = Number(a.seq);
          const left = (start / maxSeq) * 100;
          const width = Math.max(((endSeq - start) / maxSeq) * 100, 1.5);
          return (
            <div key={i} className="alloc-row"
                 title={`0x${addr.toString(16)} · ${Number(a.size)} B · ${freed ? "freed" : reallocated ? "reallocated" : "outstanding at exit"}`}>
              <code className="alloc-addr">0x{addr.toString(16)}</code>
              <span className="alloc-lane">
                <span className={`alloc-bar ${freed ? "freed" : reallocated ? "realloc" : "leak"}`}
                      style={{ marginLeft: `${left}%`, width: `${width}%` }}>
                  {Number(a.size)} B
                </span>
              </span>
              <span className={`alloc-status ${freed ? "ok" : reallocated ? "partial" : "blocked"}`}>
                {freed ? "freed" : reallocated ? "realloc" : "outstanding"}
              </span>
            </div>
          );
        })}
      </div>
      {allocs.length > 12 && <p className="muted">…{allocs.length - 12} more allocations recorded (shown: first 12)</p>}
      <p className="muted">Bars span from the alloc record to the matching free/realloc
        record — timeline position, not wall-clock time. An allocation without a matching
        free at exit is marked <i>outstanding</i>; that is an observation, not an accusation.</p>
    </section>
  );
}

/** Object reference graph — bounded reachable subgraph of module globals at exit. */
function ObjectGraph({ graph }: { graph: Record<string, unknown> }) {
  const nodes = (graph.nodes as Array<Record<string, unknown>>) ?? [];
  const edges = (graph.edges as Array<Record<string, unknown>>) ?? [];
  const caps = graph.caps as Record<string, number> | undefined;
  if (!nodes.length) return <p className="muted">no object graph captured</p>;
  const W = 560, H = 300;
  // deterministic layout: refs-then-id ordered grid
  const pos = new Map<string, { x: number; y: number }>();
  const cols = Math.ceil(Math.sqrt(nodes.length));
  nodes.forEach((n, i) => {
    pos.set(String(n.obj_id), {
      x: 60 + (i % cols) * ((W - 120) / Math.max(cols - 1, 1)),
      y: 46 + Math.floor(i / cols) * ((H - 90) / Math.max(Math.ceil(nodes.length / cols) - 1, 1)),
    });
  });
  const edgeCount = new Map<string, number>();
  for (const e of edges) {
    const k = `${e.src}->${e.dst}`;
    edgeCount.set(k, (edgeCount.get(k) ?? 0) + 1);
  }
  return (
    <section>
      <h4>Object reference graph <span className="badge exact">observed</span>
        <span className="muted"> (bounded reachable subgraph of module globals at exit)</span></h4>
      <svg viewBox={`0 0 ${W} ${H}`} className="objgraph" role="img"
           aria-label={`object graph: ${nodes.length} nodes, ${edges.length} edges`}>
        <defs>
          <marker id="cv-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto">
            <path d="M0,0 L7,3 L0,6 z" fill="rgba(167,139,250,.8)" />
          </marker>
        </defs>
        {[...edgeCount.entries()].map(([k, n], i) => {
          const [src, dst] = k.split("->");
          const a = pos.get(src); const b = pos.get(dst);
          if (!a || !b) return null;
          const self = src === dst;
          const x2 = self ? a.x + 4 : b.x; const y2 = self ? a.y + 4 : b.y;
          return <line key={i} x1={a.x} y1={a.y} x2={x2} y2={y2}
                       className="objedge" markerEnd="url(#cv-arrow)"
                       strokeOpacity={Math.min(0.35 + n * 0.2, 1)} />;
        })}
        {nodes.map((n) => {
          const p = pos.get(String(n.obj_id));
          if (!p) return null;
          return (
            <g key={String(n.obj_id)}>
              <circle cx={p.x} cy={p.y} r={11} className="objnode" />
              <text x={p.x} y={p.y - 16} textAnchor="middle" className="objlabel">
                {String(n.type)}{n.len != null ? `·${String(n.len)}` : ""}
              </text>
              <text x={p.x} y={p.y + 26} textAnchor="middle" className="objid">#{String(n.obj_id)}</text>
            </g>
          );
        })}
      </svg>
      <p className="muted">{nodes.length} nodes / {edges.length} edges
        {caps ? ` (caps: ${caps.nodes} nodes, ${caps.edges} edges, depth ${caps.depth})` : ""}.
        Node identities are id() values from this run — Python references, not C pointers.</p>
    </section>
  );
}

function fmtBytes(b: number): string {
  if (b >= 1e6) return `${(b / 1e6).toFixed(2)} MB`;
  if (b >= 1e3) return `${(b / 1e3).toFixed(1)} kB`;
  return `${b} B`;
}
