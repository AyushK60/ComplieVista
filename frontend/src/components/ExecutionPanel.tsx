import { useCallback, useEffect, useRef, useState } from "react";
import { ExecutionEvent, ExecutionJob, ObservationStream, executions } from "../api";
import MemoryScope from "./MemoryScope";
import ProcessScope from "./ProcessScope";

/**
 * M4-E/M5-E recorded replay timeline + MemoryScope/ProcessScope tabs. Replay
 * navigates recorded history and never re-runs the program; the memory/process
 * tabs browse recorded observations and never spawn containers.
 */
export default function ExecutionPanel({
  executionId, onSelectLine,
}: { executionId: string; onSelectLine: (line: number | null) => void }) {
  const [job, setJob] = useState<ExecutionJob | null>(null);
  const [events, setEvents] = useState<ExecutionEvent[]>([]);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [output, setOutput] = useState<string | null>(null);
  const [memory, setMemory] = useState<ObservationStream | null>(null);
  const [process, setProcess] = useState<ObservationStream | null>(null);
  const [tab, setTab] = useState<"replay" | "memory" | "process">("replay");
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    let alive = true;
    // M5QA: never show a previous run's evidence while the new one is pending.
    setEvents([]);
    setOutput(null);
    setMemory(null);
    setProcess(null);
    setCursor(0);
    setTab("replay");
    setError(null);
    const poll = async () => {
      try {
        const j = await executions.get(executionId);
        if (!alive) return;
        setJob(j);
        if (["QUEUED", "RUNNING"].includes(j.status)) setTimeout(poll, 800);
        else if (j.status === "COMPLETED") {
          const [evs, out, mem, proc] = await Promise.all([
            executions.events(executionId, 0, 5000),
            executions.output(executionId),
            executions.memory(executionId).catch(() => null),
            executions.process(executionId).catch(() => null),
          ]);
          if (!alive) return;
          setEvents(evs.events);
          setOutput(out.stdout ?? "(no stdout)");
          setMemory(mem);
          setProcess(proc);
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
      <div className="tabs" role="tablist" aria-label="execution evidence tabs">
        <button role="tab" aria-selected={tab === "replay"}
                className={tab === "replay" ? "active" : ""}
                onClick={() => setTab("replay")}>Replay</button>
        <button role="tab" aria-selected={tab === "memory"}
                className={tab === "memory" ? "active" : ""}
                onClick={() => setTab("memory")}>
          Memory{memory ? ` (${memory.total})` : ""}
        </button>
        <button role="tab" aria-selected={tab === "process"}
                className={tab === "process" ? "active" : ""}
                onClick={() => setTab("process")}>
          Process{process ? ` (${process.total})` : ""}
        </button>
      </div>
      {tab === "memory" && (
        <MemoryScope stream={memory}
                     cursorSeq={current?.seq ?? 0}
                     onSelectLine={(l) => onSelectLine(l)} />
      )}
      {tab === "process" && <ProcessScope stream={process} />}
      {tab === "replay" && <>
      <p className="replay-banner">
        Recorded replay — does not rewind the running process.
        exit={job.exit_code} · {job.duration_ms}ms · {events.length} events
        {job.events_truncated ? " · TRUNCATED" : ""}
      </p>
      {job.trace_trust === "UNTRUSTED_TARGET" && (
        <p className="notice" role="note" aria-label="trace trust warning">
          ⚠ Trace trust: UNTRUSTED_TARGET — this program ran untrusted in the same
          container as the observer; it could attempt to alter or disable
          instrumentation, so these events are NOT guaranteed genuine.
          {job.trace_integrity === "SUSPECT" ? " Channel integrity: SUSPECT." :
            " Channel integrity: consistent, channel: protected observer pipe."}
        </p>
      )}
      {job.trace_trust === "CURATED_COOPERATIVE" && (
        <p className="muted" role="note" aria-label="trace trust">
          Trace trust: CURATED_COOPERATIVE ({job.trace_channel ?? "recorded channel"} ·
          integrity {job.trace_integrity ?? "unrecorded"}).
        </p>
      )}
      {job.trace_integrity === "SUSPECT" && job.trace_trust !== "UNTRUSTED_TARGET" && (
        <p className="err" role="alert">Trace channel integrity SUSPECT — events may
          be incomplete or altered; treat this trace as unreliable.</p>
      )}
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
      </>}
      {error && <p className="err">{error}</p>}
      <p className="muted">{job.note}</p>
    </div>
  );
}
