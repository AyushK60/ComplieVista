import { useState } from "react";
import { PairSpec, api, experiments, pairs } from "../api";

/**
 * M6-C/M6-E Compare view: two INDEPENDENT language rails synchronized by
 * concept — never by pretending C stages equal Python stages. A paired
 * experiment runs both sides through the real M4 execution pipeline and checks
 * the independently verified expected output. Python has no LLVM O-levels.
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
    return <p className="muted">Loading pair specs…</p>;
  }

  const runPair = async (pair: PairSpec) => {
    setError(null); setResult(null); setStatus("running");
    setSelected(pair);
    try {
      if (!pair.c_source || !pair.py_source) {
        throw new Error("pair sources unavailable");
      }
      const c = await api.createSnapshotFromPaste("c", pair.c_file, pair.c_source);
      const py = await api.createSnapshotFromPaste("python", pair.py_file, pair.py_source);
      const ref = await experiments.create({
        kind: "compare", config: {
          pair_id: pair.id,
          c: { snapshot_id: c.snapshot_id, target_id: c.target_id },
          python: { snapshot_id: py.snapshot_id, target_id: py.target_id },
        }});
      const id = ref.experiment_id ?? "";
      setExpId(id);
      for (let i = 0; i < 300; i++) {
        const e = await experiments.get(id);
        setStatus(e.status);
        if (["COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BLOCKED"].includes(e.status)) {
          setResult((e.stages.find((s) => s.stage === "compare")?.result ??
            {}) as Record<string, unknown>);
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
    <div className="compare" role="region" aria-label="Cross-language compare">
      <h2>Cross-Language Compare</h2>
      <p className="muted">Two independent pipelines (Clang 18.1.3 / CPython 3.12),
        synchronized by concept — the stages are NOT equivalent across languages.
        Expected outputs were verified with host toolchains independently of the
        containers. Python has no LLVM -O levels.</p>
      <div className="pairlist" role="list">
        {specs.map((p) => (
          <div className="pair" role="listitem" key={p.id}>
            <code>{p.id}</code> — {p.concept}{" "}
            <button onClick={() => runPair(p)} disabled={status === "running"}>
              Run paired experiment
            </button>
            <p className="muted">expected: <code>{p.expected_stdout}</code></p>
          </div>
        ))}
      </div>
      {error && <p className="err">{error}</p>}
      {status && status !== "COMPLETED" && <p className="muted">experiment: {status}…</p>}
      {result && selected && (
        <div className="rails">
          {(["c", "python"] as const).map((side) => {
            const s = sides[side] ?? {};
            return (
              <div className="rail" key={side} role="group"
                   aria-label={`${side} rail`}>
                <h3>{side === "c" ? "C rail (Clang 18.1.3)" : "Python rail (CPython 3.12)"}</h3>
                <p className="muted">concept: {selected.concept}</p>
                <p>
                  status {String(s.status ?? "—")} · exit {String(s.exit_code ?? "—")} ·{" "}
                  {String(s.duration_ms ?? "—")} ms{" "}
                  {s.expected_match
                    ? <span className="chip ok">matches expected</span>
                    : <span className="chip blocked">mismatch/absent</span>}
                </p>
                <pre className="excerpt">{String(s.stdout ?? "(no stdout)")}</pre>
                {s.execution_id ? (
                  <p className="muted">measured run: <code>{String(s.execution_id)}</code> —
                    recorded replay, memory and process evidence available in the
                    workspace for this execution id.</p>
                ) : null}
              </div>
            );
          })}
          <p className="muted">
            match: {String(result.match)} — both rails must produce the expected
            output; the languages remain independently implemented (different
            runtimes, different memory models).{expId ? ` experiment ${expId}` : ""}
          </p>
        </div>
      )}
    </div>
  );
}
