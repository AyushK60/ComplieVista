import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ExecutionEvent, ExecutionJob, executions } from "../../api";
import MemoryPanel from "./MemoryPanel";
import ProcessPanel from "./ProcessPanel";

/**
 * Execution Observatory — recorded replay of a real restricted-container run,
 * centered on the relationships between calls, frames, variables and returns.
 * Primary navigation is the call structure canvas and the stack scene; the
 * timeline is secondary. Every value shown comes from the recorded trace —
 * nothing is simulated. C runs record call/return only (shim policy, labeled).
 */

interface Frame {
  fn: string;
  line: number | null;
  callIdx: number;
  locals: Record<string, unknown> | null;
}

type Locals = Record<string, Record<string, unknown>>;

export interface TreeNode {
  idx: number;              // index of the call event
  fn: string;
  line: number | null;
  args: Locals;             // locals recorded AT the call
  children: TreeNode[];
  ret: string | null;       // return value repr (from return event)
  retIdx: number | null;    // index of the matching return event
  depth: number;
  parent: TreeNode | null;
  eventCount: number;       // events from call to return (inclusive)
  agg?: false;
}

/** Trace values are typed records ({type,repr}|{type,identity}|{type,len}) —
 * render the honest repr, never "[object Object]". */
function retRepr(arg: unknown): string | null {
  if (arg == null) return null;
  if (typeof arg === "string") return arg;
  if (typeof arg === "object") {
    const a = arg as Record<string, unknown>;
    if (typeof a.repr === "string") return a.repr;
    if (typeof a.identity === "string") return a.identity;
    if (a.len != null) return `${String(a.type ?? "object")} len=${String(a.len)}`;
    if (a.type != null) return String(a.type);
  }
  return String(arg);
}

function localsRepr(v: Record<string, unknown> | undefined): string {
  if (!v) return "—";
  if (typeof v.repr === "string") return v.repr;
  if (typeof v.identity === "string") return v.identity;
  if (v.len != null) return `${String(v.type ?? "object")} len=${String(v.len)}`;
  return String(v.type ?? "—");
}

export function buildTree(events: ExecutionEvent[]): TreeNode[] {
  const roots: TreeNode[] = [];
  const stack: TreeNode[] = [];
  for (let i = 0; i < events.length; i++) {
    const e = events[i];
    if (e.kind === "call") {
      const node: TreeNode = {
        idx: i, fn: String(e.payload.fn ?? "?"), line: (e.payload.line as number) ?? null,
        args: (e.payload.locals as Locals) ?? {},
        children: [], ret: null, retIdx: null, depth: stack.length,
        parent: stack.length ? stack[stack.length - 1] : null, eventCount: 0,
      };
      (stack.length ? stack[stack.length - 1].children : roots).push(node);
      stack.push(node);
    } else if (e.kind === "return") {
      const n = stack.pop();
      if (n) { n.ret = retRepr(e.payload.arg); n.retIdx = i; n.eventCount = i - n.idx + 1; }
    } else if (e.kind === "exception") {
      const n = stack[stack.length - 1];
      if (n) { n.ret = `✗ ${String(e.payload.exc ?? "exception")}`; n.retIdx = i; n.eventCount = i - n.idx + 1; }
    }
  }
  // unterminated frames (trace truncated): count to end
  for (const n of stack) n.eventCount = events.length - n.idx;
  return roots;
}

/** Merge consecutive same-name siblings (×N) to keep huge traces navigable.
 * The group reports the range of the argument that changed across calls, so
 * recursion (fib ×2: n=4, n=3) reads as changing arguments, not a wall of rows. */
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

/** The argument that varies across an aggregate group (for recursion: n). */
function aggArgSummary(nodes: TreeNode[]): string | null {
  const names = new Set<string>();
  for (const n of nodes.slice(0, 8)) {
    for (const k of Object.keys(n.args)) {
      const v = n.args[k];
      if (v && (typeof v.repr === "string" || typeof v.type === "string")) names.add(k);
    }
  }
  for (const name of names) {
    const vals = nodes.slice(0, 6).map((n) => localsRepr(n.args[name]));
    if (vals.length > 1 && new Set(vals).size > 1) return `${name}: ${vals.slice(0, 4).join(", ")}${nodes.length > 4 ? "…" : ""}`;
  }
  return null;
}

