import { useEffect, useState } from "react";
import AnalysisPanel from "../components/AnalysisPanel";
import ExecutionPanel from "../components/ExecutionPanel";
import OptimizationLab from "../components/OptimizationLab";
import {
  DemoEntry, DemoRunResult, demos, errorFixtures,
} from "../api";

/**
 * M7 Demo Library — exactly 20 curated real programs with guided stories
 * (Simple/Detailed/Technical, grounded in recorded artifacts), capability
 * matrix, real sandbox runs and the Error Microscope (diagnostic fixtures
 * OUTSIDE the 20 count).
 */
type Story = "simple" | "detailed" | "technical";

export default function DemoLibrary() {
  const [all, setAll] = useState<DemoEntry[] | null>(null);
  const [query, setQuery] = useState("");
  const [langFilter, setLangFilter] = useState<"all" | "python" | "c">("all");
  const [openId, setOpenId] = useState<string | null>(null);
  const [story, setStory] = useState<Story>("simple");
  const [run, setRun] = useState<DemoRunResult | null>(null);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errFixtures, setErrFixtures] = useState<Array<{
    id: string; file: string; language: string; kind: string }> | null>(null);
  const [errDiag, setErrDiag] = useState<Record<string, string>>({});

  useEffect(() => {
    demos.list().then((m) => setAll(m.demos)).catch((e) => setError(String(e)));
    errorFixtures.list().then((f) => setErrFixtures(f.fixtures))
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="err">{error}</p>;
  if (!all || !errFixtures) return <p className="muted">Loading demo library…</p>;

  const open = all.find((d) => d.id === openId);
  const filtered = all.filter((d) => {
    const lang = (d.id.startsWith("PY-") || d.id.endsWith("-PY")) ? "python" : "c";
    if (langFilter !== "all" && lang !== langFilter) return false;
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (d.id + " " + d.title + " " + d.concepts.join(" "))
      .toLowerCase().includes(q);
  });

  const doRun = async (id: string) => {
    setBusy(true); setError(null); setRun(null); setAnalysisId(null);
    try {
      setRun(await demos.run(id));
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(false);
  };
  const doAnalyze = async (id: string) => {
    setBusy(true); setError(null); setRun(null); setAnalysisId(null);
    try {
      setAnalysisId((await demos.analyze(id)).analysis_id);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(false);
  };
  const runErr = async (id: string) => {
    setBusy(true); setError(null);
    try {
      const r = await errorFixtures.run(id);
      setErrDiag((prev) => ({ ...prev, [id]: r.diagnostic ?? "(no diagnostic)" }));
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(false);
  };

  return (
    <div className="demolibrary" role="region" aria-label="Demo Library">
      <h2>Demo Library — 20 real programs</h2>
      <p className="muted">
        5 Python-only · 5 C-only · 5 matched pairs (C + Python). Every demo runs in
        the real restricted containers; guided explanations are grounded in the
        recorded artifacts, not generic claims. Arbitrary pasted source, file
        upload/ZIP and read-only GitHub import remain available in the{" "}
        <a href="/workspace">Source Workspace</a>.
      </p>
      <p className="filters">
        <input placeholder="search id / title / concept…" value={query}
               aria-label="search demos"
               onChange={(e) => setQuery(e.target.value)} />
        {(["all", "python", "c"] as const).map((l) => (
          <button key={l} onClick={() => setLangFilter(l)}
                  aria-pressed={langFilter === l}
                  className={langFilter === l ? "active" : ""}>
            {l}
          </button>
        ))}
      </p>

      {!open && (
        <div className="demogrid" role="list">
          {filtered.map((d) => (
            <div className="democard" role="listitem" key={d.id}>
              <p><code>{d.id}</code> <span className="muted">{d.group}</span>{" "}
                <span className="chip">{d.difficulty}</span></p>
              <p>{d.title}</p>
              <p className="muted">{d.concepts.join(" · ")}</p>
              <button onClick={() => { setOpenId(d.id); setRun(null);
                setAnalysisId(null); setStory("simple"); }}>
                Open
              </button>
            </div>
          ))}
          {filtered.length === 0 && <p className="muted">no demos match.</p>}
        </div>
      )}

      {open && (
        <div className="demodetail" role="region" aria-label={`demo ${open.id}`}>
          <p><button onClick={() => setOpenId(null)}>← back to catalog</button></p>
          <h3><code>{open.id}</code> — {open.title}</h3>
          <p className="muted">
            group {open.group} · {open.difficulty} · {open.concepts.join(" · ")}
          </p>

          <div className="tabs" role="tablist" aria-label="explanation levels">
            {(["simple", "detailed", "technical"] as const).map((s) => (
              <button key={s} role="tab" aria-selected={story === s}
                      className={story === s ? "active" : ""}
                      onClick={() => setStory(s)}>
                {s[0].toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
          <p className="guided">{open.guided[story]}</p>

          <h4>Capability matrix (honest)</h4>
          <table className="grid">
            <tbody>
              {Object.entries(open.capabilities).map(([k, v]) => (
                <tr key={k}><td>{k}</td><td>{v}</td></tr>
              ))}
            </tbody>
          </table>
          <ul className="muted">{open.limits.map((l, i) => <li key={i}>{l}</li>)}</ul>

          <p>
            <button className="primary run" disabled={busy} onClick={() => doRun(open.id)}>
              Run in restricted container
            </button>{" "}
            <button disabled={busy} onClick={() => doAnalyze(open.id)}>
              Analyze (static stages)
            </button>{" "}
            <a href={demos.reportUrl(open.id)} target="_blank" rel="noreferrer">
              sanitized report (JSON)
            </a>
          </p>

          {run && (
            <div className="demorun" role="region" aria-label="demo run result">
              <p className={run.stdout_match ? "replay-banner" : "err"}>
                {run.status} · exit {String(run.exit_code)} ·{" "}
                {run.stdout_match ? "matches expected ✓" : "MISMATCH ✗"}
              </p>
              <details open>
                <summary className="muted">program output vs expected</summary>
                <pre className="excerpt">{run.stdout ?? "(none)"}</pre>
                <p className="muted">expected: <code>{run.expected_stdout}</code></p>
              </details>
              <ExecutionPanel executionId={run.execution_id}
                              onSelectLine={() => { /* demo: no source pane */ }} />
              {open.group !== "A" && (
                <OptimizationLab snapshotId={run.snapshot_id}
                                 targetId={run.target_id}
                                 language={open.id.startsWith("PY") ? "python" : "c"} />
              )}
            </div>
          )}
          {analysisId && (
            <AnalysisPanel analysisId={analysisId} onSelectLine={() => { }} />
          )}
        </div>
      )}

      <h3>Error Microscope (diagnostic fixtures — not counted in the 20)</h3>
      <div className="errfixtures">
        {errFixtures.map((f) => (
          <div className="errfixture" key={f.id}>
            <p><code>{f.id}</code> ({f.kind}, {f.language}){" "}
              <button disabled={busy} onClick={() => runErr(f.id)}>Run</button></p>
            {errDiag[f.id] && <pre className="excerpt">{errDiag[f.id]}</pre>}
          </div>
        ))}
      </div>
    </div>
  );
}
