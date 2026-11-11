import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, demos, executions, StageData } from "../../api";
import { nodeCategory } from "../graphModel";
import { Icon } from "../../ui";

/**
 * Landing hero. Left: the idea in one sentence. Right: the journey window, a paper bezel around
 * an ink screen that walks the whole pipeline of a real program, phase by phase:
 *   source -> tokens -> syntax tree -> bytecode -> a recorded run.
 * Every cell is the tools' own output (CPython tokenize / ast / dis, and a sandboxed sys.settrace
 * run) keyed by source line, so the line being highlighted on the left is the line whose tokens,
 * nodes, bytecode or execution step are shown on the right. Nothing is drawn by hand. It plays
 * on its own, pauses when you touch it, and the rail lets you jump to any phase. If the backend
 * is unreachable the window says so instead of showing anything made up.
 */
const DEMO = "PY-01";
const CACHE_A = "cv.hero.analysis.v3";
const CACHE_X = "cv.hero.exec.v1";
const SKIP_TOK = new Set(["NEWLINE", "NL", "INDENT", "DEDENT", "ENDMARKER", "ENCODING", "COMMENT"]);
const PHASES = [
  { id: "source", label: "Source", short: "Source", tool: "file snapshot", stage: "tokens" },
  { id: "tokens", label: "Tokens", short: "Tokens", tool: "CPython tokenize", stage: "tokens" },
  { id: "ast", label: "Syntax tree", short: "Syntax", tool: "ast.parse", stage: "ast" },
  { id: "bytecode", label: "Bytecode", short: "Bytecode", tool: "dis", stage: "bytecode" },
  { id: "run", label: "Execution", short: "Execution", tool: "sys.settrace in a sandbox", stage: "" },
] as const;
const PHASE_MS = [4200, 5600, 5600, 5600, 7200];

type Tok = { kind: string; text: string; line: number };
type AstNode = { id: string; parent: string | null; kind: string; line: number | null; name: string | null };
type Ins = { code_object: string; offset: number; opname: string; argval: string; starts_line: number | null };
type Handle = { analysisId: string; snapshotId?: string };
type Step = { text: string; line: number | null; kind: "call" | "line" | "return" };
type Run = { stdout: string; steps: Step[]; total: number; exit: number | null; executionId: string } | null;
type Data = {
  state: "loading" | "ready" | "failed";
  handle: Handle | null;
  source: string[]; first: number; fn: string; fileLines: number; fileSha?: string;
  tokens: Tok[]; ast: AstNode[]; bytecode: Ins[]; tokSha?: string;
  run: Run; runState: "loading" | "ready" | "none";
};

async function obtain(): Promise<Handle> {
  try {
    const cached = JSON.parse(sessionStorage.getItem(CACHE_A) ?? "null") as Handle | null;
    if (cached) {
      const job = await api.analysis(cached.analysisId);
      if (job.status === "COMPLETED") return cached;
    }
  } catch { /* analyze afresh */ }
  const r = await demos.analyze(DEMO);
  const handle = { analysisId: r.analysis_id, snapshotId: r.snapshot_id };
  let job = await api.analysis(handle.analysisId);
  for (let n = 0; n < 40 && ["QUEUED", "RUNNING"].includes(job.status); n++) {
    await new Promise((res) => setTimeout(res, 600));
    job = await api.analysis(handle.analysisId);
  }
  if (job.status !== "COMPLETED") throw new Error("analysis did not complete");
  try { sessionStorage.setItem(CACHE_A, JSON.stringify(handle)); } catch { /* ignore */ }
  return handle;
}

function describe(ev: { kind: string; payload: Record<string, unknown> }): Step {
  const p = ev.payload as { fn?: string; line?: number; locals?: Record<string, { repr?: string }>; arg?: { repr?: string } };
  const line = typeof p.line === "number" ? p.line : null;
  if (ev.kind === "call") {
    const args = p.locals && p.fn !== "<module>"
      ? Object.entries(p.locals).map(([k, v]) => `${k}=${v.repr ?? "?"}`).join(", ") : "";
    return { kind: "call", line, text: `call ${p.fn}(${args})` };
  }
  if (ev.kind === "return") return { kind: "return", line, text: `return ${p.arg?.repr ?? "None"}` };
  return { kind: "line", line, text: `line ${line}` };
}

