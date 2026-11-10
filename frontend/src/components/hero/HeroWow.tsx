import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, demos, AnalysisJob, StageData } from "../../api";
import { Icon } from "../../ui";

const GraphView = lazy(() => import("../GraphView"));

/**
 * Landing hero. A dark, animated stage that is also a real instrument: the window on
 * the right runs a real CPython 3.12 analysis of PY-01 and shows the tool's own tokens,
 * syntax tree and bytecode next to the exact source. Everything decorative (background
 * tree, drifting tokens, ribbon) is labelled as decoration by aria-hidden and never
 * claims to be output. If the backend is unreachable the window says so honestly.
 */
const DEMO = "PY-01";
const CACHE = "cv.hero.analysis.v2";
type StepId = "tokens" | "ast" | "bytecode";
const STEPS: Array<{ id: StepId; label: string; blurb: string; ribbon: number }> = [
  { id: "tokens", label: "Tokens", blurb: "Your text, split into the pieces the lexer reports.", ribbon: 1 },
  { id: "ast", label: "Syntax tree", blurb: "The parser nests those tokens into structure. Click a node.", ribbon: 2 },
  { id: "bytecode", label: "Bytecode", blurb: "The instructions the CPython virtual machine runs.", ribbon: 4 },
];
const WORDS = ["tokens", "a syntax tree", "LLVM IR", "bytecode", "a running program"];
const RIBBON = ["Source", "Tokens", "Syntax tree", "LLVM IR", "Bytecode", "Execution"];
const FLOATERS = ["def", "for", "->", "0x1f", "%3 = add", "LOAD_NAME", "i32", "{ }", "==", "return", "while", "ptr", "JUMP", "call", "br", "i64", "yield", "int main"];

type Handle = { analysisId: string; snapshotId?: string };
type Live = {
  state: "loading" | "ready" | "failed";
  handle: Handle | null;
  tokens: StageData | null;
  bytecode: StageData | null;
  source: string[] | null;
};

async function obtain(): Promise<{ handle: Handle; job: AnalysisJob }> {
  try {
    const cached = JSON.parse(sessionStorage.getItem(CACHE) ?? "null") as Handle | null;
    if (cached) {
      const job = await api.analysis(cached.analysisId);
      if (job.status === "COMPLETED") return { handle: cached, job };
    }
  } catch { /* fresh analysis below */ }
  const r = await demos.analyze(DEMO);
  const handle = { analysisId: r.analysis_id, snapshotId: r.snapshot_id };
  let job = await api.analysis(handle.analysisId);
  for (let n = 0; n < 40 && ["QUEUED", "RUNNING"].includes(job.status); n++) {
    await new Promise((res) => setTimeout(res, 600));
    job = await api.analysis(handle.analysisId);
  }
  if (job.status !== "COMPLETED") throw new Error("analysis did not complete");
  try { sessionStorage.setItem(CACHE, JSON.stringify(handle)); } catch { /* ignore */ }
  return { handle, job };
}

function useLive(): Live {
  const [live, setLive] = useState<Live>({ state: "loading", handle: null, tokens: null, bytecode: null, source: null });
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { handle } = await obtain();
        const [tokens, bytecode] = await Promise.all([api.stage(handle.analysisId, "tokens"), api.stage(handle.analysisId, "bytecode")]);
        let source: string[] | null = null;
        try {
          if (handle.snapshotId) {
            const snap = await api.snapshot("demo-library", handle.snapshotId);
            const f = snap.files.find((x) => x.rel_path.endsWith(`${DEMO}.py`)) ?? snap.files[0];
            const fd = await api.file("demo-library", handle.snapshotId, f.id);
            source = (fd.text ?? "").split("\n");
          }
        } catch { /* source pane falls back to a skeleton */ }
        if (alive) setLive({ state: "ready", handle, tokens, bytecode, source });
      } catch {
        if (alive) setLive((l) => ({ ...l, state: "failed" }));
      }
    })();
    return () => { alive = false; };
  }, []);
  return live;
}

