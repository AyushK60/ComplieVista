import { useState } from "react";
import { PairSpec, api, experiments, pairs } from "../api";

/**
 * M8 Compare — two INDEPENDENT language rails synchronized by concept, never by
 * pretending C stages equal Python stages. A paired experiment runs both sides
 * through the real M4 execution pipeline and checks the verified expected
 * output. Python has no LLVM O-levels; the runtimes are never called equivalent.
 */
export default function Compare() {
  const [specs, setSpecs] = useState<PairSpec[] | null>(null);
  const [selected, setSelected] = useState<PairSpec | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [expId, setExpId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (specs === null) {
    pairs.list().then((p) => setSpecs(p.pairs)).catch((e) => setError(String(e)));
    return <main className="compare"><p className="muted"><span className="spinner" /> loading pair specs…</p></main>;
  }

  const runPair = async (pair: PairSpec) => {
    setError(null); setResult(null); setStatus("running");
    setSelected(pair);
    try {
      if (!pair.c_source || !pair.py_source) throw new Error("pair sources unavailable");
      const c = await api.createSnapshotFromPaste("c", pair.c_file, pair.c_source);
      const py = await api.createSnapshotFromPaste("python", pair.py_file, pair.py_source);
      const ref = await experiments.create({
        kind: "compare", config: {
          pair_id: pair.id,
          c: { snapshot_id: c.snapshot_id, target_id: c.target_id },
          python: { snapshot_id: py.snapshot_id, target_id: py.target_id },
        },
      });
      const id = ref.experiment_id ?? "";
      setExpId(id);
      for (let i = 0; i < 300; i++) {
        const e = await experiments.get(id);
        setStatus(e.status);
        if (["COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BLOCKED"].includes(e.status)) {
          setResult((e.stages.find((s) => s.stage === "compare")?.result ?? {}) as Record<string, unknown>);
          return;
        }
        await new Promise((r) => setTimeout(r, 1000));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStatus(null);
    }
  };

  const sides = (result?.sides ?? {}) as Record<string, Record<string, unknown>>;

  return (
    <main className="compare">
      <div className="cmp-head">
        <p className="dl-eyebrow">Cross-Language Compare</p>
        <h1>The same idea, two machines.</h1>
        <p className="muted">
          Two independent pipelines (Clang 18.1.3 / CPython 3.12), synchronized by concept —
          the stages are <b>not</b> equivalent across languages. Expected outputs were verified
          with host toolchains independently of the containers. Python has no LLVM -O levels.
        </p>
      </div>

      <div className="cmp-pairs">
        {specs.map((p) => (
          <button key={p.id} className={"paircard panel" + (selected?.id === p.id ? " active" : "")}
                  onClick={() => runPair(p)} disabled={status === "running"}>
            <code>{p.id}</code>
            <h3>{p.concept}</h3>
            <p className="muted">expected output: <code>{p.expected_stdout}</code></p>
            <span className="dc-open">{status === "running" && selected?.id === p.id ? "running…" : "Run both pipelines →"}</span>
          </button>
        ))}
      </div>

      {error && <p className="err" role="alert">{error}</p>}
      {status && status !== "COMPLETED" && (
        <p className="notice"><span className="spinner" /> experiment: {status}…</p>
      )}

      {result && selected && (
        <div className="cmp-rails">
          <p className={"cmp-verdict " + (result.match ? "ok" : "err")}>
            {result.match ? "✓ both rails produced the expected output" : "✗ mismatch — inspect the rails"}
            {expId ? <span className="muted"> · experiment {expId}</span> : null}
          </p>
          <div className="cmp-grid">
            {(["c", "python"] as const).map((side) => {
              const s = sides[side] ?? {};
              return (
                <div className={"rail panel " + side} key={side} role="group" aria-label={`${side} rail`}>
                  <div className="rail-h">
                    <span className={`langbadge ${side === "c" ? "c" : "python"}`}>{side}</span>
                    <h3>{side === "c" ? "Clang 18.1.3 pipeline" : "CPython 3.12 pipeline"}</h3>
                    <span className="spacer" />
                    {s.expected_match
                      ? <span className="badge ok">matches expected</span>
                      : <span className="badge blocked">mismatch/absent</span>}
                  </div>
                  <div className="rail-stats">
                    <span className="chip">status {String(s.status ?? "—")}</span>
                    <span className="chip">exit {String(s.exit_code ?? "—")}</span>
                    <span className="chip">{String(s.duration_ms ?? "—")} ms container wall</span>
                  </div>
                  <pre className="excerpt">{String(s.stdout ?? "(no stdout)")}</pre>
                  <p className="muted rail-note">
                    Container wall time includes runtime startup — <b>not comparable</b> to
                    OptimizationLab benchmark medians.
                    {s.execution_id ? <> Measured run <code>{String(s.execution_id)}</code> —
                      open it in the workspace for trace, memory and process evidence.</> : null}
                  </p>
                </div>
              );
            })}
          </div>
          <p className="muted">
            Both rails must produce the expected output for a match — but the languages remain
            independently implemented: different runtimes, different memory models, different
            compilation stories.
          </p>
        </div>
      )}
    </main>
  );
}
