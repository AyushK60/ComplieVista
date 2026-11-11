import { useCallback, useEffect, useMemo, useState } from "react";
import { ExecutionEvent, executions, loadAllEvents } from "../../api";

import { buildTree, stackAt, TreeNode } from "./ExecutionDock";

/**
 * Visual Program Walkthrough - "Watch This Program Work".
 * A beginner-oriented execution scene driven ONLY by the recorded trace:
 *   • the active source line (from real line events),
 *   • the executed flow of the active function (line sequence, loop iteration
 *     counters DERIVED from revisits of a line within one frame - labeled),
 *   • the call/stack stage (recorded frames),
 *   • the variable stage (locals recorded at call; memory-snapshot diffs where
 *     the cooperative tracer provided them - snapshot-based, labeled),
 *   • the recorded output (whole-run; per-print timing is not recorded).
 * Navigation steps through MEANINGFUL events (calls, returns, exceptions, and
 * line changes) so a coherent story plays without pressing Next constantly.
 */

interface Frame { fn: string; line: number | null; callIdx: number; locals: Record<string, unknown> | null }
type Locals = Record<string, Record<string, unknown>>;

function localsRepr(v: Record<string, unknown> | undefined): string {
  if (!v) return "—";
  if (typeof v.repr === "string") return v.repr;
  if (typeof v.identity === "string") return v.identity;
  if (v.len != null) return `${String(v.type ?? "object")} len=${String(v.len)}`;
  return String(v.type ?? "—");
}

