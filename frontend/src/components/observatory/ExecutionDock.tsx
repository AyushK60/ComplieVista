import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ExecutionEvent, ExecutionJob, executions, loadAllEvents } from "../../api";
import MemoryPanel from "./MemoryPanel";
import ProcessPanel from "./ProcessPanel";
import TraceTheater from "./TraceTheater";
export { buildTree, stackAt } from "./traceModel";
export type { TreeNode } from "./traceModel";

/**
 * Execution Observatory — recorded replay of a real restricted-container run,
 * centered on the relationships between calls, frames, variables and returns.
 * Primary navigation is the call structure canvas and the stack scene; the
 * timeline is secondary. Every value shown comes from the recorded trace —
 * nothing is simulated. C runs record call/return only (shim policy, labeled).
 */

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
          setEventsLoading(true);
          const [evs, out] = await Promise.all([loadAllEvents(executionId), executions.output(executionId)]);
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
        <a className="btn ghost" href={`/api/v1/executions/${executionId}/replay.html`} download
           title="one self-contained HTML file that replays this recorded run offline — no backend needed">
          ⬇ Replay file
        </a>
        <span className="muted tech-only">recorded replay · never re-executes ·
          {" "}{events.length} events{job.events_truncated ? " (TRUNCATED)" : ""}</span>
      </div>
      {job.trace_trust === "UNTRUSTED_TARGET" && (
        <p className="trustnote" role="note" aria-label="trace trust warning">
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
              <pre className="excerpt" tabIndex={0} aria-label="program output">{output ?? "(none)"}</pre>
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
