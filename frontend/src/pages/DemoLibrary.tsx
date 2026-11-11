import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { DemoEntry, DemoRunResult, demos, errorFixtures } from "../api";
import { Button, EmptyState, Skeleton } from "../ui";
import Specimen from "../components/Specimen";
import { loadRecent, recentUrl } from "../lib/recent";
import { prefetch } from "../lib/prefetch";

/**
 * Demo Library — a learning gallery over the exact 20-program inventory
 * (5 Python-only, 5 C-only, 5 matched pairs). Organized for choosing by what
 * you want to understand: Explore Python / Explore C / Compare both languages,
 * with concept and difficulty filters. Each card states what the program
 * teaches, which real capabilities it has, its difficulty, and opens into the
 * guided observatory. Error Microscope fixtures are kept outside the 20.
 */

type Lang = "all" | "python" | "c";
const DIFF_ORDER: Record<string, number> = { introductory: 0, intermediate: 1, advanced: 2 };
/** The catalog uses two vocabularies (the single-language demos say introductory/
 * intermediate/advanced, the matched pairs say very easy … challenging). The UI groups
 * them into the same three tiers; the catalog data itself is not altered. */
const DIFF_TIER: Record<string, string> = {
  "very easy": "introductory", easy: "introductory", introductory: "introductory",
  moderate: "intermediate", intermediate: "intermediate",
  challenging: "advanced", advanced: "advanced",
};
const tier = (d: string) => DIFF_TIER[d] ?? d;
/** concepts used by only one demo are tucked behind a toggle to keep the filter row scannable */
const MIN_SHARED_CONCEPT = 2;

function demoLang(d: DemoEntry): Lang {
  return (d.id.startsWith("PY-") || d.id.endsWith("-PY")) ? "python" : "c";
}

/** Short honest stage chips derived from the demo's real capability matrix. */
function stageChips(d: DemoEntry): string[] {
  const caps = d.capabilities ?? {};
  const out: string[] = [];
  if (/^AVAILABLE|^PARTIAL/.test(caps.analysis ?? "")) out.push("tokens", "AST", demoLang(d) === "c" ? "IR" : "bytecode");
  if (/^AVAILABLE|^PARTIAL/.test(caps.execution ?? "")) out.push("run");
  if (/^AVAILABLE|^PARTIAL/.test(caps.trace ?? "")) out.push("trace replay");
  if (/^AVAILABLE|^PARTIAL/.test(caps.memory ?? "")) out.push("memory");
  if (/^AVAILABLE|^PARTIAL/.test(caps.process ?? "")) out.push("process");
  if (/^AVAILABLE|^PARTIAL/.test(caps.optimization ?? "")) out.push("optimization");
  return out;
}

