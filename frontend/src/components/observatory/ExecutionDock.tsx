import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ExecutionEvent, ExecutionJob, executions } from "../../api";
import MemoryPanel from "./MemoryPanel";
import ProcessPanel from "./ProcessPanel";

/**
 * Execution & Systems Dock — recorded replay of a real restricted-container run.
 * The TraceTheater scene (call tree + stack tower) is the primary navigation;
 * the timeline scrubber is secondary. Browsing never re-runs the program.
 */

interface Frame {
  fn: string;
  line: number | null;
  callIdx: number;
  locals: Record<string, unknown> | null;
}

interface TreeNode {
  idx: number;              // index of the call event
  fn: string;
  line: number | null;
  children: TreeNode[];
  ret: string | null;       // return value repr (from return event)
  retIdx: number | null;    // index of the matching return event
  depth: number;
  agg?: false;
}

function buildTree(events: ExecutionEvent[]): TreeNode[] {
  const roots: TreeNode[] = [];
  const stack: TreeNode[] = [];
  for (let i = 0; i < events.length; i++) {
    const e = events[i];
    if (e.kind === "call") {
      const node: TreeNode = {
        idx: i, fn: String(e.payload.fn ?? "?"), line: (e.payload.line as number) ?? null,
        children: [], ret: null, retIdx: null, depth: stack.length,
      };
      (stack.length ? stack[stack.length - 1].children : roots).push(node);
      stack.push(node);
    } else if (e.kind === "return") {
      const n = stack.pop();
      if (n) { n.ret = e.payload.arg != null ? String(e.payload.arg) : null; n.retIdx = i; }
    } else if (e.kind === "exception") {
      const n = stack[stack.length - 1];
      if (n) n.ret = `✗ ${String(e.payload.exc ?? "exception")}`;
    }
  }
  return roots;
}

/** Merge consecutive same-name siblings (×N) to keep huge traces navigable. */
function aggregate(children: TreeNode[]): Array<TreeNode | AggNode> {
  const out: Array<TreeNode | AggNode> = [];
  let i = 0;
  while (i < children.length) {
    let j = i;
    while (j < children.length && children[j].fn === children[i].fn) j++;
    if (j - i > 2 && children[i].children.length === 0) {
      out.push({ agg: true, fn: children[i].fn, nodes: children.slice(i, j) });
    } else {
      for (let k = i; k < j; k++) out.push(children[k]);
    }
    i = j;
  }
  return out;
}
interface AggNode { agg: true; fn: string; nodes: TreeNode[] }

function stackAt(events: ExecutionEvent[], cursor: number): Frame[] {
  const frames: Frame[] = [];
  const idxs: number[] = [];
  for (let i = 0; i < cursor; i++) {
    const e = events[i];
    if (e.kind === "call") {
      frames.push({ fn: String(e.payload.fn ?? "?"), line: (e.payload.line as number) ?? null,
        callIdx: i, locals: (e.payload.locals as Record<string, unknown>) ?? null });
      idxs.push(i);
    } else if (e.kind === "return" || e.kind === "exception") {
      frames.pop(); idxs.pop();
    } else if (e.kind === "line" && frames.length) {
      frames[frames.length - 1].line = (e.payload.line as number) ?? frames[frames.length - 1].line;
    }
  }
  return frames;
}

