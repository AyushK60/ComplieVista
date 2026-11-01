import { useEffect, useMemo, useState } from "react";
import { ObservationStream, executions } from "../../api";

/**
 * ProcessScope — container-side process evidence as a lifecycle scene:
 * a launch/exit band, the sampled RSS/threads/fds lanes (explicitly sampled,
 * never event data), observed children and exit thread ids. Syscall timelines
 * are UNSUPPORTED by policy and shown as an explained gap.
 */

interface Chunk { seq: number; payload: Record<string, unknown>; sha256: string }

export default function ProcessPanel({ executionId }: { executionId: string }) {
  const [stream, setStream] = useState<ObservationStream | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setStream(null); setErr(null);
    executions.process(executionId)
      .then((s) => { if (alive) setStream(s); })
      .catch((e) => { if (alive) setErr(String(e)); });
    return () => { alive = false; };
  }, [executionId]);

  const meta = useMemo(() =>
    stream?.chunks.find((c) => c.payload.kind === "proc_meta")?.payload ?? null, [stream]);
  const samples = useMemo(() =>
    (stream?.chunks ?? []).filter((c) => c.payload.kind === "proc_sample")
      .map((c) => c.payload as Record<string, number>), [stream]);
  const children = useMemo(() =>
    (stream?.chunks ?? []).filter((c) => c.payload.kind === "proc_children"), [stream]);
  const exit = useMemo(() =>
    stream?.chunks.find((c) => c.payload.kind === "proc_exit")?.payload ?? null, [stream]);
  const truncated = useMemo(() =>
    (stream?.chunks ?? []).some((c) => c.payload.kind === "meta" && c.payload.truncated === true), [stream]);

  if (err) return <p className="err">ProcessScope: {err}</p>;
  if (!stream) return <p className="muted"><span className="spinner" /> loading process records…</p>;

  const W = 640, H = 170;
  const pad = 30;
  const maxRss = Math.max(...samples.map((s) => s.rss_kb ?? 0), 1);
  const maxThreads = Math.max(...samples.map((s) => s.threads ?? 0), 1);
  const maxFd = Math.max(...samples.map((s) => s.fds ?? 0), 1);
  const x = (i: number) => pad + (i * (W - pad * 2)) / Math.max(samples.length - 1, 1);
  const yRss = (v: number) => H - pad - (v / maxRss) * (H - pad * 2);

  const areaPath = samples.length
    ? `M ${x(0)} ${H - pad} ` +
      samples.map((s, i) => `L ${x(i)} ${yRss(s.rss_kb ?? 0)}`).join(" ") +
      ` L ${x(samples.length - 1)} ${H - pad} Z`
    : "";

  return (
    <div className="proscope" role="region" aria-label="ProcessScope">
      <div className="memscope-stats">
        <span className="chip">{stream.total} records</span>
        <span className="chip ok">exit {String(stream.exit_code ?? exit?.exit_code ?? "?")}</span>
        <span className="chip">{String(stream.duration_ms ?? exit?.duration_ms ?? "?")} ms</span>
        <span className="chip">container pid {String(meta?.container_pid ?? "?")}</span>
        {stream.host_pid != null && <span className="chip">host pid {String(stream.host_pid)}</span>}
        {truncated && <span className="chip blocked">samples truncated</span>}
      </div>

      {samples.length > 0 && (
        <section>
          <h4>Observed resource lanes <span className="badge derived">sampled /proc</span>
            <span className="muted"> — {samples.length} samples at a stated {String(meta?.sample_interval_ms ?? "?")} ms interval;
              sampled values, not events or guaranteed peaks</span></h4>
          <svg viewBox={`0 0 ${W} ${H}`} className="prochart" role="img"
               aria-label={`RSS area chart over ${samples.length} samples, max ${maxRss} kB`}>
            <defs>
              <linearGradient id="rssgrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgba(103,232,249,.5)" />
                <stop offset="100%" stopColor="rgba(103,232,249,.02)" />
              </linearGradient>
            </defs>
            {[0.25, 0.5, 0.75].map((g) => (
              <line key={g} x1={pad} x2={W - pad} y1={pad + g * (H - pad * 2)}
                    y2={pad + g * (H - pad * 2)} className="gridline" />
            ))}
            <path d={areaPath} fill="url(#rssgrad)" stroke="none" />
            <polyline fill="none" className="rssline"
                      points={samples.map((s, i) => `${x(i)},${yRss(s.rss_kb ?? 0)}`).join(" ")} />
            <polyline fill="none" className="threadline"
                      points={samples.map((s, i) =>
                        `${x(i)},${H - pad - ((s.threads ?? 0) / maxThreads) * (H - pad * 2)}`).join(" ")} />
            <polyline fill="none" className="fdline"
                      points={samples.map((s, i) =>
                        `${x(i)},${H - pad - ((s.fds ?? 0) / maxFd) * (H - pad * 2)}`).join(" ")} />
            <text x={pad} y={16} className="axislabel">RSS max {maxRss} kB</text>
            <text x={W - pad} y={16} textAnchor="end" className="axislabel">
              threads ≤{maxThreads} · fds ≤{maxFd}
            </text>
            <text x={pad} y={H - 8} className="axislabel">launch</text>
            <text x={W - pad} y={H - 8} textAnchor="end" className="axislabel">
              exit · {String(stream.duration_ms ?? exit?.duration_ms ?? "?")} ms
            </text>
          </svg>
          <div className="prolegend">
            <span><i className="lg rss" /> RSS (kB)</span>
            <span><i className="lg threads" /> threads</span>
            <span><i className="lg fds" /> fds</span>
          </div>
        </section>
      )}

      {children.length > 0 && (
        <section>
          <h4>Observed child processes <span className="badge exact">observed</span></h4>
          <div className="aliaswrap">
            {children.slice(0, 6).map((c, i) => (
              <span key={i} className="alias-chip">
                t≈{String(c.payload.t_ms ?? "?")} ms · pids {(c.payload.pids as number[]).join(", ")}
                <span className="muted"> · {String(c.payload.observed ?? "during run")}</span>
              </span>
            ))}
          </div>
        </section>
      )}

      {exit && "thread_ids" in exit && (
        <section>
          <h4>Thread ids at exit <span className="badge exact">observed</span></h4>
          <p className="muted"><code>{((exit.thread_ids as number[]) ?? []).join(", ")}</code></p>
        </section>
      )}

      <div className="unavailable">
        <span className="glyph">◍</span>
        <div>
          <b>Syscall timeline — not available, by policy.</b> strace/ptrace are disabled in the
          restricted profile (ADR-0007/0008). The lanes above are periodic /proc samples; no
          individual OS events are inferred from them.
        </div>
      </div>

      {meta && (
        <table className="insp-fields tech-only">
          <tbody>
            <tr><td>container pid namespace</td><td><code>{String(meta.container_pid)}</code> (ppid {String(meta.ppid)})</td></tr>
            <tr><td>host-side pid</td><td><code>{stream.host_pid != null ? String(stream.host_pid) : "unavailable (container exited before sampling)"}</code></td></tr>
            {meta.kernel != null && <tr><td>kernel</td><td><code>{String(meta.kernel)}</code></td></tr>}
            <tr><td>sample interval (stated)</td><td><code>{String(meta.sample_interval_ms)} ms</code></td></tr>
            <tr><td>sample cap</td><td><code>{String(meta.sample_cap ?? "—")}</code></td></tr>
          </tbody>
        </table>
      )}

      <details className="tech-only">
        <summary className="muted">Evidence limitations ({stream.limitations.length})</summary>
        <ul className="limits">{stream.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>
      </details>
    </div>
  );
}