async function obtainRun(fn: string, lo: number, hi: number): Promise<Run> {
  let id: string | null = null;
  try {
    const c = sessionStorage.getItem(CACHE_X);
    if (c) { const j = await executions.get(c); if (j.status === "COMPLETED") id = c; }
  } catch { /* run afresh */ }
  if (!id) {
    const r = await demos.run(DEMO);
    if (r.status !== "COMPLETED") return null;
    id = r.execution_id;
    try { sessionStorage.setItem(CACHE_X, id); } catch { /* ignore */ }
  }
  const [{ events }, out] = await Promise.all([executions.events(id, 0, 200), executions.output(id)]);
  const mine = events.filter((e) => (e.payload as { fn?: string }).fn === fn);
  const steps = (mine.length ? mine : events.slice(0, 8)).map(describe)
    .filter((s) => s.line == null || (s.line >= lo && s.line <= hi) || mine.length === 0).slice(0, 8);
  return { stdout: out.stdout ?? "", steps, total: events.length, exit: out.exit_code, executionId: id };
}

function useJourney(): Data {
  const [d, setD] = useState<Data>({
    state: "loading", handle: null, source: [], first: 1, fn: "", fileLines: 0,
    tokens: [], ast: [], bytecode: [], run: null, runState: "loading",
  });
  useEffect(() => {
    let alive = true;
    (async () => {
      let region = { fn: "", lo: 1, hi: 1 };
      try {
        const h = await obtain();
        const [tok, ast, bc]: StageData[] = await Promise.all(["tokens", "ast", "bytecode"].map((s) => api.stage(h.analysisId, s)));
        let lines: string[] = []; let sha: string | undefined;
        if (h.snapshotId) {
          const snap = await api.snapshot("demo-library", h.snapshotId);
          const f = snap.files.find((x) => x.rel_path.endsWith(`${DEMO}.py`)) ?? snap.files[0];
          const fd = await api.file("demo-library", h.snapshotId, f.id);
          lines = (fd.text ?? "").split("\n"); sha = fd.content_sha256;
        }
        let at = lines.findIndex((l) => /^def\s/.test(l)); if (at < 0) at = 0;
        const src = lines.slice(at, at + 4);
        region = { fn: /^def\s+(\w+)/.exec(src[0] ?? "")?.[1] ?? "", lo: at + 1, hi: at + src.length };
        if (alive) setD((x) => ({
          ...x, state: "ready", handle: h, source: src, first: at + 1, fn: region.fn,
          fileLines: lines.filter((_, i) => i < lines.length - 1 || lines[i] !== "").length, fileSha: sha,
          tokens: tok.items as unknown as Tok[], ast: ast.items as unknown as AstNode[],
          bytecode: bc.items as unknown as Ins[], tokSha: tok.raw_artifact_sha256 ?? undefined,
        }));
      } catch {
        if (alive) setD((x) => ({ ...x, state: "failed" }));
        return;
      }
      try {
        const run = await obtainRun(region.fn, region.lo, region.hi);
        if (alive) setD((x) => ({ ...x, run, runState: run ? "ready" : "none" }));
      } catch {
        if (alive) setD((x) => ({ ...x, runState: "none" }));
      }
    })();
    return () => { alive = false; };
  }, []);
  return d;
}

/* ——— colouring: the same hues the workspace uses ——— */
const KW = new Set(["def", "return", "if", "else", "elif", "for", "while", "in", "import", "from", "class", "and", "or", "not", "True", "False", "None", "lambda", "yield", "with", "as", "try", "except", "raise", "pass", "break", "continue", "global"]);
function colour(line: string) {
  const out: Array<{ t: string; c?: string }> = [];
  const re = /(#.*$)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|(\b\d+(?:\.\d+)?\b)|(\b[A-Za-z_]\w*\b)|(\s+|.)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(line))) {
    if (m[1]) out.push({ t: m[1], c: "k-com" });
    else if (m[2]) out.push({ t: m[2], c: "k-str" });
    else if (m[3]) out.push({ t: m[3], c: "k-num" });
    else if (m[4]) out.push({ t: m[4], c: KW.has(m[4]) ? "k-kw" : undefined });
    else out.push({ t: m[5] });
  }
  return out;
}
function tokClass(kind: string, text: string): string {
  const u = kind.toUpperCase();
  if (u === "NUMBER") return "k-num";
  if (u.includes("STRING")) return "k-str";
  if (u === "NAME") return KW.has(text) ? "k-kw" : "k-id";
  return "k-op";
}

