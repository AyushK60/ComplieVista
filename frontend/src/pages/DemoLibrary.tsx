import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DemoEntry, DemoRunResult, demos, errorFixtures } from "../api";

/**
 * Demo Library — a learning gallery over the exact 20-program inventory
 * (5 Python-only, 5 C-only, 5 matched pairs). Organized for choosing by what
 * you want to understand: Explore Python / Explore C / Compare both languages,
 * with concept and difficulty filters. Each card states what the program
 * teaches, which real capabilities it has, its difficulty, and opens into the
 * guided observatory. Error Microscope fixtures are kept outside the 20.
 */

type Lang = "all" | "python" | "c";
const CONCEPT_ICONS: Record<string, string> = {
  recursion: "⑃", pointers: "➚", memory: "◫", optimization: "⚡", sorting: "⇅",
  tokens: "␣", "call stack": "▤", bytecode: "◈", "control flow": "⑂",
};
const DIFF_ORDER: Record<string, number> = { introductory: 0, intermediate: 1, advanced: 2 };

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

/* ——— specimen: a small ink-screen preview, varied but consistent ——— */
function Specimen({ d }: { d: DemoEntry }) {
  const concepts = d.concepts.join(" ").toLowerCase();
  const seed = [...d.id].reduce((a, c) => a + c.charCodeAt(0), 0);
  const id = d.id.replace(/[^A-Z0-9-]/gi, "");
  let art: React.ReactNode;
  if (concepts.includes("recursion") || concepts.includes("call stack")) {
    const w = 2 + (seed % 2);
    art = (
      <svg viewBox="0 0 260 84" className="dcs-svg">
        {[0, 1].slice(0, w).map((i) => (
          <g key={i}>
            <path className="dc-wire" stroke="rgba(226,141,128,.5)" d={`M60 ${14 + i * 6} C 90 ${30 + i * 8}, 90 ${44 + i * 6}, ${62 + i * 74} ${62}`} />
            <rect x={34 + i * 118} y={54} width={52} height={18} rx={5} fill="rgba(226,141,128,.1)" stroke="rgba(226,141,128,.55)" />
            <text x={60 + i * 118} y={67} textAnchor="middle" fontSize="9" fill="#e9efed" fontFamily="var(--font-mono)">f({4 - i * 2})</text>
          </g>
        ))}
        <rect x={34} y={6} width={52} height={18} rx={5} fill="rgba(226,141,128,.16)" stroke="rgba(226,141,128,.7)" />
        <text x={60} y={19} textAnchor="middle" fontSize="9" fill="#e9efed" fontFamily="var(--font-mono)">f({6 + (seed % 3)})</text>
      </svg>
    );
  } else if (concepts.includes("sorting") || concepts.includes("loop") || concepts.includes("array")) {
    const n = 7;
    art = (
      <svg viewBox="0 0 260 84">
        {Array.from({ length: n }, (_, i) => {
          const h = 16 + ((seed * (i + 3)) % 52);
          return <rect key={i} x={16 + i * 34} y={78 - h} width={22} height={h} rx={3}
            fill={i % 2 ? "rgba(111,195,184,.35)" : "rgba(111,195,184,.18)"} stroke="rgba(111,195,184,.6)" />;
        })}
      </svg>
    );
  } else if (concepts.includes("pointer") || concepts.includes("memory") || concepts.includes("heap")) {
    art = (
      <svg viewBox="0 0 260 84">
        <rect x={18} y={30} width={46} height={24} rx={5} fill="rgba(185,168,216,.14)" stroke="rgba(185,168,216,.6)" />
        <text x={41} y={45} textAnchor="middle" fontSize="9" fill="#e9efed" fontFamily="var(--font-mono)">ptr</text>
        <path className="dc-wire" stroke="rgba(185,168,216,.6)" d="M64 42 C 96 42, 96 42, 124 42" />
        <path d="M120 38 L128 42 L120 46" className="dc-wire" stroke="rgba(185,168,216,.6)" />
        <rect x={130} y={22} width={62} height={40} rx={5} fill="rgba(185,168,216,.1)" stroke="rgba(185,168,216,.5)" strokeDasharray="3 2" />
        <text x={161} y={46} textAnchor="middle" fontSize="9" fill="#b1c3c3" fontFamily="var(--font-mono)">0x7f…</text>
        <rect x={206} y={30} width={40} height={24} rx={5} fill="rgba(150,198,139,.12)" stroke="rgba(150,198,139,.55)" />
        <text x={226} y={45} textAnchor="middle" fontSize="9" fill="#e9efed" fontFamily="var(--font-mono)">free</text>
      </svg>
    );
  } else if (concepts.includes("optimization") || concepts.includes("benchmark")) {
    art = (
      <svg viewBox="0 0 260 84">
        {["-O0", "-O1", "-O2"].map((o, i) => (
          <g key={o}>
            <rect x={16} y={12 + i * 24} width={150 - i * 28} height={14} rx={4}
              fill="rgba(230,168,126,.28)" stroke="rgba(230,168,126,.55)" />
            <text x={172 - i * 28 + 8} y={23 + i * 24} fontSize="9" fill="#b1c3c3" fontFamily="var(--font-mono)">{o}</text>
          </g>
        ))}
      </svg>
    );
  } else if (concepts.includes("bytecode") || concepts.includes("token")) {
    const ops = ["LOAD", "STORE", "CALL", "RETURN"];
    art = (
      <svg viewBox="0 0 260 84">
        {ops.map((o, i) => (
          <g key={o}>
            <rect x={16 + (i % 2) * 120} y={12 + Math.floor(i / 2) * 30} width={96} height={20} rx={5}
              fill="rgba(230,168,126,.1)" stroke="rgba(230,168,126,.4)" />
            <text x={64 + (i % 2) * 120} y={26 + Math.floor(i / 2) * 30} textAnchor="middle" fontSize="9"
              fill="#e6a87e" fontFamily="var(--font-mono)">{o} {i}</text>
          </g>
        ))}
      </svg>
    );
  } else {
    // control flow / branching / default: branch arcs
    art = (
      <svg viewBox="0 0 260 84">
        <path className="dc-wire" stroke="rgba(111,195,184,.6)" d="M20 42 H 96" />
        <path className="dc-wire" stroke="rgba(111,195,184,.45)" d="M96 42 C 120 42, 120 20, 144 20 H 200" />
        <path className="dc-wire" stroke="rgba(111,195,184,.45)" d="M96 42 C 120 42, 120 64, 144 64 H 200" />
        <rect x={70} y={32} width={52} height={20} rx={5} fill="rgba(111,195,184,.12)" stroke="rgba(111,195,184,.55)" />
        <text x={96} y={45} textAnchor="middle" fontSize="9" fill="#e9efed" fontFamily="var(--font-mono)">if</text>
        <text x={214} y={23} fontSize="9" fill="#b1c3c3" fontFamily="var(--font-mono)">true</text>
        <text x={214} y={67} fontSize="9" fill="#b1c3c3" fontFamily="var(--font-mono)">else</text>
      </svg>
    );
  }
  return (
    <div className="dc-screen screen on-ink" aria-hidden>
      {art}
      <span className="dcs-caption">{id} · specimen</span>
    </div>
  );
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
  const difficulties = [...new Set(all.map((d) => d.difficulty))].sort((a, b) => (DIFF_ORDER[a] ?? 9) - (DIFF_ORDER[b] ?? 9));

  const filtered = all.filter((d) => {
    if (lang !== "all" && demoLang(d) !== lang) return false;
    if (concept && !d.concepts.includes(concept)) return false;
    if (difficulty && d.difficulty !== difficulty) return false;
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
        navigate(`/workspace?demo=${d.id}&execution=${r.execution_id}&snapshot=${r.snapshot_id}&project=demo-library&target=${r.target_id}&file=${encodeURIComponent(d.primary_file)}${mode === "run" ? "&walkthrough=1" : ""}`);
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
        </div>
        <div className="dl-concepts">
          <span className="dl-diff-lab muted" style={{ fontSize: 11, fontFamily: "var(--font-mono)", alignSelf: "center", marginRight: 2 }}>concept</span>
          {concepts.map((c) => (
            <button key={c} className={`conceptchip ${concept === c ? "active" : ""}`}
                    aria-pressed={concept === c}
                    onClick={() => setConcept(concept === c ? null : c)}>
              {CONCEPT_ICONS[c] ?? ""} {c}
            </button>
          ))}
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

      {groups.map(([label, lede, demos_]) => demos_.length > 0 && (
        <section key={label} className="dl-group">
          <h2>{label} <span className="chip">{demos_.length}</span></h2>
          <p className="dl-grouplede">{lede}</p>
          <div className="dl-grid">
            {demos_.map((d) => (
              <button key={d.id} className="democard panel" onClick={() => setOpenId(d.id)}>
                <Specimen d={d} />
                <div className="dc-body">
                  <div className="dc-top">
                    <span className={`langbadge ${d.group === "C" ? "pair" : demoLang(d)}`}>{demoLang(d)}</span>
                    <code className="dc-id">{d.id}</code>
                    <span className="spacer" />
                    <span className="chip">{d.difficulty}</span>
                  </div>
                  <h3>{d.title}</h3>
                  <p className="dc-teaches"><b>Teaches:</b> {teaches(d)}</p>
                  <div className="dc-concepts">
                    {d.concepts.slice(0, 4).map((c) => <span key={c} className="conceptchip mini">{c}</span>)}
                  </div>
                  <div className="dc-stages" aria-label="available stages">
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
        <p className="muted">No demos match — clear a filter.</p>
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
