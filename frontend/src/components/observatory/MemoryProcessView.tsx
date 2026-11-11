import { useEffect, useMemo, useRef, useState } from "react";
import { ExecutionEvent, loadAllEvents } from "../../api";
import MemoryPanel from "./MemoryPanel";
import ProcessPanel from "./ProcessPanel";
import { buildTree, localsRepr, stackAt, TreeNode } from "./traceModel";

/**
 * Memory and process, up front: a scrubbable stack-and-call-tree playback over the RECORDED
 * trace events, then the recorded heap/frame observations (MemoryScope) and /proc samples
 * (ProcessScope). Nothing is simulated: moving the slider only changes which recorded
 * event is the cursor. C runs record call/return only, so their stack has no locals.
 */
function flatten(nodes: TreeNode[], out: TreeNode[] = []): TreeNode[] {
  for (const n of nodes) { out.push(n); flatten(n.children, out); }
  return out;
}

export default function MemoryProcessView({ executionId, onSelectLine }: {
  executionId: string; onSelectLine: (line: number) => void;
}) {
  const [events, setEvents] = useState<ExecutionEvent[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    let alive = true;
    setEvents(null); setCursor(0); setPlaying(false);
    loadAllEvents(executionId)
      .then((e) => { if (alive) setEvents(e); })
      .catch((e) => { if (alive) setErr(String(e)); });
    return () => { alive = false; };
  }, [executionId]);

  const evs = useMemo(() => events ?? [], [events]);
  const tree = useMemo(() => flatten(buildTree(evs)), [evs]);
  const stack = useMemo(() => stackAt(evs, cursor), [evs, cursor]);
  const maxDepth = Math.max(0, ...tree.map((n) => n.depth));

  useEffect(() => {
    clearInterval(timer.current);
    if (!playing || !evs.length) return;
    timer.current = setInterval(() => setCursor((c) => {
      if (c >= evs.length) { setPlaying(false); return c; }
      return c + 1;
    }), 220);
    return () => clearInterval(timer.current);
  }, [playing, evs.length]);

  const active = (n: TreeNode) => n.idx < cursor && (n.retIdx == null || n.retIdx >= cursor);
  const cur = cursor > 0 ? evs[cursor - 1] : undefined;
  useEffect(() => {
    const l = cur?.payload.line;
    if (typeof l === "number") onSelectLine(l);
  }, [cur]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="mpv">
      <header className="mpv-h">
        <h2>Memory and process</h2>
        <p className="muted">Step through the recorded run and watch the call stack grow and unwind, then see the heap
          blocks and operating-system view of the same run. Everything is replayed from the recording.</p>
      </header>

      {err && <p className="err">{err}</p>}
      {!events && !err && <p className="muted"><span className="spinner" /> loading recorded events…</p>}
      {events && events.length === 0 && <p className="muted">This run recorded no call or line events.</p>}
      {events && events.length > 0 && (
        <section className="mpv-play" aria-label="stack and call tree playback">
          <div className="mpv-ctl">
            <button className="btn" onClick={() => { setCursor(0); setPlaying(false); }}>⏮ Start</button>
            <button className="btn" onClick={() => setCursor((c) => Math.max(0, c - 1))} aria-label="previous event">◀</button>
            <button className="btn primary" aria-pressed={playing}
                    onClick={() => { if (cursor >= evs.length) setCursor(0); setPlaying((p) => !p); }}>
              {playing ? "❚❚ Pause" : "▶ Play"}</button>
            <button className="btn" onClick={() => setCursor((c) => Math.min(evs.length, c + 1))} aria-label="next event">▶</button>
            <input type="range" min={0} max={evs.length} value={cursor} aria-label="event position"
                   onChange={(e) => { setPlaying(false); setCursor(Number(e.target.value)); }} />
            <span className="muted">event {cursor} / {evs.length} · {tree.length} calls · max depth {maxDepth + 1}</span>
          </div>
          <div className="mpv-grid">
            <div>
              <h4>Call stack <span className="badge exact">recorded</span></h4>
              <ol className="mpv-stack" aria-live="polite" aria-label="call stack, newest on top">
                {stack.length === 0 && <li className="mpv-empty">(empty)</li>}
                {[...stack].reverse().map((f, i) => (
                  <li key={f.callIdx} className={i === 0 ? "top" : ""}>
                    <b>{f.fn}</b>{f.line != null && <span className="muted"> line {f.line}</span>}
                    {f.locals && Object.keys(f.locals).length > 0 && (
                      <code>{Object.entries(f.locals).slice(0, 6).map(([k, v]) => `${k}=${localsRepr(v as Record<string, unknown>)}`).join("  ")}</code>
                    )}
                  </li>
                ))}
              </ol>
            </div>
            <div>
              <h4>Call tree <span className="badge exact">recorded</span></h4>
              <ul className="mpv-tree" aria-label="call tree">
                {tree.slice(0, 300).map((n) => (
                  <li key={n.idx} data-on={active(n) ? "" : undefined} data-done={n.retIdx != null && n.retIdx < cursor ? "" : undefined}
                      style={{ paddingLeft: 8 + n.depth * 16 }}>
                    <code>{n.fn}</code>
                    {n.ret != null && n.retIdx != null && n.retIdx < cursor && <span className="muted"> → {n.ret}</span>}
                  </li>
                ))}
                {tree.length > 300 && <li className="muted">… {tree.length - 300} further calls (bounded view)</li>}
              </ul>
            </div>
          </div>
        </section>
      )}

      <section aria-label="heap and frame observations">
        <h3>Memory <span className="muted">heap blocks, frames and objects as recorded</span></h3>
        <MemoryPanel executionId={executionId} onSelectLine={onSelectLine} />
      </section>
      <section aria-label="process observations">
        <h3>Process <span className="muted">resource lanes, children and threads sampled from /proc</span></h3>
        <ProcessPanel executionId={executionId} />
      </section>
    </div>
  );
}