export default function ProgramWalkthrough({ executionId, sourceText, onSelectLine }: {
  executionId: string;
  sourceText: string;
  onSelectLine: (line: number | null) => void;
}) {
  const [events, setEvents] = useState<ExecutionEvent[]>([]);
  const [snapshots, setSnapshots] = useState<Array<{ seq: number; payload: Record<string, unknown> }>>([]);
  const [output, setOutput] = useState<string | null>(null);
  const [job, setJob] = useState<{ status: string; exit_code: number | null } | null>(null);
  const [mi, setMi] = useState(0);          // index into the meaningful event list
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);    // 0.5 | 1 | 1.5 | 2 (explanatory pacing)
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const j = await executions.get(executionId);
        if (!alive) return;
        setJob({ status: j.status, exit_code: j.exit_code });
        if (j.status !== "COMPLETED") return;
        const evs = await loadAllEvents(executionId);
        const out = await executions.output(executionId);
        // memory frame snapshots (may not exist for every profile - honest absence)
        let snaps: Array<{ seq: number; payload: Record<string, unknown> }> = [];
        try {
          const m = await executions.memory(executionId, 0, 500);
          snaps = (m.chunks ?? []).map((c) => ({ seq: c.seq, payload: c.payload }));
        } catch { /* snapshots unavailable - variable stage falls back to call locals */ }
        if (!alive) return;
        setLoading(false);
        setEvents(evs);
        setSnapshots(snaps);
        setOutput(out.stdout ?? "(no stdout)");
      } catch (e) { if (alive) { setLoading(false); setError(String(e)); } }
    })();
    return () => { alive = false; };
  }, [executionId]);

  const tree = useMemo(() => buildTree(events), [events]);
  const nodeByIdx = useMemo(() => {
    const m = new Map<number, TreeNode>();
    const walk = (ns: TreeNode[]) => { for (const n of ns) { m.set(n.idx, n); walk(n.children); } };
    walk(tree);
    return m;
  }, [tree]);

  /** meaningful events: calls, returns, exceptions, and line CHANGES */
  const meaningful = useMemo(() => {
    const out: number[] = [];
    let lastLineByFn = new Map<string, number>();
    for (let i = 0; i < events.length; i++) {
      const e = events[i];
      if (e.kind !== "line") { out.push(i); continue; }
      const fn = String(e.payload.fn ?? "");
      const ln = Number(e.payload.line ?? -1);
      if (lastLineByFn.get(fn) !== ln) out.push(i);
      lastLineByFn.set(fn, ln);
    }
    return out;
  }, [events]);

  const curIdx = meaningful.length ? meaningful[Math.min(mi, meaningful.length - 1)] : -1;
  const cur = curIdx >= 0 ? events[curIdx] : null;
  const framesAt = useMemo(() => stackAt(events, curIdx + 1), [events, curIdx]);
  const active: Frame | null = framesAt.length ? framesAt[framesAt.length - 1] : null;

  // loop indicator: DERIVED - the most-revisited line of the active frame.
  // Persists while the loop is running (any line of the frame), so the label
  // doesn't flash only when the playhead sits exactly on the loop header.
  const iterations = useMemo(() => {
    if (!active || !cur || cur.kind !== "line") return null;
    const visits = new Map<number, number>();
    for (let i = active.callIdx; i <= curIdx && i < events.length; i++) {
      const e = events[i];
      if (e.kind === "line" && e.payload.fn === active.fn) {
        const ln = Number(e.payload.line);
        visits.set(ln, (visits.get(ln) ?? 0) + 1);
      }
    }
    let max = 0;
    for (const c of visits.values()) max = Math.max(max, c);
    return max > 2 ? max : null;
  }, [active, cur, curIdx, events]);

  // latest memory snapshot for the active frame (event_seq <= current)
  const latestSnap = useMemo(() => {
    if (!active) return null;
    let best: Record<string, unknown> | null = null;
    for (const s of snapshots) {
      const p = s.payload;
      if (String(p.fn) === active.fn && Number(p.event_seq) <= curIdx + 1) best = p;
    }
    return best;
  }, [snapshots, active, curIdx]);

  // variable diff vs the previous snapshot of the same frame (honest: snapshot-based)
  const varRows = useMemo(() => {
    const rows: Array<{ name: string; value: string; state: "new" | "changed" | "same" }> = [];
    const prev = new Map<string, string>();
    if (latestSnap) {
      const before = new Map<string, string>();
      for (const s of snapshots) {
        const p = s.payload;
        if (String(p.fn) === (latestSnap.fn as string) && Number(p.frame_id) === Number(latestSnap.frame_id)
            && Number(p.event_seq) < Number(latestSnap.event_seq)) {
          before.clear();
          for (const l of (p.locals as Array<Record<string, unknown>>) ?? []) {
            before.set(String(l.name), localsRepr(l.preview as Record<string, unknown>));
          }
        }
      }
      for (const l of (latestSnap.locals as Array<Record<string, unknown>>) ?? []) {
        const name = String(l.name);
        const val = localsRepr(l.preview as Record<string, unknown>);
        rows.push({ name, value: val, state: !before.has(name) ? "new" : before.get(name) !== val ? "changed" : "same" });
      }
      return rows;
    }
    // no snapshots: locals recorded at the call
    const callLocals = active?.locals as Locals | null;
    if (callLocals) {
      for (const [k, v] of Object.entries(callLocals)) {
        if (!k.startsWith("__")) rows.push({ name: k, value: localsRepr(v), state: "same" });
      }
    }
    return rows;
  }, [latestSnap, snapshots, active]);

  // source of the active function for the flow stage
  const sourceLines = useMemo(() => sourceText.split("\n"), [sourceText]);
  const flowLines = useMemo(() => {
    if (!active) return [];
    const seq: Array<{ line: number; state: "done" | "active" }> = [];
    const seen = new Set<number>();
    for (let i = active.callIdx; i <= curIdx && i < events.length; i++) {
      const e = events[i];
      if (e.kind === "line" && e.payload.fn === active.fn) {
        const ln = Number(e.payload.line);
        if (!seen.has(ln)) { seen.add(ln); seq.push({ line: ln, state: "done" }); }
        else {
          const ex = seq.find((s) => s.line === ln);
          if (ex) ex.state = "done";
        }
      }
    }
    if (cur?.kind === "line" && cur.payload.fn === active.fn) {
      const ln = Number(cur.payload.line);
      const ex = seq.find((s) => s.line === ln);
      if (ex) ex.state = "active"; else seq.push({ line: ln, state: "active" });
    }
    return seq.slice(-9);
  }, [active, cur, curIdx, events]);

  const callNode = useMemo(() => {
    if (curIdx < 0) return null;
    let bestDepth = -1;
    let bestIdx = -1;
    const walk = (ns: TreeNode[]) => {
      for (const n of ns) {
        if (curIdx >= n.idx && (n.retIdx == null || curIdx <= n.retIdx) && n.depth > bestDepth) {
          bestDepth = n.depth; bestIdx = n.idx;
        }
        walk(n.children);
      }
    };
    walk(tree);
    return bestIdx >= 0 ? nodeByIdx.get(bestIdx) ?? null : null;
  }, [curIdx, tree, nodeByIdx]);

  const step = (d: number) => {
    setPlaying(false);
    setMi((v) => Math.max(0, Math.min(meaningful.length - 1, v + d)));
  };
  const tick = useCallback(() => setMi((v) => Math.min(meaningful.length - 1, v + 1)), [meaningful.length]);
  useEffect(() => {
    if (!playing) return;
    if (mi >= meaningful.length - 1) { setPlaying(false); return; }
    const t = window.setTimeout(tick, 900 / speed);
    return () => clearTimeout(t);
  }, [playing, mi, tick, speed, meaningful.length]);

  // scroll the active line into view in the source dock (rendered by the
  // workspace next to this scene - the single, full-height source view)
  useEffect(() => {
    const ln = cur?.kind === "line" ? Number(cur.payload.line) : active?.line;
    if (ln == null) return;
    const el = document.querySelector(`.sourcedock [data-line="${ln}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [cur, active]);

  useEffect(() => {
    const ln = cur?.kind === "line" ? Number(cur.payload.line) : active?.line ?? null;
    onSelectLine(ln);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [curIdx]);

  if (error) return <p className="err" style={{ padding: 16 }}>Walkthrough: {error}</p>;
  if (job && job.status !== "COMPLETED") {
    return <p className="muted" style={{ padding: 16 }}>Execution {job.status.toLowerCase()}… the walkthrough starts when the run completes.</p>;
  }
  if (loading) {
    return <p className="muted" style={{ padding: 16 }}><span className="spinner" /> Loading the recorded run…</p>;
  }
  if (!events.length) {
    return <div className="unavailable" style={{ margin: 16 }}><span className="glyph">◍</span>
      No recorded events for this run - the walkthrough needs a completed traced execution.</div>;
  }

  const explain = !cur ? "Press play to watch the recorded execution."
    : cur.kind === "call" ? `${cur.payload.fn} is called${cur.payload.line != null ? ` (line ${cur.payload.line})` : ""}.`
    : cur.kind === "return" ? `${cur.payload.fn} returns ${cur.payload.arg != null ? localsRepr((cur.payload.arg as Record<string, unknown>) ?? {}) : "—"} to its caller.`
    : cur.kind === "exception" ? `An exception (${String(cur.payload.exc ?? "?")}) unwinds the stack.`
    : `Line ${cur.payload.line} of ${cur.payload.fn} runs.`;

  return (
    <div className="walkthrough" role="region" aria-label="visual program walkthrough">
      <div className="wt-head">
        <span className="badge exact">recorded replay</span>
        <span className="muted">Watch This Program Work - the highlighted source line and every value below come from the recorded run.</span>
        <span className="spacer" />
        <span className="muted tech-only">meaningful event {Math.min(mi + 1, meaningful.length)}/{meaningful.length} · seq {curIdx + 1}</span>
      </div>

      <div className="wt-grid">
        {/* flow + call/stack */}
        <div className="wt-flow panel">
            <div className="theater-pane-h">
              What happens now
              {iterations != null && (
                <span className="chip partial" title="Derived from revisits of this line within the recorded frame - a derived view, not an instrumented counter">
                  loop pass ×{iterations}
                </span>
              )}
            </div>
            <p className="wt-explain">{explain}</p>
            {flowLines.length > 0 && (
              <div className="wt-flowlines">
                {flowLines.map((f, i) => (
                  <div key={i} className={"wt-flowline " + f.state}>
                    <code>{(sourceLines[f.line - 1] ?? "").slice(0, 64) || " "}</code>
                    <span className="muted">:{f.line}</span>
                  </div>
                ))}
              </div>
            )}
            {callNode && callNode.children.length > 0 && (
              <p className="muted" style={{ padding: "0 14px 10px", fontSize: 12 }}>
                this call made <b>{callNode.children.length}</b> sub-call{callNode.children.length === 1 ? "" : "s"}
                {callNode.ret != null && <> and returned <code>{callNode.ret.slice(0, 30)}</code></>}
              </p>
            )}
          </div>

        {/* variables */}
        <div className="wt-vars panel">
          <div className="theater-pane-h">
            Variables
            <span className="muted">{latestSnap ? " · snapshot diff" : " · recorded at call"}</span>
          </div>
          {varRows.length === 0
            ? <p className="muted" style={{ padding: "8px 14px" }}>no variables recorded for this frame</p>
            : <table className="insp-fields wt-vartable">
                <tbody>
                  {varRows.slice(0, 10).map((r) => (
                    <tr key={r.name} className={r.state !== "same" ? `var-${r.state}` : ""}>
                      <td>{r.name}{r.state === "changed" && <span className="badge partial">changed</span>}
                        {r.state === "new" && <span className="badge exact">new</span>}</td>
                      <td><code>{r.value}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>}
          <p className="muted" style={{ padding: "0 14px 10px", fontSize: 11 }}>
            {latestSnap
              ? "Changes compare the tracer's frame snapshots - snapshot-based, not live."
              : "Values were recorded when this frame was created; mid-call changes are not captured by this profile."}
          </p>
        </div>

        <div className="wt-stack panel">
          <div className="theater-pane-h">Call stack <span className="muted">(top = active)</span></div>
          <div className="wt-stackbody">
            {framesAt.length === 0 && <p className="muted" style={{ padding: "6px 14px" }}>— program starting —</p>}
            {[...framesAt].reverse().map((f, i) => (
              <div key={`${f.callIdx}-${i}`} className={"wt-frame" + (i === 0 ? " top" : "")}>
                <code>{f.fn}</code>
                {i === 0 && <span className="chip ok">active</span>}
              </div>
            ))}
          </div>
        </div>

        {/* output */}
        <div className="wt-out panel">
          <div className="theater-pane-h">Recorded output <span className="muted">(whole run - per-print timing is not recorded)</span></div>
          <pre className="wt-outbody" tabIndex={0} aria-label="program output">{output ?? "(none)"}</pre>
        </div>
      </div>

      <div className="theater-controls wt-controls" role="toolbar" aria-label="walkthrough controls">
        <button className="btn ghost" onClick={() => { setPlaying(false); setMi(0); }} aria-label="restart" title="back to the first event">«</button>
        <button className="btn ghost" onClick={() => step(-1)} aria-label="previous meaningful event" title="previous meaningful event">‹</button>
        <button className="btn primary" onClick={() => setPlaying(!playing)} aria-label={playing ? "pause" : "play"}
                title={playing ? "pause" : "play the recorded events"}>
          {playing ? "❚❚" : "▶"}
        </button>
        <button className="btn ghost" onClick={() => step(1)} aria-label="next meaningful event" title="next meaningful event">›</button>
        <button className="btn ghost" onClick={() => { setPlaying(false); setMi(meaningful.length - 1); }} aria-label="jump to end" title="jump to the last event">»</button>
        <input type="range" min={0} max={Math.max(meaningful.length - 1, 0)} value={Math.min(mi, meaningful.length - 1)}
               aria-label="walkthrough position" style={{ flex: 1 }}
               onChange={(e) => { setPlaying(false); setMi(Number(e.target.value)); }} />
        <select className="input" style={{ width: "auto" }} value={speed} aria-label="playback speed"
                onChange={(e) => setSpeed(Number(e.target.value))}>
          <option value={0.5}>0.5×</option>
          <option value={1}>1×</option>
          <option value={1.5}>1.5×</option>
          <option value={2}>2×</option>
        </select>
        <span className="muted">{Math.min(mi + 1, meaningful.length)}/{meaningful.length} meaningful events</span>
      </div>
    </div>
  );
}