function teaches(d: DemoEntry): string {
  const s = d.guided.simple.split(/(?<=\.)\s/)[0] ?? d.guided.simple;
  return s.length > 150 ? s.slice(0, 147) + "…" : s;
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
  const [difficulty, setDifficulty] = useState<string | null>(null);
  const [showAllConcepts, setShowAllConcepts] = useState(false);
  const [recent] = useState(() => loadRecent().slice(0, 3));
  // The open demo lives in the URL (/demos/:demoId) so it can be shared and the
  // browser back button returns to the gallery.
  const { demoId } = useParams();
  const openId = demoId ?? null;
  const setOpenId = (id: string | null) => navigate(id ? `/demos/${encodeURIComponent(id)}` : "/demos");
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
  const conceptCount = new Map<string, number>();
  for (const d of all) for (const c of d.concepts) conceptCount.set(c, (conceptCount.get(c) ?? 0) + 1);
  const concepts = [...conceptCount.keys()].sort();
  const sharedConcepts = concepts.filter((c) => (conceptCount.get(c) ?? 0) >= MIN_SHARED_CONCEPT || c === concept);
  const shownConcepts = showAllConcepts ? concepts : sharedConcepts;
  const difficulties = [...new Set(all.map((d) => tier(d.difficulty)))].sort((a, b) => (DIFF_ORDER[a] ?? 9) - (DIFF_ORDER[b] ?? 9));

  const filtered = all.filter((d) => {
    if (lang !== "all" && demoLang(d) !== lang) return false;
    if (concept && !d.concepts.includes(concept)) return false;
    if (difficulty && tier(d.difficulty) !== difficulty) return false;
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (d.id + " " + d.title + " " + d.concepts.join(" ")).toLowerCase().includes(q);
  });

  const groups: Array<[string, string, DemoEntry[]]> = [
    ["Explore Python", "Five programs interpreted by CPython 3.12 — from fundamentals to recursion, closures and the runtime itself.", filtered.filter((d) => demoLang(d) === "python" && d.group === "A")],
    ["Explore C", "Five programs compiled with Clang/LLVM 18 — memory you manage yourself, optimization you can watch happen.", filtered.filter((d) => demoLang(d) === "c" && d.group === "B")],
    ["Compare both languages", "Matched pairs: the same problem taken down both pipelines, each stage synchronized by concept — never pretended equivalent.", filtered.filter((d) => d.group === "C")],
  ];

  const launch = async (d: DemoEntry, mode: "analyze" | "run" | "watch") => {
    setBusy(d.id + mode);
    try {
      if (mode === "analyze") {
        const r = await demos.analyze(d.id);
        const snapPart = r.snapshot_id ? `&snapshot=${r.snapshot_id}&project=demo-library` : "";
        navigate(`/workspace?demo=${d.id}&analysis=${r.analysis_id}${snapPart}&file=${encodeURIComponent(d.primary_file)}`);
      } else {
        const r: DemoRunResult = await demos.run(d.id);
        navigate(`/workspace?demo=${d.id}&execution=${r.execution_id}&snapshot=${r.snapshot_id}&project=demo-library&target=${r.target_id}&file=${encodeURIComponent(d.primary_file)}${mode === "watch" ? "&walkthrough=1" : ""}`);
      }
    } catch (e) {
      setCatalog((c) => ({ ...c, error: e instanceof Error ? e.message : String(e) }));
    }
    setBusy(null);
  };

  const open = all.find((d) => d.id === openId) ?? null;

  // scroll position on open, back and forward is handled once, in AppShell

  if (openId && !open && !catalog.loading && catalog.demos) {
    return (
      <main className="demolib">
        <div className="demo-detail">
          <h1>No demo called “{openId}”</h1>
          <p className="muted">The Demo Library has {all.length} programs. <Link to="/demos">Browse them all →</Link></p>
        </div>
      </main>
    );
  }

  if (open) {
    return (
      <main className="demolib">
        <div className="demo-detail">
          <button className="btn ghost" onClick={() => setOpenId(null)}>← back to the gallery</button>
          <div className="dd-head">
            <span className={`langbadge ${demoLang(open)}`}>{demoLang(open)}</span>
            <h1>{open.title}</h1>
            <span className="chip">{tier(open.difficulty)}</span>
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
                    onClick={() => launch(open, "watch")}>
              {busy === open.id + "watch" ? <><span className="spinner" /> running…</> : "▶ Watch This Program Work"}
            </button>
            <button className="btn big" disabled={!!busy}
                    onClick={() => launch(open, "run")}>
              {busy === open.id + "run" ? <><span className="spinner" /> running…</> : "Run (observatory)"}
            </button>
            <a className="btn ghost" href={demos.reportUrl(open.id)} target="_blank" rel="noreferrer">
              sanitized report (JSON)
            </a>
          </div>
          <p className="muted dd-actionhelp">
            <strong>Explore</strong> shows the compilation stages — nothing runs.{" "}
            <strong>Watch</strong> runs it once in a sandbox, then replays it step by step.{" "}
            <strong>Run</strong> opens the full execution, memory and process observatory.
          </p>

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
        <h1>Twenty real programs. What do you want to understand?</h1>
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
          <span className="muted dl-count" aria-live="polite">{filtered.length} of {all.length} programs</span>
        </div>
        <div className="dl-concepts">
          <span className="dl-diff-lab muted" style={{ fontSize: 11, fontFamily: "var(--font-mono)", alignSelf: "center", marginRight: 2 }}>concept</span>
          {shownConcepts.map((c) => (
            <button key={c} className={`conceptchip ${concept === c ? "active" : ""}`}
                    aria-pressed={concept === c}
                    onClick={() => setConcept(concept === c ? null : c)}>
              {c}
            </button>
          ))}
          {concepts.length > sharedConcepts.length && (
            <button className="conceptchip more" aria-expanded={showAllConcepts}
                    onClick={() => setShowAllConcepts((v) => !v)}>
              {showAllConcepts ? "show fewer" : `+ ${concepts.length - sharedConcepts.length} more`}
            </button>
          )}
        </div>
        <div className="dl-difficulty">
          <span className="lab">difficulty</span>
          <button className={`conceptchip ${difficulty === null ? "active" : ""}`} aria-pressed={difficulty === null}
                  onClick={() => setDifficulty(null)}>all</button>
          {difficulties.map((df) => (
            <button key={df} className={`conceptchip ${difficulty === df ? "active" : ""}`}
                    aria-pressed={difficulty === df}
                    onClick={() => setDifficulty(difficulty === df ? null : df)}>{df}</button>
          ))}
        </div>
      </div>

      {recent.length > 0 && !catalog.loading && (
        <section className="dl-recent" aria-label="recent sessions">
          <p className="label">Pick up where you left off</p>
          <ul>
            {recent.map((r) => (
              <li key={r.key}>
                <a href={recentUrl(r)}><b>{r.title}</b><span className="chip">{r.language === "c" ? "C" : "Python"}</span></a>
              </li>
            ))}
          </ul>
        </section>
      )}

      {catalog.loading && !catalog.demos && <Skeleton rows={6} label="Loading demo catalog" />}
      {!catalog.loading && catalog.error && !catalog.demos && (
        <p className="err" role="alert">
          The demo catalog could not be loaded: {catalog.error}{" "}
          <button className="btn" aria-label="Retry loading the demo catalog" onClick={() => setReloadTick((t) => t + 1)}>Retry</button>
        </p>
      )}
      {catalog.error && catalog.demos && (
        <p className="err" role="alert">
          Catalog refresh failed (showing previously loaded data): {catalog.error}{" "}
          <button className="btn" aria-label="Retry loading the demo catalog" onClick={() => setReloadTick((t) => t + 1)}>Retry</button>
        </p>
      )}

      {groups.map(([label, lede, demos_]) => demos_.length > 0 && (
        <section key={label} className="dl-group">
          <h2>{label} <span className="chip">{demos_.length}</span></h2>
          <p className="dl-grouplede">{lede}</p>
          <div className="dl-grid">
            {demos_.map((d) => (
              <button key={d.id} className="democard panel" onClick={() => setOpenId(d.id)}
                      onMouseEnter={() => prefetch("/workspace")} onFocus={() => prefetch("/workspace")}>
                <Specimen d={d} />
                <div className="dc-body">
                  <div className="dc-top">
                    <span className={`langbadge ${d.group === "C" ? "pair" : demoLang(d)}`}>{demoLang(d)}</span>
                    <code className="dc-id">{d.id}</code>
                    <span className="spacer" />
                    <span className="chip">{tier(d.difficulty)}</span>
                  </div>
                  <h3>{d.title}</h3>
                  <p className="dc-teaches"><b>Teaches:</b> {teaches(d)}</p>
                  <div className="dc-concepts">
                    {d.concepts.slice(0, 4).map((c) => <span key={c} className="conceptchip mini">{c}</span>)}
                  </div>
                  <div className="dc-stages tech-only" aria-label="available stages">
                    {stageChips(d).slice(0, 7).map((s) => <span key={s} className="st">{s}</span>)}
                  </div>
                  <span className="dc-open">Explore →</span>
                </div>
              </button>
            ))}
          </div>
        </section>
      ))}
      {!catalog.loading && catalog.demos && filtered.length === 0 && (
        <EmptyState icon="search" title="No demos match those filters"
          action={<Button onClick={() => { setQuery(""); setLang("all"); setConcept(null); setDifficulty(null); }}>Clear filters</Button>}>
          Try a broader search, or clear the concept and difficulty filters.</EmptyState>
      )}

      <section className="dl-errors">
        <h2>Error Microscope <span className="muted">— real diagnostic fixtures, not part of the 20</span></h2>
        <p className="muted">Genuine clang/CPython diagnostics: syntax, semantic, link and runtime errors. Each card shows
          <b> where in the journey the error is detected</b> — before the program ever runs, or during it.</p>
        <div className="errgrid">
          {(fixtures.data ?? []).map((f) => {
            const phase = f.kind === "runtime"
              ? { label: "detected during execution", cls: "runtime" }
              : f.kind === "link"
                ? { label: "detected at link time (after compilation)", cls: "link" }
                : { label: "detected before execution (compiler front-end)", cls: "compile" };
            return (
              <div key={f.id} className="errcard panel">
                <div className="fc-head">
                  <span className={`badge ${f.kind === "runtime" || f.kind === "link" ? "blocked" : "partial"}`}>{f.kind}</span>
                  <code>{f.id}</code>
                  <span className="chip">{f.language}</span>
                  <span className="spacer" />
                  <span className={`badge ${phase.cls === "compile" ? "derived" : "blocked"}`}>{phase.label}</span>
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
            );
          })}
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