export default function ExecutionDock({ executionId, onSelectLine, activeLine }: {
  executionId: string;
  onSelectLine: (line: number | null) => void;
  activeLine?: number | null;
}) {
  const [job, setJob] = useState<ExecutionJob | null>(null);
  const [events, setEvents] = useState<ExecutionEvent[]>([]);
  const [output, setOutput] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(true);
  const [tab, setTab] = useState<"trace" | "memory" | "process" | "output">("trace");

  useEffect(() => {
    let alive = true;
    setEvents([]); setOutput(null); setJob(null); setTab("trace"); setError(null);
    const poll = async () => {
      try {
        const j = await executions.get(executionId);
        if (!alive) return;
        setJob(j);
        if (["QUEUED", "RUNNING"].includes(j.status)) setTimeout(poll, 800);
        else if (j.status === "COMPLETED") {
          const [evs, out] = await Promise.all([
            executions.events(executionId, 0, 5000),
            executions.output(executionId),
          ]);
          if (!alive) return;
          setEvents(evs.events);
          setOutput(out.stdout ?? "(no stdout)");
        }
      } catch (e) { if (alive) setError(String(e)); }
    };
    poll();
    return () => { alive = false; };
  }, [executionId]);

  if (!job) {
    return (
      <div className="execdock panel">
        <div className="panel-h">Execution &amp; Systems</div>
        <p className="muted"><span className="spinner" /> preparing run…</p>
      </div>
    );
  }
  if (["QUEUED", "RUNNING"].includes(job.status)) {
    return (
      <div className="execdock panel">
        <div className="panel-h">Execution &amp; Systems</div>
        <p className="notice">Execution {job.status.toLowerCase()}… in a restricted container
          <button className="btn ghost" onClick={() => executions.cancel(executionId)}>Cancel</button>
        </p>
      </div>
    );
  }
  if (job.status !== "COMPLETED") {
    return (
      <div className="execdock panel">
        <div className="panel-h">Execution &amp; Systems</div>
        <p className="err">Execution {job.status}: {job.error_code ?? "no output produced"}</p>
        <p className="muted">{job.note}</p>
      </div>
    );
  }

  return (
    <div className={"execdock panel" + (open ? "" : " collapsed")}>
      <div className="panel-h execdock-h">
        <button className="btn ghost" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {open ? "▾" : "▸"} Execution &amp; Systems
        </button>
        <span className="chip ok">exit {String(job.exit_code)}</span>
        <span className="chip">{job.duration_ms ?? "?"} ms</span>
        {job.trace_trust === "CURATED_COOPERATIVE" && (
          <span className="badge exact" title={`channel ${job.trace_channel ?? "?"}`}>trace: trusted</span>
        )}
        {job.trace_trust === "UNTRUSTED_TARGET" && (
          <span className="badge blocked" title="this program ran untrusted beside the observer">
            trace: UNTRUSTED_TARGET
          </span>
        )}
        {job.trace_integrity === "SUSPECT" && <span className="badge blocked">integrity SUSPECT</span>}
        <span className="spacer" />
        <span className="muted tech-only">recorded replay · never re-executes ·
          {" "}{events.length} events{job.events_truncated ? " (TRUNCATED)" : ""}</span>
      </div>
      {job.trace_trust === "UNTRUSTED_TARGET" && (
        <p className="trustnote" role="note">
          ⚠ This program ran untrusted in the same container as the observer. It could have
          attempted to alter or disable instrumentation, so these events are not guaranteed
          genuine{job.trace_integrity === "CONSISTENT" ? " (channel integrity checks passed, but the trust domain is shared)" : ""}.
        </p>
      )}
      {open && (
        <>
          <div className="exectabs" role="tablist" aria-label="execution evidence">
            {([["trace", "Trace theater"], ["memory", "MemoryScope"], ["process", "ProcessScope"], ["output", "Output"]] as const)
              .map(([t, label]) => (
                <button key={t} role="tab" aria-selected={tab === t}
                        className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
                  {label}
                </button>
              ))}
          </div>
          {tab === "trace" && (
            <TraceTheater events={events} job={job}
                          onSelectLine={onSelectLine} activeLine={activeLine} />
          )}
          {tab === "memory" && <MemoryPanel executionId={executionId} onSelectLine={onSelectLine} />}
          {tab === "process" && <ProcessPanel executionId={executionId} />}
          {tab === "output" && (
            <div className="execoutput">
              <pre className="excerpt">{output ?? "(none)"}</pre>
              <p className="muted tech-only">digests — stdout <code>{job.stdout_sha256?.slice(0, 20) ?? "—"}…</code> ·
                stderr <code>{job.stderr_sha256?.slice(0, 20) ?? "—"}…</code> ·
                trace <code>{job.trace_sha256?.slice(0, 20) ?? "—"}…</code></p>
            </div>
          )}
          {error && <p className="err">{error}</p>}
        </>
      )}
    </div>
  );
}

/* ————————————————— TraceTheater ————————————————— */

