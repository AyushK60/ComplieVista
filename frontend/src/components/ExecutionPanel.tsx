import { useCallback, useEffect, useRef, useState } from "react";
import { ExecutionEvent, ExecutionJob, executions } from "../api";

/**
 * M4-E recorded replay timeline: play/pause/step forward/BACK/jump over recorded
 * events. The banner is explicit: replay navigates recorded history; it never
 * re-runs the program. Source highlighting via onSelectLine.
 */
export default function ExecutionPanel({
  executionId, onSelectLine,
}: { executionId: string; onSelectLine: (line: number | null) => void }) {
  const [job, setJob] = useState<ExecutionJob | null>(null);
  const [events, setEvents] = useState<ExecutionEvent[]>([]);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [output, setOutput] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    let alive = true;
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

  const tick = useCallback(() => {
    setCursor((c) => Math.min(c + 1, events.length));
  }, [events.length]);

  useEffect(() => {
    if (!playing) return;
    if (cursor >= events.length) { setPlaying(false); return; }
    timerRef.current = window.setTimeout(tick, 120);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [playing, cursor, tick, events.length]);

  if (!job) return <p className="muted">Loading execution…</p>;
  if (["QUEUED", "RUNNING"].includes(job.status)) {
    return (
      <div className="execution">
        <p className="notice">Execution {job.status.toLowerCase()}… (restricted container)
          <button className="cancel" onClick={() => executions.cancel(executionId)}>Cancel</button>
        </p>
      </div>
    );
  }
  if (job.status === "BLOCKED") {
    return <p className="err">Execution BLOCKED: {job.error_code}</p>;
  }
  if (job.status !== "COMPLETED") {
    return <p className="err">Execution {job.status}: {job.error_code ?? ""}</p>;
  }

  const current = events.length > 0 && cursor > 0 ? events[Math.min(cursor, events.length) - 1] : null;
  if (current) {
    const line = (current.payload?.line as number) ?? null;
    if (line != null && onSelectLine) {
      // eslint-disable-next-line react-hooks/exhaustive-deps
      setTimeout(() => onSelectLine(line), 0);
    }
  }

  return (
    <div className="execution" role="region" aria-label="execution replay">
      <p className="replay-banner">
        Recorded replay — does not rewind the running process.
        exit={job.exit_code} · {job.duration_ms}ms · {events.length} events
        {job.events_truncated ? " · TRUNCATED" : ""}
      </p>
      <div className="timeline-controls" role="toolbar" aria-label="replay controls">
        <button onClick={() => setCursor(0)} aria-label="jump to start">⏮</button>
        <button onClick={() => { setPlaying(false); setCursor((c) => Math.max(0, c - 1)); }}
                aria-label="step back">◀◀</button>
        <button onClick={() => setPlaying(!playing)} aria-label={playing ? "pause" : "play"}>
          {playing ? "⏸" : "▶"}
        </button>
        <button onClick={() => { setPlaying(false); tick(); }} aria-label="step forward">▶▶</button>
        <button onClick={() => { setPlaying(false); setCursor(events.length); }}
                aria-label="jump to end">⏭</button>
        <input type="range" min={0} max={events.length} value={cursor}
               onChange={(e) => { setPlaying(false); setCursor(Number(e.target.value)); }}
               aria-label="timeline position" style={{ flex: 1 }} />
        <span className="muted">{cursor}/{events.length}</span>
      </div>
      {current && (
        <div className="event-detail">
          <p><code>{current.kind}</code> {String(current.payload?.fn ?? "")}
            {current.payload?.line ? ` :${current.payload.line}` : ""}
            {current.payload?.exc ? ` — ${current.payload.exc}: ${current.payload.msg}` : ""}</p>
          {current.payload?.locals != null && (
            <table className="grid locals">
              <tbody>
                {Object.entries(current.payload.locals as Record<string, Record<string, unknown>>)
                  .slice(0, 12).map(([k, v]) => (
                    <tr key={k}><td>{k}</td><td>{String(v?.repr ?? v?.type ?? "—")}</td></tr>
                  ))}
              </tbody>
            </table>
          )}
        </div>
      )}
      <details>
        <summary className="muted">Program output (stdout)</summary>
        <pre className="excerpt">{output}</pre>
      </details>
      {error && <p className="err">{error}</p>}
      <p className="muted">{job.note}</p>
    </div>
  );
}
