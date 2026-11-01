import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DemoEntry, DemoRunResult, demos, errorFixtures } from "../api";

/**
 * M8 Demo Library — a searchable learning gallery over the exact 20-program
 * inventory (5 Python-only, 5 C-only, 5 matched pairs). Grouped by language
 * family, tagged by concept and difficulty; each program opens as a guided
 * journey in the observatory. Error Microscope fixtures are kept outside the 20.
 */

type Lang = "all" | "python" | "c";
const CONCEPT_ICONS: Record<string, string> = {
  recursion: "⑃", pointers: "➚", memory: "◫", optimization: "⚡", sorting: "⇅",
  tokens: "␣", "call stack": "▤", bytecode: "◈", "control flow": "⑂", pointers_: "➚",
};

function demoLang(d: DemoEntry): Lang {
  return (d.id.startsWith("PY-") || d.id.endsWith("-PY")) ? "python" : "c";
}
function pairOf(d: DemoEntry): string | null {
  return d.group === "C" ? d.id.split("-").slice(0, 2).join("-") : null;
}

export default function DemoLibrary() {
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState<{ demos: DemoEntry[] | null; error: string | null; loading: boolean }>(
    { demos: null, error: null, loading: true });
  const [fixtures, setFixtures] = useState<{ data: Array<{ id: string; file: string; language: string; kind: string }> | null; error: string | null; loading: boolean }>(
    { data: null, error: null, loading: true });
  const [reloadTick, setReloadTick] = useState(0);
  const [query, setQuery] = useState("");
  const [lang, setLang] = useState<Lang>("all");
  const [concept, setConcept] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [errDiag, setErrDiag] = useState<Record<string, string>>({});

  useEffect(() => {
    let alive = true;
    setCatalog((c) => ({ ...c, loading: true, error: null }));
    setFixtures((f) => ({ ...f, loading: true, error: null }));
    demos.list()
      .then((m) => { if (alive) setCatalog({ demos: m.demos, error: null, loading: false }); })
      .catch((e) => { if (alive) setCatalog((c) => ({ ...c, loading: false, error: String(e) })); });
    errorFixtures.list()
      .then((f) => { if (alive) setFixtures({ data: f.fixtures, error: null, loading: false }); })
      .catch((e) => { if (alive) setFixtures((f) => ({ ...f, loading: false, error: String(e) })); });
    return () => { alive = false; };
  }, [reloadTick]);

  const all = catalog.demos ?? [];
  const concepts = [...new Set(all.flatMap((d) => d.concepts))].sort();

  const filtered = all.filter((d) => {
    if (lang !== "all" && demoLang(d) !== lang) return false;
    if (concept && !d.concepts.includes(concept)) return false;
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (d.id + " " + d.title + " " + d.concepts.join(" ")).toLowerCase().includes(q);
  });

  const groups: Array<[string, DemoEntry[]]> = [
    ["Python programs — interpreted by CPython 3.12", filtered.filter((d) => demoLang(d) === "python" && d.group === "A")],
    ["C programs — compiled with Clang/LLVM 18", filtered.filter((d) => demoLang(d) === "c" && d.group === "B")],
    ["Matched pairs — the same concept in both worlds", filtered.filter((d) => d.group === "C")],
  ];

  const launch = async (d: DemoEntry, mode: "analyze" | "run") => {
    setBusy(d.id + mode);
    try {
      if (mode === "analyze") {
        const r = await demos.analyze(d.id);
        navigate(`/workspace?demo=${d.id}&analysis=${r.analysis_id}&file=${encodeURIComponent(d.primary_file)}`);
      } else {
        const r: DemoRunResult = await demos.run(d.id);
        // run first; the student can click Analyze afterwards in the observatory
        navigate(`/workspace?demo=${d.id}&execution=${r.execution_id}&snapshot=${r.snapshot_id}&target=${r.target_id}&file=${encodeURIComponent(d.primary_file)}`);
      }
    } catch (e) {
      setCatalog((c) => ({ ...c, error: e instanceof Error ? e.message : String(e) }));
    }
    setBusy(null);
  };

  const open = all.find((d) => d.id === openId) ?? null;

  if (open) {
    return (
      <main className="demolib">
        <div className="demo-detail">
          <button className="btn ghost" onClick={() => setOpenId(null)}>← back to the gallery</button>
          <div className="dd-head">
            <span className={`langbadge ${demoLang(open)}`}>{demoLang(open)}</span>
            <h1>{open.title}</h1>
            <span className="chip">{open.difficulty}</span>
          </div>
          <p className="muted">{open.id} · {open.concepts.join(" · ")}</p>

          <div className="dd-guided">
            {(["simple", "detailed", "technical"] as const).map((s, i) => (
              <div key={s} className={`dd-story ${s}`}>
                <h4>{["The idea", "How it works", "Under the hood"][i]}</h4>
                <p>{open.guided[s]}</p>
              </div>
            ))}
          </div>

          <div className="dd-actions">
            <button className="btn primary big" disabled={!!busy}
                    onClick={() => launch(open, "analyze")}>
              {busy === open.id + "analyze" ? <><span className="spinner" /> analyzing…</> : "Explore this program →"}
            </button>
            <button className="btn run big" disabled={!!busy}
                    onClick={() => launch(open, "run")}>
              {busy === open.id + "run" ? <><span className="spinner" /> running…</> : "Run & replay execution"}
            </button>
            <a className="btn ghost" href={demos.reportUrl(open.id)} target="_blank" rel="noreferrer">
              sanitized report (JSON)
            </a>
          </div>

          <div className="dd-meta">
            <div className="dd-caps panel">
              <div className="panel-h">Capability matrix (honest)</div>
              <table className="insp-fields">
                <tbody>
                  {Object.entries(open.capabilities).map(([k, v]) => (
                    <tr key={k}>
                      <td>{k}</td>
                      <td><span className={`badge ${String(v).startsWith("AVAILABLE") || String(v) === "FULL" ? "ok" : String(v) === "UNSUPPORTED" || String(v) === "BLOCKED" ? "blocked" : "partial"}`}>{String(v)}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="dd-limits panel">
              <div className="panel-h">What this demo can and cannot show</div>
              <ul className="limits" style={{ padding: "12px 18px" }}>
                {open.limits.map((l, i) => <li key={i}>{l}</li>)}
              </ul>
              <p className="muted" style={{ padding: "0 18px 14px" }}>
                Files: {open.files.map((f) => f.path).join(", ")}
                {open.tus.length > 1 ? ` · ${open.tus.length} translation units` : ""}
              </p>
            </div>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="demolib">
      <div className="dl-head">
        <p className="dl-eyebrow">Demo Library</p>
        <h1>Twenty real programs, one observatory.</h1>
        <p className="muted">
          5 Python-only · 5 C-only · 5 matched pairs. Every demo runs through the real
          restricted containers; every view is grounded in recorded artifacts. Prefer your own
          code? Go to the <a href="/workspace">Source Workspace</a>.
        </p>
        <div className="dl-filters">
          <input className="input" placeholder="search title, id or concept…" value={query}
                 aria-label="search demos" onChange={(e) => setQuery(e.target.value)} />
          <div className="dl-langfilter" role="group" aria-label="language filter">
            {(["all", "python", "c"] as Lang[]).map((l) => (
              <button key={l} aria-pressed={lang === l}
                      className={lang === l ? "active" : ""}
                      onClick={() => setLang(l)}>{l}</button>
            ))}
          </div>
        </div>
        <div className="dl-concepts">
          {concepts.map((c) => (
            <button key={c} className={`conceptchip ${concept === c ? "active" : ""}`}
                    aria-pressed={concept === c}
                    onClick={() => setConcept(concept === c ? null : c)}>
              {CONCEPT_ICONS[c] ?? ""} {c}
            </button>
          ))}
        </div>
      </div>

      {catalog.loading && !catalog.demos && <p className="muted" role="status">Loading demo catalog…</p>}
      {!catalog.loading && catalog.error && !catalog.demos && (
        <p className="err" role="alert">
          The demo catalog could not be loaded: {catalog.error}{" "}
          <button className="btn" onClick={() => setReloadTick((t) => t + 1)}>Retry</button>
        </p>
      )}
      {catalog.error && catalog.demos && (
        <p className="err" role="alert">
          Catalog refresh failed (showing previously loaded data): {catalog.error}{" "}
          <button className="btn" onClick={() => setReloadTick((t) => t + 1)}>Retry</button>
        </p>
      )}

      {groups.map(([label, demos_]) => demos_.length > 0 && (
        <section key={label} className="dl-group">
          <h2>{label} <span className="chip">{demos_.length}</span></h2>
          <div className="dl-grid">
            {demos_.map((d) => (
              <button key={d.id} className="democard panel" onClick={() => setOpenId(d.id)}>
                <div className="dc-top">
                  <span className={`langbadge ${demoLang(d)}`}>{demoLang(d)}</span>
                  <code className="dc-id">{d.id}</code>
                  <span className="spacer" />
                  <span className="chip">{d.difficulty}</span>
                </div>
                <h3>{d.title}</h3>
                <div className="dc-concepts">
                  {d.concepts.slice(0, 4).map((c) => <span key={c} className="conceptchip mini">{c}</span>)}
                </div>
                <p className="dc-story">{d.guided.simple.slice(0, 130)}…</p>
                <span className="dc-open">Explore →</span>
              </button>
            ))}
          </div>
        </section>
      ))}
      {!catalog.loading && catalog.demos && filtered.length === 0 && (
        <p className="muted">No demos match — clear a filter.</p>
      )}

      <section className="dl-errors">
        <h2>Error Microscope <span className="muted">— real diagnostic fixtures, not part of the 20</span></h2>
        <p className="muted">Genuine clang/CPython diagnostics: syntax, semantic, link and runtime errors. See exactly how each tool explains a broken program.</p>
        <div className="errgrid">
          {(fixtures.data ?? []).map((f) => (
            <div key={f.id} className="errcard panel">
              <div className="fc-head">
                <span className={`badge ${f.kind === "runtime" || f.kind === "link" ? "blocked" : "partial"}`}>{f.kind}</span>
                <code>{f.id}</code>
                <span className="chip">{f.language}</span>
              </div>
              <button className="btn" disabled={busy === f.id} onClick={async () => {
                setBusy(f.id);
                try {
                  const r = await errorFixtures.run(f.id);
                  setErrDiag((prev) => ({ ...prev, [f.id]: r.diagnostic ?? "(no diagnostic)" }));
                } catch (e) {
                  setErrDiag((prev) => ({ ...prev, [f.id]: String(e) }));
                }
                setBusy(null);
              }}>Reproduce the diagnostic</button>
              {errDiag[f.id] && <pre className="excerpt">{errDiag[f.id]}</pre>}
            </div>
          ))}
          {!fixtures.loading && fixtures.error && !fixtures.data && (
            <p className="err" role="alert">
              Error fixtures could not be loaded: {fixtures.error}{" "}
              <button className="btn" onClick={() => setReloadTick((t) => t + 1)}>Retry</button>
            </p>
          )}
        </div>
      </section>
    </main>
  );
}