function Journey({ d }: { d: Data }) {
  const [phase, setPhase] = useState(0);
  const [playing, setPlaying] = useState(() => !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
  const [held, setHeld] = useState(false);          // pointer or focus is inside the window
  const [sel, setSel] = useState<number>(d.first + d.source.length - 1);
  const [step, setStep] = useState(0);
  const winRef = useRef<HTMLDivElement | null>(null);
  const lineNos = useMemo(() => d.source.map((_, i) => d.first + i), [d.source, d.first]);
  const run = d.run;
  const pid = PHASES[phase].id;

  const active = playing && !held;

  // advance the phase on a timer; each phase starts its own sweep from the beginning
  useEffect(() => {
    if (!active) return;
    const t = setTimeout(() => setPhase((p) => (p + 1) % PHASES.length), PHASE_MS[phase]);
    return () => clearTimeout(t);
  }, [active, phase]);
  useEffect(() => { setStep(0); setSel(lineNos[lineNos.length - 1] ?? d.first); }, [phase]); // eslint-disable-line react-hooks/exhaustive-deps

  // sweep the selected line through the region (tokens, syntax, bytecode) ...
  useEffect(() => {
    if (!active || !["tokens", "ast", "bytecode"].includes(pid) || lineNos.length < 2) return;
    let i = lineNos.length - 1;
    const t = setInterval(() => { i = (i + 1) % lineNos.length; setSel(lineNos[i]); }, 1350);
    return () => clearInterval(t);
  }, [active, pid, lineNos]);
  // ... and step through the recorded events in the run phase
  useEffect(() => {
    if (!active || pid !== "run" || !run || run.steps.length < 2) return;
    const t = setInterval(() => setStep((s) => (s + 1) % run.steps.length), 1050);
    return () => clearInterval(t);
  }, [active, pid, run]);

  const curStep = pid === "run" && run ? run.steps[Math.min(step, run.steps.length - 1)] : null;
  const hot = pid === "run" ? curStep?.line ?? null : pid === "source" ? null : sel;

  const toks = useMemo(() => d.tokens.filter((t) => t.line === sel && !SKIP_TOK.has(t.kind.toUpperCase()) && !t.text.includes("\n")), [d.tokens, sel]);
  const nodes = useMemo(() => {
    const byId = new Map(d.ast.map((n) => [n.id, n]));
    const depth = (n: AstNode) => { let k = 0, p = n.parent ? byId.get(n.parent) : undefined; while (p) { k++; p = p.parent ? byId.get(p.parent) : undefined; } return k; };
    const here = d.ast.filter((n) => n.line === sel).map((n) => ({ n, depth: depth(n) }));
    const min = Math.min(...here.map((x) => x.depth), 99);
    return here.map((x) => ({ ...x, rel: Math.min(4, x.depth - min) }));
  }, [d.ast, sel]);
  const groups = useMemo(() => {
    const out: Array<{ co: string; ins: Ins[] }> = [];
    let cur: { co: string; ins: Ins[] } | null = null;
    for (const i of d.bytecode) {
      if (i.starts_line != null) cur = i.starts_line === sel ? { co: i.code_object, ins: [] } : null;
      if (cur) { cur.ins.push(i); if (!out.includes(cur)) out.push(cur); }
    }
    return out;
  }, [d.bytecode, sel]);
  const insTotal = groups.reduce((a, g) => a + g.ins.length, 0);
  let budget = 10;

  const pick = useCallback((n: number) => { setPlaying(false); setSel(n); }, []);
  const h = d.handle;
  const stage = PHASES[phase].stage;
  const open = !h ? "/demos" : stage
    ? `/workspace?demo=${DEMO}&analysis=${h.analysisId}${h.snapshotId ? `&snapshot=${h.snapshotId}&project=demo-library` : ""}&file=${DEMO}.py&stage=${stage}`
    : `/demos/${DEMO}`;

  return (
    <div className="jw" ref={winRef}
         onPointerEnter={() => setHeld(true)} onPointerLeave={() => setHeld(false)}
         onFocus={() => setHeld(true)} onBlur={(e) => { if (!winRef.current?.contains(e.relatedTarget as Node)) setHeld(false); }}>
      <div className="jw-bar">
        <span className="jw-file"><b>{DEMO}.py</b> · real CPython 3.12 output</span>
        <span className="jw-count tabular" aria-hidden>{phase + 1} / {PHASES.length}</span>
        <button type="button" className="jw-play" aria-label={playing ? "Pause the tour" : "Play the tour"} onClick={() => setPlaying((p) => !p)}>
          <Icon name={playing ? "pause" : "play"} size={13} />
        </button>
      </div>

      <div className="jw-screen" data-phase={pid}>
        <div className="jw-cols">
          <div className="jw-src" role="group" aria-label="source lines">
            <h2 className="pl-h"><b>01</b> Source</h2>
            <div className="pl-body">
              {d.source.map((text, i) => {
                const n = d.first + i;
                return (
                  <button key={n} type="button" className={"pl-line" + (hot === n ? " on" : "")} aria-pressed={hot === n}
                          onClick={() => pick(n)} onMouseEnter={() => { if (["tokens", "ast", "bytecode"].includes(pid)) setSel(n); }}>
                    <span className="pl-n">{n}</span>
                    <span className="pl-code">{text.length ? colour(text).map((p, k) => <span key={k} className={p.c}>{p.t}</span>) : "​"}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="jw-out" aria-live="polite">
            <h2 className="pl-h">
              <b>{String(phase + 1).padStart(2, "0")}</b> {PHASES[phase].label}
              <span>{pid === "source" || pid === "run" ? PHASES[phase].tool : hot != null ? `line ${hot}` : ""}</span>
            </h2>

            {pid === "source" && (
              <div className="pl-body pl-note">
                <p>Your file, exactly as written.</p>
                <p className="muted-c">{d.fileLines} lines{d.fileSha ? ` · sha256 ${d.fileSha.slice(0, 12)}…` : ""}</p>
                <p className="muted-c">It is snapshotted, never changed, and never executed just to analyze it.</p>
              </div>
            )}

            {pid === "tokens" && (
              <div className="pl-body" data-pane="tokens">
                <ul className="pl-toks">
                  {toks.map((t, i) => (<li key={i}><span className={"pl-token " + tokClass(t.kind, t.text)}>{t.text}</span><i>{t.kind.toLowerCase()}</i></li>))}
                </ul>
                <p className="pl-prov tabular">via {PHASES[1].tool} · {toks.length} tokens on this line{d.tokSha ? ` · stream sha256 ${d.tokSha.slice(0, 12)}…` : ""}</p>
              </div>
            )}

            {pid === "ast" && (
              <div className="pl-body" data-pane="ast">
                <ul className="pl-nodes">
                  {nodes.slice(0, 10).map(({ n, rel }) => (
                    <li key={n.id} style={{ paddingLeft: rel * 14 }} className={nodeCategory(n as unknown as Record<string, unknown>)}>
                      <span className="pl-kind">{n.kind}</span>{n.name ? <span className="pl-name"> {n.name}</span> : null}
                    </li>
                  ))}
                  {nodes.length > 10 && <li className="pl-more">+{nodes.length - 10} more</li>}
                  {nodes.length === 0 && <li className="pl-more">no node starts on this line</li>}
                </ul>
                <p className="pl-prov tabular">via {PHASES[2].tool} · {nodes.length} nodes start on this line</p>
              </div>
            )}

            {pid === "bytecode" && (
              <div className="pl-body" data-pane="bytecode">
                {groups.map((g, gi) => {
                  const take = g.ins.slice(0, Math.max(0, budget));
                  budget -= take.length;
                  return take.length ? (
                    <div key={gi} className="pl-grp">
                      <div className="pl-co">{g.co.replace(/^co\d+:/, "")}</div>
                      {take.map((i) => (
                        <div key={i.offset} className="pl-ins">
                          <span className="pl-off">{String(i.offset).padStart(3, "0")}</span>
                          <span className="pl-op">{i.opname}</span>
                          <span className="pl-arg">{i.argval && i.argval !== "None" ? i.argval : ""}</span>
                        </div>
                      ))}
                    </div>
                  ) : null;
                })}
                {insTotal === 0 && <p className="pl-more">no instruction starts on this line</p>}
                <p className="pl-prov tabular">via {PHASES[3].tool} · {insTotal} instructions for this line</p>
              </div>
            )}

            {pid === "run" && (
              <div className="pl-body" data-pane="run">
                {d.runState === "loading" && <p className="pl-more">recording the run in a sandbox…</p>}
                {d.runState === "none" && <p className="pl-more">The run is not available right now. Open the demo to record it.</p>}
                {run && (
                  <>
                    <ol className="pl-steps">
                      {run.steps.map((s, i) => (
                        <li key={i} className={(i === Math.min(step, run.steps.length - 1) ? "on " : "") + s.kind}>
                          <span className="pl-sq tabular">{String(i + 1).padStart(2, "0")}</span><span>{s.text}</span>
                        </li>
                      ))}
                    </ol>
                    <pre className="pl-stdout" aria-label="program output">{run.stdout.trimEnd()}</pre>
                    <p className="pl-prov tabular">{run.total} events recorded · exit {run.exit ?? "?"} · replay it in the workspace</p>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <ol className="jw-rail" aria-label="phases of the journey">
        {PHASES.map((p, i) => (
          <li key={p.id}>
            <button type="button" className={i === phase ? "on" : i < phase ? "done" : ""} aria-current={i === phase ? "step" : undefined}
                    onClick={() => { setPlaying(false); setPhase(i); }}>
              <span className="jw-rn">{i + 1}</span><span className="jw-rl">{p.short}</span>
              {i === phase && <span key={`${phase}-${active}`} className={"jw-fill" + (active ? " go" : "")} style={{ animationDuration: `${PHASE_MS[phase]}ms` }} aria-hidden />}
            </button>
          </li>
        ))}
      </ol>
      <p className="jw-foot">
        <span>Lines {d.first}–{d.first + d.source.length - 1} of <code>{DEMO}.py</code>. Pick a line, or a phase.</span>
        <Link to={open}>{stage ? "Open this stage in the workspace" : "Replay this run"} <span aria-hidden>→</span></Link>
      </p>
    </div>
  );
}

export default function SpecimenHero() {
  const d = useJourney();
  return (
    <section className="hero" aria-labelledby="hero-h">
      <div className="hero-grid">
        <div className="hero-copy">
          <p className="eyebrow">CompileVista · a compiler observatory</p>
          <h1 id="hero-h">Your program, <em>taken apart.</em></h1>
          <p className="hero-lede">Paste a C or Python program and follow it through the real Clang and CPython: tokens, syntax trees, IR, bytecode and a recorded run. Everything on screen is the tools' own output.</p>
          <div className="hero-ctas">
            <Link to="/demos" className="btn primary big">Explore the demos</Link>
            <Link to="/workspace" className="btn big">Paste your own code</Link>
          </div>
          <dl className="hero-facts">
            <div><dt>76 / 76</dt><dd>metrics match an independent oracle</dd></div>
            <div><dt>20</dt><dd>real programs to take apart</dd></div>
            <div><dt>0</dt><dd>bytes leave your machine</dd></div>
          </dl>
        </div>

        {d.state === "failed" ? (
          <div className="jw jw-off" role="status">
            <p><b>The live window needs the local backend.</b> Start it with <code>Start.cmd</code>. Nothing here is simulated, so without the backend there is nothing to show.</p>
          </div>
        ) : d.state === "loading" ? (
          <div className="jw" role="status" aria-label="loading the journey">
            <div className="jw-bar"><span className="jw-file"><b>{DEMO}.py</b> · analyzing with CPython 3.12…</span></div>
            <div className="jw-screen"><div className="pl-skel"><i /><i /><i /><i /><i /><i /></div></div>
          </div>
        ) : (
          <Journey d={d} />
        )}
      </div>
    </section>
  );
}
