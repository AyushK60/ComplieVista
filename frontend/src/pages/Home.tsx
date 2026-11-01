import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AnalysisSummary, ApiError, api, Capabilities, Health } from "../api";

/** Home page: the M0 toolchain proof, kept intact as an M1 regression surface. */
type StageView = {
  stage: string;
  availability: string;
  counts: Record<string, unknown>;
  limitations: string[];
  items?: Array<{ kind?: string; type?: string; text?: string }>;
  artifact?: { path: string; sha256: string };
  excerpt?: string;
};

function Chip({ label, state }: { label: string; state: string }) {
  const cls =
    state === "AVAILABLE" ? "chip ok" : state === "BLOCKED" || state === "UNSUPPORTED" ? "chip blocked" : "chip partial";
  return (
    <span className={cls}>
      {label}: {state}
    </span>
  );
}

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [views, setViews] = useState<StageView[]>([]);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setHealth(await api.health());
        setCaps(await api.capabilities());
        setAnalyses(await api.analyses());
        const vs: StageView[] = [];
        for (const [id, stage] of [["m0-c", "ir"], ["m0-python", "tokens"]] as const) {
          vs.push(await fetch(`/api/v1/analyses/${id}/stages/${stage}`).then((r) => r.json()));
        }
        setViews(vs);
      } catch (e) {
        setError(e instanceof ApiError ? e.body : { code: "CLIENT", message: String(e) });
      }
    })();
  }, []);

  return (
    <main>
      <nav className="topnav">
        <strong>CompileVista</strong>
        <Link to="/">Home</Link>
        <Link to="/workspace">Source Workspace</Link>
        <Link to="/compare">Compare</Link>
        <Link to="/demos">Demo Library</Link>
      </nav>
      <h1>CompileVista — toolchain proof (M0)</h1>
      <p className="muted">
        Browser (Windows) → Vite (WSL Node) → FastAPI (WSL) → genuine toolchain evidence.
        The interactive source workspace lives in the <Link to="/workspace">Source Workspace</Link>
        <Link to="/compare">Compare</Link>
        <Link to="/demos">Demo Library</Link>.
      </p>
      {error && <p className="err">API unreachable: {error.code}: {error.message}</p>}
      {health && (
        <section>
          <h2>Backend health</h2>
          <p>
            status={health.status} · python={health.python_version} · schema={health.schema_version}
          </p>
        </section>
      )}
      {caps && (
        <section>
          <h2>Capabilities (probed in WSL)</h2>
          <p>
            {Object.entries(caps.tools).map(([k, v]) => (
              <span key={k} className={v.available ? "chip ok" : "chip blocked"}>
                {k} {v.available ? v.version.split(" ").slice(-1)[0] : "unavailable"}
              </span>
            ))}
          </p>
          <p>
            {Object.entries(caps.modes).map(([k, v]) => (
              <Chip key={k} label={k} state={v} />
            ))}
          </p>
        </section>
      )}
      {analyses.length > 0 && (
        <section>
          <h2>Registered analyses</h2>
          {analyses.map((a) => (
            <p key={a.id}>
              <strong>{a.id}</strong> ({a.language}) · {a.stages.length} stages · snapshot{" "}
              <code>{a.source_combined_sha256.slice(0, 16)}…</code>
            </p>
          ))}
        </section>
      )}
      {views.map((v, i) => (
        <section key={i}>
          <h2>
            Stage view: {v.stage} <Chip label="availability" state={v.availability} />
          </h2>
          {v.items && (
            <div className="tokenRibbon">
              {v.items.slice(0, 48).map((t, j) => (
                <span key={j} className="token" title={t.kind ?? t.type}>
                  {(t.text ?? t.kind ?? "").slice(0, 24)}
                </span>
              ))}
              {(v.items.length ?? 0) > 48 && <span className="muted"> …</span>}
            </div>
          )}
          {v.excerpt && <pre className="excerpt">{v.excerpt.slice(0, 900)}</pre>}
          <p className="muted">
            counts: {JSON.stringify(v.counts)} · artifact <code>{v.artifact?.path}</code> ·{" "}
            <code>{v.artifact?.sha256.slice(0, 16)}…</code>
          </p>
          {v.limitations.length > 0 && (
            <ul className="limits">
              {v.limitations.map((l, j) => (
                <li key={j}>{l}</li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </main>
  );
}
