import { ObservationChunk } from "../api";

/**
 * M5-E ProcessScope — container-side process evidence: pid namespace identity,
 * /proc samples (RSS/VM/threads/fds at a stated interval), observed child
 * processes, thread ids at exit, launch/exit. Syscall-level tracing is
 * UNSUPPORTED by policy and shown honestly when absent.
 */
export default function ProcessScope({
  stream,
}: {
  stream: (Omit<{ chunks: ObservationChunk[]; limitations: string[]; total: number;
    profile: string; language: string }, "kinds"> &
    { host_pid?: number | null; exit_code?: number | null;
      duration_ms?: number | null }) | null;
}) {
  if (!stream) return <p className="muted">No process evidence recorded.</p>;
  const chunks = stream.chunks;
  const meta = chunks.find((c) => c.payload.kind === "proc_meta")?.payload;
  const samples = chunks.filter((c) => c.payload.kind === "proc_sample")
    .map((c) => c.payload as Record<string, number>);
  const children = chunks.filter((c) => c.payload.kind === "proc_children" && c.payload.pids);
  const exit = chunks.find((c) => c.payload.kind === "proc_exit")?.payload;
  const truncated = chunks.some((c) => c.payload.kind === "meta"
    && c.payload.truncated === true);

  const rssValues = samples.map((s) => s.rss_kb ?? 0);
  const maxRss = Math.max(...rssValues, 1);
  const W = 420, H = 120;

  return (
    <div className="processscope" role="region" aria-label="ProcessScope">
      <p className="muted">
        schema m5.process.v1 · profile {stream.profile} · {stream.total} records ·
        OS: Linux (WSL2 container pid namespace) — not native Windows.
      </p>
      {meta && (
        <table className="grid locals">
          <tbody>
            <tr><td>container pid</td><td>{String(meta.container_pid)}</td></tr>
            <tr><td>parent pid (container ns)</td><td>{String(meta.ppid)}</td></tr>
            <tr><td>host-side pid (runtime)</td>
                <td>{stream.host_pid != null ? String(stream.host_pid)
                     : "unavailable (container exited before sampling)"}</td></tr>
            <tr><td>kernel</td><td>{String(meta.kernel)}</td></tr>
            <tr><td>sample interval</td>
                <td>{String(meta.sample_interval_ms)} ms (stated, not continuous)</td></tr>
          </tbody>
        </table>
      )}
      <p className="replay-banner">
        exit={String(stream.exit_code ?? exit?.exit_code ?? "?")} ·{" "}
        {String(stream.duration_ms ?? exit?.duration_ms ?? "?")}ms elapsed
        {truncated ? " · SAMPLES TRUNCATED" : ""}
      </p>

      {samples.length > 0 && (
        <section aria-label="rss timeline">
          <h4>RSS samples (VmRSS, kB — /proc/self/status)</h4>
          <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img"
               aria-label={`RSS over ${samples.length} samples, max ${maxRss} kB`}
               style={{ maxHeight: 130, border: "1px solid #ddd", background: "#fafafa" }}>
            <polyline
              fill="none" stroke="#4a78a8" strokeWidth={1.5}
              points={samples.map((s, i) => {
                const x = (W * i) / Math.max(samples.length - 1, 1);
                const y = H - 8 - ((s.rss_kb ?? 0) / maxRss) * (H - 20);
                return `${x},${y}`;
              }).join(" ")} />
          </svg>
          <p className="muted">
            {samples.length} samples · interval {String(meta?.sample_interval_ms ?? "?")} ms ·
            max RSS {maxRss} kB · sampled data, not event data
          </p>
        </section>
      )}

      {children.length > 0 && (
        <section aria-label="children">
          <h4>Observed child processes (container pid namespace)</h4>
          <ul>{children.slice(0, 6).map((c, i) => (
            <li key={i} className="muted">
              t≈{String(c.payload.t_ms ?? "?")}ms · pids{" "}
              {(c.payload.pids as number[]).join(", ")} ·{" "}
              {String(c.payload.observed ?? "during run")}
            </li>
          ))}</ul>
        </section>
      )}

      {exit && "thread_ids" in exit && (
        <section aria-label="threads">
          <h4>Thread ids at exit (observed)</h4>
          <p className="muted">
            {(exit.thread_ids as number[]).join(", ")} · {String(exit.samples)} samples
          </p>
        </section>
      )}

      <p className="notice">
        <span className="chip blocked">unavailable</span> Syscall timeline
        (strace/ptrace): UNSUPPORTED by policy in the restricted profile
        (ADR-0007/0008) — not measured, not inferred.
      </p>
      <details>
        <summary className="muted">Evidence limitations</summary>
        <ul>{stream.limitations.map((l, i) => <li key={i} className="muted">{l}</li>)}</ul>
      </details>
    </div>
  );
}