export function stackAt(events: ExecutionEvent[], cursor: number): Frame[] {
  const frames: Frame[] = [];
  for (let i = 0; i < cursor; i++) {
    const e = events[i];
    if (e.kind === "call") {
      frames.push({ fn: String(e.payload.fn ?? "?"), line: (e.payload.line as number) ?? null,
        callIdx: i, locals: (e.payload.locals as Record<string, unknown>) ?? null });
    } else if (e.kind === "return" || e.kind === "exception") {
      frames.pop();
    } else if (e.kind === "line" && frames.length) {
      frames[frames.length - 1].line = (e.payload.line as number) ?? frames[frames.length - 1].line;
    }
  }
  return frames;
}

const EVENT_KINDS = ["call", "line", "return", "exception"] as const;

export interface TraceFrame { fn: string; line: number | null; callIdx: number; locals: Record<string, unknown> | null }
export interface TreeNodeInfo extends TreeNode {}

export default function ExecutionDock({ executionId, onSelectLine, activeLine }: {
  executionId: string;
  onSelectLine: (line: number | null) => void;
  activeLine?: number | null;
}) {
  const [job, setJob] = useState<ExecutionJob | null>(null);
  const [events, setEvents] = useState<ExecutionEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);
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
          // paginate the recorded event stream (500/page cap) up to 5000 events
          setEventsLoading(true);
          const evs: ExecutionEvent[] = [];
          let after = 0;
          for (let page = 0; page < 10; page++) {
            const p = await executions.events(executionId, after, 500);
            evs.push(...p.events);
            const next = (p as { next_after?: number | null }).next_after ?? null;
            if (next == null || next <= after || evs.length >= 5000) break;
            after = next;
          }
          const out = await executions.output(executionId);
          if (!alive) return;
          setEvents(evs);
          setEventsLoading(false);
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
        <div className="panel-h">Execution Observatory</div>
        <p className="muted"><span className="spinner" /> preparing run…</p>
      </div>
    );
  }
  if (["QUEUED", "RUNNING"].includes(job.status)) {
    return (
      <div className="execdock panel">
        <div className="panel-h">Execution Observatory</div>
        <p className="notice">Execution {job.status.toLowerCase()}… in a restricted container
          <button className="btn ghost" onClick={() => executions.cancel(executionId)}>Cancel</button>
        </p>
      </div>
    );
  }
  if (job.status !== "COMPLETED") {
    return (
      <div className="execdock panel">
        <div className="panel-h">Execution Observatory</div>
        <p className="err">Execution {job.status}: {job.error_code ?? "no output produced"}</p>
        <p className="muted">{job.note}</p>
      </div>
    );
  }

  return (
    <div className={"execdock panel" + (open ? "" : " collapsed")}>
      <div className="panel-h execdock-h">
        <button className="btn ghost" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {open ? "▾" : "▸"} Execution Observatory
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
            {([["trace", "Execution observatory"], ["memory", "MemoryScope"], ["process", "ProcessScope"], ["output", "Output"]] as const)
              .map(([t, label]) => (
                <button key={t} role="tab" aria-selected={tab === t}
                        className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
                  {label}
                </button>
              ))}
          </div>
          {tab === "trace" && (
            <TraceTheater events={events} job={job} loading={eventsLoading}
                          onSelectLine={onSelectLine} activeLine={activeLine}
                          onOpenOutput={() => setTab("output")} />
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

/* ————————————————— Execution Observatory (trace theater) ————————————————— */

const GUIDE_STEPS = [
  { cap: "step 1 · the first call", body: "Execution starts at the outermost frame. Every card below is a call the tracer actually recorded — click one to inspect it." },
  { cap: "step 2 · the recursive relationship", body: "Expanding the call shows its children: the recursive calls. Depth grows with each nesting level — this is the call stack becoming visible." },
  { cap: "step 3 · arguments change", body: "Each recursive call receives a smaller argument (shown right on the call card). The same function, different frames, different values." },
  { cap: "step 4 · the base case returns", body: "At the deepest level the function returns without calling itself again. The base case is where unwinding begins." },
  { cap: "step 5 · returns propagate", body: "Each frame hands its result to its parent — watch the return values flow up the tree toward the original call." },
  { cap: "step 6 · the output", body: "The original call finishes and the program prints. Open the Output tab to see the recorded stdout." },
];

function TraceTheater({ events, job, loading, onSelectLine, activeLine, onOpenOutput }: {
  events: ExecutionEvent[];
  job: ExecutionJob;
  loading?: boolean;
  onSelectLine: (line: number | null) => void;
  activeLine?: number | null;
  onOpenOutput: () => void;
}) {
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(120);
  const [selIdx, setSelIdx] = useState<number | null>(null);
  const [kindFilter, setKindFilter] = useState<Set<string>>(new Set());
  const [guidedStep, setGuidedStep] = useState<number | null>(null);
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

  /** next/prev event of the selected kinds (filter navigation) */
  const jumpKind = (dir: 1 | -1) => {
    setPlaying(false);
    const kinds = kindFilter.size ? kindFilter : new Set(EVENT_KINDS);
    let i = selIdx != null ? selIdx + dir : cursor - 1 + dir;
    while (i >= 0 && i < events.length) {
      if (kinds.has(events[i].kind)) { selectEvent(i); return; }
      i += dir;
    }
  };

  // guided execution story: each step drives the canvas itself
  const treeByFn = useMemo(() => {
    const m = new Map<string, TreeNode[]>();
    const walk = (ns: TreeNode[]) => { for (const n of ns) { if (!m.has(n.fn)) m.set(n.fn, []); m.get(n.fn)!.push(n); walk(n.children); } };
    walk(tree);
    return m;
  }, [tree]);
  useEffect(() => {
    if (guidedStep == null) return;
    setPlaying(false);
    const mainCalls = treeByFn.get(tree[0]?.fn ?? "<module>") ?? [];
    if (guidedStep === 0) {
      setSelIdx(null); setCursor(0);
      const first = tree[0];
      if (first) selectEvent(first.idx);
    }
    if (guidedStep === 1) {
      // expand one recursion level: select first call that HAS children
      const found: TreeNode[] = [];
      const walk = (ns: TreeNode[]) => { for (const n of ns) { if (!found.length && n.children.length > 0) found.push(n); walk(n.children); } };
      walk(tree);
      if (found.length) { selectNodeDeep(found[0].idx); selectEvent(found[0].idx); }
    }
    if (guidedStep === 2) {
      // a deeper recursive call with a different argument
      const recFn = Object.keys(treeByFn).find((f) => (treeByFn.get(f)?.length ?? 0) > 1 && f !== tree[0]?.fn);
      const t = recFn ? treeByFn.get(recFn)![Math.min(1, (treeByFn.get(recFn)?.length ?? 1) - 1)] : null;
      if (t) { selectNodeDeep(t.idx); selectEvent(t.idx); }
      else if (mainCalls[1]) selectEvent(mainCalls[1].idx);
    }
    if (guidedStep === 3) {
      // the deepest call = the base case
      let maxDepth = -1;
      let deepestIdx: number | null = null;
      const walk = (ns: TreeNode[]) => { for (const n of ns) { if (n.depth > maxDepth) { maxDepth = n.depth; deepestIdx = n.idx; } walk(n.children); } };
      walk(tree);
      if (deepestIdx != null) { selectNodeDeep(deepestIdx); selectEvent(deepestIdx); }
    }
    if (guidedStep === 4) {
      // a return event propagating: pick the shallowest call WITH a return value
      let bestDepth = Infinity;
      let retIdx: number | null = null;
      let nodeIdx: number | null = null;
      const walk = (ns: TreeNode[]) => { for (const n of ns) { if (n.ret && n.retIdx != null && n.depth < bestDepth) { bestDepth = n.depth; retIdx = n.retIdx; nodeIdx = n.idx; } walk(n.children); } };
      walk(tree);
      if (nodeIdx != null && retIdx != null) { selectNodeDeep(nodeIdx); selectEvent(retIdx); }
    }
    if (guidedStep === 5) { setSelIdx(null); setCursor(events.length); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guidedStep]);

  /** expand ancestors of a node so it is visible in the tree */
  const selectNodeDeep = (idx: number) => {
    setExpandRequest(idx);
  };
  const [expandRequest, setExpandRequest] = useState<number | null>(null);

  if (loading) {
    return <p className="muted" style={{ padding: 16 }} role="status">
      <span className="spinner" /> loading recorded events…</p>;
  }
  if (!events.length) {
    return <div className="unavailable"><span className="glyph">◍</span>
      This run produced no trace events{job.language === "c"
        ? " — the C trace shim records function calls/returns only; this target emitted none."
        : "."}</div>;
  }

  return (
    <div className="theater" role="region" aria-label="execution observatory">
      <div className="theater-stats">
        <span className="chip"><i className="tf-dot k-name" />{totalCalls} calls</span>
        <span className="chip"><i className="tf-dot k-kw" />max depth {maxDepth}</span>
        <span className="chip">{events.length} events</span>
        {(EVENT_KINDS as readonly string[]).map((k) => (
          <button key={k} className={`chip kindchip${kindFilter.has(k) ? " on" : ""}`}
                  aria-pressed={kindFilter.has(k)}
                  title={kindFilter.has(k) ? `remove ${k} from filter navigation` : `navigate ${k} events only`}
                  onClick={() => setKindFilter((prev) => {
                    const next = new Set(prev);
                    if (next.has(k)) next.delete(k); else next.add(k);
                    return next;
                  })}>
            {k}
          </button>
        ))}
        {job.language === "c" && (
          <span className="muted">C shim records call/return only (no line events, no locals — policy)</span>
        )}
      </div>

      {guidedStep != null && (
        <div className="tf-guided" role="note" aria-live="polite">
          <div className="tf-guided-h"><span>guided · execution · step {guidedStep + 1}/{GUIDE_STEPS.length}</span></div>
          <p className="tf-guided-step">{GUIDE_STEPS[guidedStep].body}</p>
          <div className="tf-guided-actions">
            <button className="btn ghost" onClick={() => setGuidedStep((s) => Math.max(0, (s ?? 0) - 1))} disabled={guidedStep === 0}>← back</button>
            {guidedStep < GUIDE_STEPS.length - 1
              ? <button className="btn primary" onClick={() => setGuidedStep((s) => (s ?? 0) + 1)}>continue →</button>
              : <button className="btn primary" onClick={onOpenOutput}>show the recorded output →</button>}
            <button className="btn ghost" onClick={() => setGuidedStep(null)}>exit guided</button>
            <div className="tf-guided-dots" aria-hidden>
              {GUIDE_STEPS.map((_, i) => <span key={i} className={i === guidedStep ? "on" : ""} />)}
            </div>
          </div>
        </div>
      )}

      <div className="theater-grid">
        <div className="theater-tree panel" aria-label="recorded call structure">
          <div className="theater-pane-h">
            Call structure
            <span className="spacer" />
            {!guidedStep && (
              <button className="btn ghost" style={{ fontSize: 11, padding: "2px 10px" }}
                      onClick={() => setGuidedStep(0)}>guided story</button>
            )}
          </div>
          <div className="theater-tree-body">
            <TreeLevel nodes={tree} cursor={cursor} selIdx={selIdx}
                       onSelect={selectEvent} expandRequest={expandRequest}
                       depthLimit={6} initial />
          </div>
        </div>

        <div className="theater-right">
          <CallDetail events={events} tree={tree} selIdx={selIdx}
                      onSelect={selectEvent} onSelectLine={onSelectLine} />

          <div className="theater-tower panel" aria-label="stack frames at the playhead">
            <div className="theater-pane-h">Stack scene <span className="muted">(top = active frame)</span></div>
            <div className="tower-body">
              {frames.length === 0 && <p className="muted">— before the first call —</p>}
              {[...frames].reverse().map((f, i) => (
                <button key={`${f.callIdx}-${i}`}
                        className={"tower-frame" + (i === 0 ? " top" : "")}
                        onClick={() => selectEvent(f.callIdx)}
                        title={`frame created at event ${f.callIdx + 1}`}>
                  <span className="tower-link" aria-hidden />
                  <code>{f.fn}</code>
                  {f.line != null && <span className="muted"> :{f.line}</span>}
                  {i === 0 && <span className="chip ok">active</span>}
                </button>
              ))}
            </div>
            {frames.length > 0 && frames[frames.length - 1].locals && (
              <div className="tower-locals">
                <div className="theater-pane-h">Variables of the active frame
                  <span className="muted"> · recorded at call</span></div>
                <table className="insp-fields">
                  <tbody>
                    {Object.entries(frames[frames.length - 1].locals as Locals)
                      .slice(0, 8).map(([k, v]) => (
                        <tr key={k}>
                          <td>{k}</td>
                          <td><code>{localsRepr(v)}</code></td>
                        </tr>
                      ))}
                  </tbody>
                </table>
                <p className="muted" style={{ padding: "0 14px 10px", fontSize: 11 }}>
                  These are the values the tracer recorded when the frame was created.
                  {job.language === "c" && " The C shim does not record locals."}
                </p>
              </div>
            )}
          </div>
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
        <span className="kindnav">
          <button className="btn ghost" onClick={() => jumpKind(-1)} aria-label="previous filtered event"
                  title="previous event of the filtered kinds">⇤</button>
          <button className="btn ghost" onClick={() => jumpKind(1)} aria-label="next filtered event"
                  title="next event of the filtered kinds">⇥</button>
        </span>
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

/* ————————————————— call detail ————————————————— */

function CallDetail({ events, tree, selIdx, onSelect, onSelectLine }: {
  events: ExecutionEvent[];
  tree: TreeNode[];
  selIdx: number | null;
  onSelect: (idx: number) => void;
  onSelectLine: (line: number | null) => void;
}) {
  const info = useMemo(() => {
    if (selIdx == null) return null;
    const e = events[selIdx];
    if (!e) return null;
    if (e.kind === "call") {
      let node: TreeNode | null = null;
      const walk = (ns: TreeNode[]) => { for (const n of ns) { if (n.idx === selIdx) node = n; walk(n.children); } };
      walk(tree);
      return { kind: "call" as const, node };
    }
    // return/line/exception: find the enclosing frame's call
    let node: TreeNode | null = null;
    const walk = (ns: TreeNode[]) => {
      for (const n of ns) {
        if ((n.retIdx != null && selIdx <= n.retIdx && selIdx >= n.idx)
            || (n.retIdx == null && selIdx >= n.idx)) {
          if (!node || n.depth > (node as TreeNode).depth) node = n;
        }
        walk(n.children);
      }
    };
    walk(tree);
    return { kind: e.kind, node };
  }, [selIdx, events, tree]);

  if (!info || !info.node) {
    return (
      <div className="calldetail panel" aria-label="call detail">
        <div className="theater-pane-h">Call detail</div>
        <p className="muted" style={{ padding: "10px 14px" }}>
          Select a call in the structure — its recorded arguments, return value,
          ancestry and event span appear here.
        </p>
      </div>
    );
  }
  const n = info.node as TreeNode;
  const ev = events[selIdx!];
  const ancestry: TreeNode[] = [];
  let p = n.parent;
  while (p) { ancestry.unshift(p); p = p.parent; }
  const args = Object.entries(n.args ?? {}).slice(0, 8);

  return (
    <div className="calldetail panel" aria-label="call detail">
      <div className="theater-pane-h">
        Call detail
        <span className="spacer" />
        <span className="muted">events {n.idx + 1}–{(n.retIdx ?? events.length - 1) + 1} · {n.eventCount} recorded</span>
      </div>
      <div className="cd-body">
        <div className="cd-row">
          <span className="badge exact">{ev.kind}</span>
          <code>{n.fn}</code>
          {n.line != null && (
            <button className="btn ghost src-link" onClick={() => onSelectLine(n.line)}>
              ↦ source line {n.line}
            </button>
          )}
        </div>
        {ev.kind === "return" && ev.payload.arg != null && (
          <div className="cd-row"><span className="muted">returned</span>
            <code className="cd-ret">{retRepr(ev.payload.arg)}</code></div>
        )}
        {args.length > 0 && (
          <table className="insp-fields cd-args">
            <thead><tr><td colSpan={2}>arguments / locals recorded at the call</td></tr></thead>
            <tbody>
              {args.map(([k, v]) => (
                <tr key={k}><td>{k}</td><td><code>{localsRepr(v)}</code></td></tr>
              ))}
            </tbody>
          </table>
        )}
        {n.ret && (
          <div className="cd-row"><span className="muted">call returned</span>
            <code className="cd-ret">{n.ret}</code>
            {n.retIdx != null && (
              <button className="btn ghost" style={{ fontSize: 11, padding: "1px 8px" }}
                      onClick={() => onSelect(n.retIdx!)}>jump to return ⇥</button>
            )}
          </div>
        )}
        {ancestry.length > 0 && (
          <div className="cd-ancestry">
            <span className="muted">called from</span>
            {ancestry.map((a) => (
              <button key={a.idx} className="btn ghost cd-anc" onClick={() => onSelect(a.idx)}>
                {a.fn}:{a.line ?? "?"}
              </button>
            ))}
          </div>
        )}
        {n.children.length > 0 && (
          <div className="cd-row">
            <span className="muted">sub-calls</span>
            <span className="chip">{n.children.length} direct</span>
            {n.children.some((c) => c.children.length > 0) && (
              <button className="btn ghost" style={{ fontSize: 11, padding: "1px 8px" }}
                      onClick={() => onSelect(n.idx)}>focus in tree</button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ————————————————— tree rendering ————————————————— */

const MAX_RENDER = 400;

function TreeLevel({ nodes, cursor, selIdx, onSelect, expandRequest, depthLimit, initial }: {
  nodes: TreeNode[];
  cursor: number;
  selIdx: number | null;
  onSelect: (idx: number) => void;
  expandRequest: number | null;
  depthLimit: number;
  initial?: boolean;
}) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [aggOpen, setAggOpen] = useState<Set<number>>(new Set());
  const shown = useMemo(() => aggregate(nodes), [nodes]);

  // when a deep node is requested (guided script), expand its ancestor line
  useEffect(() => {
    if (expandRequest == null) return;
    setExpanded((prev) => {
      const next = new Set(prev);
      let added = false;
      const contains = (ns: TreeNode[], idx: number): TreeNode | null => {
        for (const n of ns) {
          if (n.idx === idx) return n;
          const r = contains(n.children, idx);
          if (r) { if (!next.has(n.idx)) { next.add(n.idx); added = true; } return r; }
        }
        return null;
      };
      contains(nodes, expandRequest);
      return added ? next : prev;
    });
  }, [expandRequest, nodes]);

  const render = (n: TreeNode | AggNode, depth: number): React.ReactNode => {
    if (n.agg) {
      const open = aggOpen.has(n.nodes[0].idx);
      const argSummary = aggArgSummary(n.nodes);
      return (
        <div key={`agg-${n.nodes[0].idx}`} className="treenode">
          <button className="tncall agg" onClick={() => setAggOpen((s) => {
            const next = new Set(s); next.add(n.nodes[0].idx); return next;
          })}>
            <code>{n.fn}</code> <span className="chip">×{n.nodes.length}</span>
            {argSummary && <span className="tnargs">{argSummary}</span>}
            <span className="muted">{open ? "(collapse)" : "(expand repeated calls)"}</span>
          </button>
          {open && n.nodes.slice(0, 24).map((c) => render(c, depth + 1))}
          {open && n.nodes.length > 24 && <p className="muted" style={{ paddingLeft: 22 }}>…{n.nodes.length - 24} more identical calls (recorded, not rendered)</p>}
        </div>
      );
    }
    const onActivePath = n.idx < cursor && (n.retIdx == null || n.retIdx >= cursor);
    const visited = n.idx < cursor;
    const done = n.retIdx != null && n.retIdx < cursor;
    const open = expanded.has(n.idx) || (initial && n.depth < depthLimit);
    const kids = n.children;
    const activeCls = onActivePath ? " on-path" : "";
    const argReprs = Object.entries(n.args ?? {})
      .filter(([k]) => !k.startsWith("__"))
      .slice(0, 2)
      .map(([k, v]) => `${k}=${localsRepr(v).slice(0, 12)}`).join(" ");
    return (
      <div key={n.idx} className="treenode">
        <div className="tnrow">
          <button className={`tncall${visited ? " visited" : ""}${done ? " done" : ""}${activeCls}${selIdx === n.idx ? " selected" : ""}`}
                  onClick={() => onSelect(n.idx)}>
            <code>{n.fn}</code>
            {n.line != null && <span className="muted">:{n.line}</span>}
            {argReprs && <span className="tnargs">{argReprs}</span>}
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
                       onSelect={onSelect} expandRequest={expandRequest} depthLimit={depthLimit} initial={initial} />
            {kids.length > MAX_RENDER && (
              <p className="muted" style={{ paddingLeft: 20 }}>
                …{kids.length - MAX_RENDER} more sub-calls recorded (raise the depth limit or use the filtered jump)
              </p>
            )}
          </div>
        )}
      </div>
    );
  };

  return <>{shown.map((n) => render(n, initial ? 0 : 99))}</>;
}