/* ——— decoration ——— */
function mulberry(seed: number) {
  return () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

function TreeBackdrop() {
  const { nodes, edges } = useMemo(() => {
    const rnd = mulberry(7);
    const ns: Array<{ x: number; y: number; w: number; hot: boolean; d: number }> = [];
    const es: Array<[number, number]> = [];
    const place = (depth: number, y0: number, y1: number, parent: number) => {
      const idx = ns.length;
      ns.push({ x: 120 + depth * 250, y: (y0 + y1) / 2, w: 70 + Math.floor(rnd() * 60), hot: rnd() < 0.16, d: depth });
      if (parent >= 0) es.push([parent, idx]);
      if (depth >= 5) return;
      const kids = depth === 0 ? 3 : rnd() < 0.3 ? 1 : 2 + Math.floor(rnd() * 2);
      const span = (y1 - y0) / kids;
      for (let k = 0; k < kids; k++) place(depth + 1, y0 + k * span, y0 + (k + 1) * span, idx);
    };
    place(0, 40, 860, -1);
    return { nodes: ns, edges: es };
  }, []);
  return (
    <svg className="wow-tree" viewBox="0 0 1500 900" preserveAspectRatio="xMidYMid slice" aria-hidden>
      {edges.map(([a, b], i) => {
        const A = nodes[a], B = nodes[b];
        const x1 = A.x + A.w, y1 = A.y, x2 = B.x, y2 = B.y;
        const mx = (x1 + x2) / 2;
        return <path key={i} d={`M${x1} ${y1} C${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`} className={"wt-edge" + (i % 4 === 0 ? " flow" : "")} style={{ animationDelay: `${(i % 9) * -0.7}s` }} />;
      })}
      {nodes.map((n, i) => (
        <rect key={i} x={n.x} y={n.y - 9} width={n.w} height={18} rx={5} className={"wt-node" + (n.hot ? " hot" : "")} style={{ animationDelay: `${(i % 11) * -0.5}s` }} />
      ))}
    </svg>
  );
}

function Floaters() {
  const items = useMemo(() => {
    const rnd = mulberry(21);
    return FLOATERS.map((t, i) => ({ t, left: 4 + rnd() * 92, dur: 18 + rnd() * 22, delay: -rnd() * 30, size: 11 + Math.floor(rnd() * 6), o: 0.1 + rnd() * 0.18, key: i }));
  }, []);
  return (
    <div className="wow-floaters" aria-hidden>
      {items.map((f) => (
        <span key={f.key} style={{ left: `${f.left}%`, animationDuration: `${f.dur}s`, animationDelay: `${f.delay}s`, fontSize: f.size, opacity: f.o }}>{f.t}</span>
      ))}
    </div>
  );
}

function RotatingWord() {
  const [i, setI] = useState(0);
  const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  useEffect(() => {
    if (reduced) return;
    const t = setInterval(() => setI((v) => (v + 1) % WORDS.length), 2400);
    return () => clearInterval(t);
  }, [reduced]);
  const cur = reduced ? WORDS.length - 1 : i;
  return (
    <span className="wow-rot" aria-live="off">
      <span className="wow-rot-sizer" aria-hidden>{WORDS.reduce((a, b) => (b.length > a.length ? b : a))}</span>
      {WORDS.map((w, k) => (
        <span key={w} className={"wow-word" + (k === cur ? " on" : k === (cur + WORDS.length - 1) % WORDS.length ? " out" : "")}>{w}</span>
      ))}
      <span className="sr-only">tokens, a syntax tree, LLVM IR, bytecode, a running program</span>
    </span>
  );
}

/* ——— the live window ——— */
const PY_KW = /\b(def|return|if|else|elif|for|while|in|import|from|class|and|or|not|True|False|None|print|range|global|lambda|yield|with|as|try|except|raise|pass|break|continue)\b/g;
function colorLine(line: string) {
  const parts: Array<{ t: string; c?: string }> = [];
  const re = /(#.*$)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|(\b\d+(?:\.\d+)?\b)|(\b[A-Za-z_][A-Za-z_0-9]*\b)|(\s+|.)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(line))) {
    if (m[1]) parts.push({ t: m[1], c: "c-com" });
    else if (m[2]) parts.push({ t: m[2], c: "c-str" });
    else if (m[3]) parts.push({ t: m[3], c: "c-num" });
    else if (m[4]) { PY_KW.lastIndex = 0; parts.push({ t: m[4], c: PY_KW.test(m[4]) ? "c-kw" : undefined }); }
    else parts.push({ t: m[5] });
  }
  return parts;
}

function Source({ lines, active }: { lines: string[] | null; active: number | null }) {
  if (!lines) return <div className="hw-skel" aria-hidden><i /><i /><i /><i /><i /><i /></div>;
  // skip the leading docstring banner: start at the first line of real code
  let start = 0;
  if (lines[0]?.trim().startsWith('"""')) {
    start = lines.findIndex((l, i) => i > 0 && l.includes('"""')) + 1;
  }
  const shown = lines.slice(start, start + 16);
  return (
    <div className="hw-src" role="region" aria-label="source of PY-01.py">
      {shown.map((l, i) => {
        const n = start + i + 1;
        return (
          <div key={n} className={"hw-line" + (active === n ? " hot" : "")}>
            <span className="hw-n">{n}</span>
            <span className="hw-code">{l.length ? colorLine(l).map((p, j) => <span key={j} className={p.c}>{p.t}</span>) : "​"}</span>
          </div>
        );
      })}
    </div>
  );
}

function Tokens({ data, active }: { data: StageData; active: number | null }) {
  const toks = (data.items as Array<{ kind: string; text: string; line: number }>)
    .filter((t) => !["NEWLINE", "NL", "INDENT", "DEDENT", "ENDMARKER", "ENCODING", "COMMENT"].includes(t.kind.toUpperCase()) && !t.text.includes("\n"));
  const byLine = new Map<number, typeof toks>();
  for (const t of toks) byLine.set(t.line, [...(byLine.get(t.line) ?? []), t]);
  const cls = (k: string) => {
    const u = k.toUpperCase();
    return u === "NAME" ? "k-name" : u === "NUMBER" ? "k-num" : u.includes("STRING") ? "k-str" : u === "OP" ? "k-op" : "k-kw";
  };
  return (
    <div className="lh-tokens" aria-label="tokens from the real tokenizer">
      {[...byLine.entries()].slice(0, 8).map(([ln, ts]) => (
        <div className={"lh-tokline" + (active === ln ? " hot" : "")} key={ln}>
          <span className="lh-ln">{ln}</span>
          {ts.slice(0, 9).map((t, i) => (
            <span key={i} className={`lh-tok ${cls(t.kind)}`} title={t.kind}>{t.text.length > 16 ? t.text.slice(0, 15) + "…" : t.text}</span>
          ))}
        </div>
      ))}
    </div>
  );
}

function Bytecode({ data }: { data: StageData }) {
  const ins = (data.items as Array<{ code_object: string; offset: number; opname: string; argval: string }>)
    .filter((i) => i.code_object === "<module>").slice(0, 13);
  return (
    <div className="lh-bytecode" aria-label="bytecode from CPython">
      {ins.map((i) => (
        <div key={i.offset} className="lh-ins">
          <span className="lh-off">{String(i.offset).padStart(4, "0")}</span>
          <span className="lh-op">{i.opname}</span>
          <span className="lh-arg">{i.argval && i.argval !== "None" ? i.argval : ""}</span>
        </div>
      ))}
    </div>
  );
}

function StageWindow({ live, onStep }: { live: Live; onStep: (ribbon: number) => void }) {
  const [step, setStep] = useState<StepId>("tokens");
  const [activeLine, setActiveLine] = useState<number | null>(null);
  const touched = useRef(false);
  const winRef = useRef<HTMLDivElement | null>(null);
  const ready = live.state === "ready";
  const cur = STEPS.find((s) => s.id === step)!;

  useEffect(() => { onStep(cur.ribbon); }, [cur.ribbon, onStep]);

  // lines that actually carry tokens, for the sweeping highlight
  const tokenLines = useMemo(() => {
    if (!live.tokens) return [] as number[];
    const s = new Set<number>();
    for (const t of live.tokens.items as Array<{ kind: string; line: number; text: string }>) {
      if (!["NEWLINE", "NL", "INDENT", "DEDENT", "ENDMARKER", "ENCODING", "COMMENT"].includes(t.kind.toUpperCase()) && !t.text.includes("\n")) s.add(t.line);
    }
    return [...s].slice(0, 8);
  }, [live.tokens]);

  const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  useEffect(() => {
    if (!ready || reduced || touched.current) return;
    const t = setInterval(() => {
      if (touched.current) return;
      setStep((s) => (s === "tokens" ? "ast" : s === "ast" ? "bytecode" : "tokens"));
    }, 7000);
    return () => clearInterval(t);
  }, [ready, reduced]);
  useEffect(() => {
    if (!ready || reduced || step !== "tokens" || !tokenLines.length) return;
    let i = 0;
    setActiveLine(tokenLines[0]);
    const t = setInterval(() => { i = (i + 1) % tokenLines.length; setActiveLine(tokenLines[i]); }, 1100);
    return () => clearInterval(t);
  }, [ready, reduced, step, tokenLines]);
  useEffect(() => { if (step !== "tokens") setActiveLine(null); }, [step]);

  // pointer parallax: the window tilts toward the cursor
  const onMove = (e: React.PointerEvent) => {
    const el = winRef.current; if (!el || reduced) return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5, py = (e.clientY - r.top) / r.height - 0.5;
    el.style.setProperty("--ry", String(-6 + px * 7));
    el.style.setProperty("--rx", String(2 - py * 6));
    el.style.setProperty("--mx", `${(px + 0.5) * 100}%`);
    el.style.setProperty("--my", `${(py + 0.5) * 100}%`);
  };
  const onLeave = () => { const el = winRef.current; if (!el) return; el.style.removeProperty("--ry"); el.style.removeProperty("--rx"); };

  const h = live.handle;
  const tryUrl = h
    ? `/workspace?demo=${DEMO}&analysis=${h.analysisId}${h.snapshotId ? `&snapshot=${h.snapshotId}&project=demo-library` : ""}&file=${DEMO}.py&stage=${step}`
    : "/demos";
  const stage = step === "tokens" ? live.tokens : step === "bytecode" ? live.bytecode : null;

  if (live.state === "failed") {
    return (
      <div className="hw-window hw-failed" ref={winRef}>
        <div className="hw-chrome"><i /><i /><i /><span className="hw-title">live view unavailable</span></div>
        <div className="hw-offline">
          <Icon name="alert" size={22} />
          <p>The live analysis needs the local backend. Start it with <code>Start.cmd</code>; nothing here is simulated.</p>
          <Link className="btn primary" to="/demos">Browse the demo library</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="hw-wrap" onPointerMove={onMove} onPointerLeave={onLeave}>
      <div className="hw-window" ref={winRef}>
        <span className="hw-glow" aria-hidden />
        <div className="hw-chrome">
          <i /><i /><i />
          <span className="hw-title">{DEMO}.py</span>
          <span className="spacer" />
          <span className="hw-live"><span className="dot" />{ready ? "live · CPython 3.12" : "analyzing…"}</span>
        </div>
        <div className="hw-steps" role="tablist" aria-label="pipeline stage">
          {STEPS.map((s, i) => (
            <button key={s.id} role="tab" aria-selected={step === s.id} className={step === s.id ? "on" : ""}
                    onClick={() => { touched.current = true; setStep(s.id); }}>
              <span className="lh-num">{i + 1}</span>{s.label}
            </button>
          ))}
          <span className="hw-blurb">{cur.blurb}</span>
        </div>
        <div className="hw-body">
          <div className="hw-left"><Source lines={live.source} active={activeLine} /></div>
          <div className="hw-flow" aria-hidden>
            <svg viewBox="0 0 60 300" preserveAspectRatio="none"><path d="M0 40 C30 40 30 90 60 90" /><path d="M0 130 C30 130 30 150 60 150" /><path d="M0 220 C30 220 30 210 60 210" /></svg>
          </div>
          <div className="hw-right" aria-live="polite">
            {!ready && <div className="hw-skel" aria-hidden><i /><i /><i /><i /><i /><i /></div>}
            {ready && step === "tokens" && live.tokens && <Tokens data={live.tokens} active={activeLine} />}
            {ready && step === "bytecode" && live.bytecode && <Bytecode data={live.bytecode} />}
            {ready && step === "ast" && h && (
              <div className="lh-graph" onPointerDown={() => { touched.current = true; }}>
                <Suspense fallback={<div className="hw-skel" aria-hidden><i /><i /><i /></div>}>
                  <GraphView compact analysisId={h.analysisId} stage="ast" onSelectNode={() => {}} onSelectLine={() => {}} />
                </Suspense>
              </div>
            )}
          </div>
        </div>
        <div className="hw-foot">
          {stage && <span className="lh-prov">{step === "tokens" ? `${stage.items.length} tokens` : `${stage.items.length} instructions`} · sha256 {stage.raw_artifact_sha256?.slice(0, 12)}…</span>}
          {step === "ast" && <span className="lh-prov">tool output, not a drawing · drag, zoom, click a node</span>}
          <span className="spacer" />
          <Link className="btn primary" to={tryUrl}>Try it <Icon name="right" size={14} /></Link>
        </div>
      </div>
      <span className="hw-chip c1" aria-hidden><i className="dot ok" /> exact output</span>
      <span className="hw-chip c2" aria-hidden>{live.tokens ? `${live.tokens.items.length} tokens` : "…"}</span>
      <span className="hw-chip c3" aria-hidden>no network · runs locally</span>
    </div>
  );
}

export default function HeroWow() {
  const live = useLive();
  const [ribbon, setRibbon] = useState(1);
  return (
    <section className="wow" aria-label="CompileVista introduction">
      <div className="wow-bg" aria-hidden>
        <span className="blob b1" /><span className="blob b2" /><span className="blob b3" />
        <TreeBackdrop />
        <Floaters />
        <span className="wow-grid" />
      </div>
      <div className="wow-inner">
        <div className="wow-copy">
          <Link to="/about" className="wow-pill"><span className="pulse" />Real Clang/LLVM 18 and CPython 3.12 output<Icon name="right" size={13} /></Link>
          <h1>Watch your code<br />become <RotatingWord /></h1>
          <p className="wow-sub">Paste a C or Python program and follow it through the real compiler: tokens, syntax trees, IR, bytecode and a recorded run. Nothing is simulated.</p>
          <div className="wow-cta">
            <Link to="/demos" className="wow-btn primary">Explore live demos <Icon name="right" size={16} /></Link>
            <Link to="/workspace" className="wow-btn ghost">Paste your code</Link>
            <span className="wow-kbd" aria-hidden><kbd>Ctrl</kbd><kbd>K</kbd> to jump anywhere</span>
          </div>
          <dl className="wow-stats">
            <div><dt>76 / 76</dt><dd>metrics matched an independent oracle</dd></div>
            <div><dt>20</dt><dd>real programs to take apart</dd></div>
            <div><dt>0</dt><dd>bytes leave your machine</dd></div>
          </dl>
        </div>
        <StageWindow live={live} onStep={setRibbon} />
      </div>
      <ol className="wow-ribbon" aria-label="the pipeline CompileVista shows">
        {RIBBON.map((r, i) => (
          <li key={r} className={i < ribbon ? "done" : i === ribbon ? "on" : ""}>
            <span className="rb-dot">{i + 1}</span><span className="rb-label">{r}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
