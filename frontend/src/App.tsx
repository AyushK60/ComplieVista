import { useEffect, useState } from "react";

/**
 * M0 foundation smoke: proves the Windows browser reaches the WSL FastAPI backend
 * and renders GENUINE stage artifacts (token stream, IR excerpt, bytecode counts).
 * No decorative pipeline, no fabricated data: everything shown comes from
 * /api/v1 responses backed by evidence manifests. Premium UI work belongs to M3/M8.
 */

type Health = { status: string; python_version: string; schema_version: string };
type ToolCap = { available: boolean; version: string };
type Capabilities = { tools: Record<string, ToolCap>; modes: Record<string, string>; notes: string[] };
type Analysis = { id: string; language: string; stages: string[]; source_combined_sha256: string };
type StageView = {
  stage: string;
  availability: string;
  counts: Record<string, unknown>;
  limitations: string[];
  items?: Array<{ kind?: string; type?: string; text?: string; line?: number; col?: number }>;
  artifact?: { path: string; sha256: string };
  excerpt?: string;
  truncated?: boolean;
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

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [views, setViews] = useState<StageView[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const h = await fetch("/api/v1/health").then((r) => r.json());
        setHealth(h);
        const c = await fetch("/api/v1/capabilities").then((r) => r.json());
        setCaps(c);
        const a = await fetch("/api/v1/analyses").then((r) => r.json());
        setAnalyses(a);
        const picks: Array<[string, string]> = [
          ["m0-c", "ir"],
          ["m0-python", "tokens"],
        ];
        const vs: StageView[] = [];
        for (const [id, stage] of picks) {
          const v = await fetch(`/api/v1/analyses/${id}/stages/${stage}`).then((r) => r.json());
          vs.push(v);
        }
        setViews(vs);
      } catch (e) {
        setError(String(e));
      }
    })();
  }, []);

  return (
    <main>
      <h1>CompileVista — M0 foundation proof [HMR OK]</h1>
      <p className="muted">
        Thin integration smoke: browser (Windows) → Vite (WSL Node) → FastAPI (WSL) → genuine
        toolchain evidence. Premium observatory UI is M3/M8 scope.
      </p>
      {error && <p className="err">API unreachable: {error}</p>}
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
// M0 watch probe