function TraceTheater({ events, job, onSelectLine, activeLine }: {
  events: ExecutionEvent[];
  job: ExecutionJob;
  onSelectLine: (line: number | null) => void;
  activeLine?: number | null;
}) {
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(120);
  const [selIdx, setSelIdx] = useState<number | null>(null);
  const treeRef = useRef<HTMLDivElement | null>(null);

  const tree = useMemo(() => buildTree(events), [events]);
  const maxDepth = useMemo(() => {
    let d = 0;
    const walk = (ns: TreeNode[]) => { for (const n of ns) { if (n.depth + 1 > d) d = n.depth + 1; walk(n.children); } };
    walk(tree);
    return d;
  }, [tree]);
  const frames = useMemo(() => stackAt(events, cursor), [events, cursor]);
  const totalCalls = useMemo(() => events.filter((e) => e.kind === "call").length, [events]);
  const current = cursor > 0 ? events[Math.min(cursor, events.length) - 1] : null;

  const tick = useCallback(() => setCursor((c) => Math.min(c + 1, events.length)), [events.length]);
  useEffect(() => {
    if (!playing) return;
    if (cursor >= events.length) { setPlaying(false); return; }
    const t = window.setTimeout(tick, speed);
    return () => clearTimeout(t);
  }, [playing, cursor, tick, speed, events.length]);

  // sync source line of the current event
  useEffect(() => {
    if (selIdx != null) {
      const e = events[selIdx];
      if (e) { onSelectLine((e.payload.line as number) ?? null); return; }
    }
    if (current) onSelectLine((current.payload.line as number) ?? null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cursor, selIdx, events]);

  const selectEvent = (idx: number) => {
    setPlaying(false);
    setSelIdx(idx);
    setCursor(idx + 1);
  };

  if (!events.length) {
    return <div className="unavailable"><span className="glyph">◍</span>
      This run produced no trace events{job.language === "c"
        ? " — the C trace shim records function calls/returns only; this target emitted none."
        : "."}</div>;
  }

  return (
    <div className="theater" role="region" aria-label="trace theater">
      <div className="theater-stats">
        <span className="chip"><i className="tf-dot k-name" />{totalCalls} calls</span>
        <span className="chip"><i className="tf-dot k-kw" />max depth {maxDepth}</span>
        <span className="chip">{events.length} events</span>
        {job.language === "c" && (
          <span className="muted">C shim records call/return only (no line events, no locals — policy)</span>
        )}
      </div>

      <div className="theater-grid">
        <div className="theater-tree panel" ref={treeRef} aria-label="recorded call tree">
          <div className="theater-pane-h">Call tree <span className="muted">(click a call to jump)</span></div>
          <div className="theater-tree-body">
            <TreeLevel nodes={tree} cursor={cursor} selIdx={selIdx}
                       onSelect={selectEvent} depthLimit={6} initial />
          </div>
        </div>

        <div className="theater-right">
          <div className="theater-tower panel" aria-label="stack frames at the playhead">
            <div className="theater-pane-h">Stack tower <span className="muted">(bottom = oldest frame)</span></div>
            <div className="tower-body">
              {frames.length === 0 && <p className="muted">— before the first call —</p>}
              {[...frames].reverse().map((f, i) => (
                <button key={`${f.callIdx}-${i}`}
                        className={"tower-frame" + (i === 0 ? " top" : "")}
                        onClick={() => selectEvent(f.callIdx)}
                        title={`frame created at event ${f.callIdx + 1}`}>
                  <code>{f.fn}</code>
                  {f.line != null && <span className="muted"> :{f.line}</span>}
                  {i === 0 && <span className="chip ok">active</span>}
                </button>
              ))}
            </div>
            {frames.length > 0 && frames[frames.length - 1].locals && (
              <div className="tower-locals">
                <div className="theater-pane-h">Variables of the active frame</div>
                <table className="insp-fields">
                  <tbody>
                    {Object.entries(frames[frames.length - 1].locals as Record<string, Record<string, unknown>>)
                      .slice(0, 10).map(([k, v]) => (
                        <tr key={k}>
                          <td>{k}</td>
                          <td><code>{String(v?.repr ?? v?.type ?? v?.identity ?? "—")}</code></td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {current && (
            <div className="theater-event panel" aria-label="current event">
              <div className="theater-pane-h">Playhead event</div>
              <p>
                <span className={`badge ${current.kind === "call" ? "exact" : current.kind === "return" ? "derived" : current.kind === "exception" ? "blocked" : "partial"}`}>
                  {current.kind}
                </span>{" "}
                <code>{String(current.payload.fn ?? "")}</code>
                {current.payload.line != null && <span className="muted"> :{String(current.payload.line)}</span>}
                {current.payload.exc != null && (
                  <span className="err"> {String(current.payload.exc)}: {String(current.payload.msg ?? "(user exception — message not captured)")}</span>
                )}
                {current.kind === "return" && current.payload.arg != null && (
                  <span> → <code>{String(current.payload.arg)}</code></span>
                )}
              </p>
            </div>
          )}
        </div>
      </div>

      <div className="theater-controls" role="toolbar" aria-label="replay controls">
        <button className="btn ghost" onClick={() => { setPlaying(false); setSelIdx(null); setCursor(0); }} aria-label="restart">⏮</button>
        <button className="btn ghost" onClick={() => { setPlaying(false); setSelIdx(null); setCursor((c) => Math.max(0, c - 1)); }} aria-label="step back">◀</button>
        <button className="btn primary" onClick={() => { setSelIdx(null); setPlaying(!playing); }} aria-label={playing ? "pause" : "play"}>
          {playing ? "⏸" : "▶"}
        </button>
        <button className="btn ghost" onClick={() => { setPlaying(false); setSelIdx(null); tick(); }} aria-label="step forward">▶</button>
        <button className="btn ghost" onClick={() => { setPlaying(false); setSelIdx(null); setCursor(events.length); }} aria-label="jump to end">⏭</button>
        <input type="range" min={0} max={events.length} value={cursor}
               aria-label="timeline position" style={{ flex: 1 }}
               onChange={(e) => { setPlaying(false); setSelIdx(null); setCursor(Number(e.target.value)); }} />
        <select className="input" style={{ width: "auto" }} value={speed} aria-label="playback speed"
                onChange={(e) => setSpeed(Number(e.target.value))}>
          <option value={400}>0.3×</option>
          <option value={120}>1×</option>
          <option value={40}>3×</option>
          <option value={10}>12×</option>
        </select>
        <span className="muted">{cursor}/{events.length}</span>
      </div>
      {activeLine != null && <span className="tech-only prov">source sync: line {activeLine}</span>}
    </div>
  );
}

const MAX_RENDER = 400;

function TreeLevel({ nodes, cursor, selIdx, onSelect, depthLimit, initial }: {
  nodes: TreeNode[];
  cursor: number;
  selIdx: number | null;
  onSelect: (idx: number) => void;
  depthLimit: number;
  initial?: boolean;
}) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [aggOpen, setAggOpen] = useState<Set<number>>(new Set());
  const shown = useMemo(() => aggregate(nodes), [nodes]);

  const render = (n: TreeNode | AggNode, depth: number): React.ReactNode => {
    if (n.agg) {
      const open = aggOpen.has(n.nodes[0].idx);
      return (
        <div key={`agg-${n.nodes[0].idx}`} className="treenode">
          <button className="tncall agg" onClick={() => setAggOpen((s) => {
            const next = new Set(s); next.add(n.nodes[0].idx); return next;
          })}>
            <code>{n.fn}</code> <span className="chip">×{n.nodes.length}</span>
            <span className="muted">{open ? "(collapse)" : "(expand)"}</span>
          </button>
          {open && n.nodes.slice(0, 24).map((c) => render(c, depth + 1))}
          {open && n.nodes.length > 24 && <p className="muted" style={{ paddingLeft: 22 }}>…{n.nodes.length - 24} more identical calls (recorded, not rendered)</p>}
        </div>
      );
    }
    const onActivePath = n.idx < cursor && (n.retIdx == null || n.retIdx >= cursor);
    const visited = n.idx < cursor;
    const done = n.retIdx != null && n.retIdx < cursor;
    const open = expanded.has(n.idx) || (initial && depth < depthLimit);
    const kids = n.children;
    const activeCls = onActivePath ? " on-path" : "";
    return (
      <div key={n.idx} className="treenode">
        <div className="tnrow">
          <button className={`tncall${visited ? " visited" : ""}${done ? " done" : ""}${activeCls}${selIdx === n.idx ? " selected" : ""}`}
                  onClick={() => onSelect(n.idx)}>
            <code>{n.fn}</code>
            {n.line != null && <span className="muted">:{n.line}</span>}
            {n.ret && <span className="tnret">→ {n.ret.length > 24 ? n.ret.slice(0, 24) + "…" : n.ret}</span>}
            {kids.length > 0 && !open && <span className="chip">{kids.length} sub-calls</span>}
          </button>
          {kids.length > 0 && (
            <button className="btn ghost tnexp" aria-expanded={open}
                    onClick={() => setExpanded((s) => {
                      const next = new Set(s);
                      if (next.has(n.idx)) next.delete(n.idx); else next.add(n.idx);
                      return next;
                    })}>
              {open ? "–" : "+"}
            </button>
          )}
        </div>
        {open && kids.length > 0 && (
          <div className="tnkids">
            <TreeLevel nodes={kids.slice(0, MAX_RENDER)} cursor={cursor} selIdx={selIdx}
                       onSelect={onSelect} depthLimit={depthLimit} />
            {kids.length > MAX_RENDER && (
              <p className="muted" style={{ paddingLeft: 20 }}>
                …{kids.length - MAX_RENDER} more sub-calls recorded (raise the depth limit or search the timeline)
              </p>
            )}
          </div>
        )}
      </div>
    );
  };

  return <>{shown.map((n) => render(n, initial ? 0 : 99))}</>;
}
