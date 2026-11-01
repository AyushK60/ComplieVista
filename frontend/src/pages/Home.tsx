import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, Capabilities, Health } from "../api";

/**
 * M8 landing page — the public presentation of the product.
 * Hero: conceptual, choreographed source→tokens→AST→bytecode→execution loop
 * (educational only; never claims measured compiler timing). Chapters tell the
 * story; system diagnostics live in the footer, not the headline.
 */

type Phase = 0 | 1 | 2 | 3 | 4;
const PHASE_LABELS = ["source", "tokens", "syntax tree", "bytecode", "execution"];

function useHeroPhase(): Phase {
  const [p, setP] = useState<Phase>(0);
  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) { setP(4); return; }
    const t = setInterval(() => setP((v) => (((v + 1) % 5) as Phase)), 2600);
    return () => clearInterval(t);
  }, []);
  return p;
}

/* A tiny, honest program (PY-01 flavored) drives the hero choreography. */
const HERO_LINES = [
  ["total", " ", "=", " ", "0", ""],
  ["for", " i ", "in", " range(3)", ":"],
  ["    total", " += ", "i"],
  ["print", "(total)"],
];

const HERO_TOKENS: Array<{ t: string; c: string }> = [
  { t: "total", c: "tok-name" }, { t: "=", c: "tok-op" }, { t: "0", c: "tok-num" },
  { t: "for", c: "tok-kw" }, { t: "i", c: "tok-name" }, { t: "in", c: "tok-kw" },
  { t: "range", c: "tok-name" }, { t: "(", c: "tok-op" }, { t: "3", c: "tok-num" },
  { t: ")", c: "tok-op" }, { t: ":", c: "tok-op" },
  { t: "total", c: "tok-name" }, { t: "+=", c: "tok-op" }, { t: "i", c: "tok-name" },
  { t: "print", c: "tok-name" }, { t: "(", c: "tok-op" }, { t: "total", c: "tok-name" },
  { t: ")", c: "tok-op" },
];

const HERO_BC = [
  "RESUME 0", "LOAD_CONST 0", "STORE_NAME total", "LOAD_NAME range",
  "PUSH_NULL", "LOAD_CONST 3", "CALL 1", "GET_ITER", "FOR_ITER",
  "STORE_NAME i", "LOAD_NAME total", "LOAD_NAME i", "INPLACE_ADD",
  "STORE_NAME total", "JUMP_BACKWARD", "LOAD_NAME print", "LOAD_NAME total",
  "CALL 0", "POP_TOP", "RETURN_CONST None",
];

function HeroVisual() {
  const phase = useHeroPhase();
  return (
    <div className="hero-stage" role="img"
         aria-label="Conceptual animation: source code separates into tokens, forms a syntax tree, compiles to bytecode, then executes">
      <div className="hero-frame panel">
        <div className="hero-frame-h">
          <span className="dot" /><span className="dot" /><span className="dot" />
          <span className="hero-frame-title">total_demo.py — conceptual view</span>
          <span className={`hero-phase p${phase}`}>{PHASE_LABELS[phase]}</span>
        </div>

        {/* phase 0: source */}
        <pre className={"hero-src" + (phase === 0 ? " on" : "")} aria-hidden>
          {HERO_LINES.map((l, i) => (
            <div className="hl" key={i}>
              <span className="ln">{i + 1}</span>
              {l.map((seg, j) => <span key={j}>{seg}</span>)}
            </div>
          ))}
        </pre>

        {/* phase 1: tokens */}
        <div className={"hero-tokens" + (phase === 1 ? " on" : "")} aria-hidden>
          {HERO_TOKENS.map((tk, i) => (
            <span key={i} className={`hero-token ${tk.c}`} style={{ animationDelay: `${i * 45}ms` }}>
              {tk.t}
            </span>
          ))}
        </div>

        {/* phase 2: AST */}
        <svg className={"hero-ast" + (phase === 2 ? " on" : "")} viewBox="0 0 460 170" aria-hidden>
          <g className="ast-edge"><path d="M230 30 L120 85" /><path d="M230 30 L340 85" /><path d="M230 30 L230 85" /></g>
          <g className="ast-edge"><path d="M120 85 L70 140" /><path d="M120 85 L170 140" /><path d="M340 85 L300 140" /><path d="M340 85 L390 140" /></g>
          <g className="ast-node">
            <rect x="196" y="8" width="68" height="26" rx="7" /><text x="230" y="25">Module</text>
            <rect x="86" y="63" width="68" height="26" rx="7" /><text x="120" y="80">For</text>
            <rect x="196" y="63" width="68" height="26" rx="7" /><text x="230" y="80">Assign</text>
            <rect x="306" y="63" width="68" height="26" rx="7" /><text x="340" y="80">Expr</text>
            <rect x="36" y="118" width="68" height="26" rx="7" /><text x="70" y="135">Name</text>
            <rect x="136" y="118" width="68" height="26" rx="7" /><text x="170" y="135">Call</text>
            <rect x="266" y="118" width="68" height="26" rx="7" /><text x="300" y="135">Name</text>
            <rect x="356" y="118" width="68" height="26" rx="7" /><text x="390" y="135">Call</text>
          </g>
        </svg>

        {/* phase 3: bytecode lanes */}
        <div className={"hero-bc" + (phase === 3 ? " on" : "")} aria-hidden>
          <div className="bc-co">code object <b>“&lt;module&gt;”</b> · CPython 3.12</div>
          <div className="bc-lanes">
            {HERO_BC.map((op, i) => (
              <span key={i} className="bc-op" style={{ animationDelay: `${i * 30}ms` }}>{op}</span>
            ))}
          </div>
        </div>

        {/* phase 4: execution */}
        <div className={"hero-run" + (phase === 4 ? " on" : "")} aria-hidden>
          <div className="run-frames">
            <div className="run-frame main">&lt;module&gt;</div>
            <div className="run-cursor" />
          </div>
          <div className="run-out"><span className="run-caret" />stdout: <b>3</b></div>
        </div>

        <div className="hero-progress" aria-hidden>
          {PHASE_LABELS.map((l, i) => (
            <span key={l} className={i === phase ? "on" : ""} data-label={l} />
          ))}
        </div>
      </div>
      <p className="hero-note">
        Conceptual animation — the real product shows your program’s actual tokens, AST,
        bytecode and recorded execution.
      </p>
    </div>
  );
}

function PipelineMap({ stages, accent }: { stages: string[]; accent: string }) {
  return (
    <ol className="pipeline" style={{ ["--pipe-accent" as string]: accent }}>
      {stages.map((s) => <li key={s}><span>{s}</span></li>)}
    </ol>
  );
}

const C_STAGES = ["Preprocess", "Tokens", "AST + semantics", "LLVM IR", "Optimization", "Assembly", "Object + link", "Execution"];
const PY_STAGES = ["Tokens", "AST", "Compile analysis", "Code objects", "Bytecode", "Interpreter", "Runtime + memory"];

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [tools, setTools] = useState<Capabilities | null>(null);
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    api.capabilities().then(setTools).catch(() => setTools(null));
  }, []);

  const toolLine = useMemo(() => {
    if (!tools) return null;
    const avail = Object.entries(tools.tools).filter(([, v]) => v.available);
    return avail.map(([k, v]) => `${k} ${v.version.split(" ").slice(-1)[0]}`).join(" · ");
  }, [tools]);

  return (
    <main className="landing">
      {/* ——— HERO ——— */}
      <section className="hero">
        <div className="hero-copy">
          <p className="hero-eyebrow">CompileVista · Computational Atlas</p>
          <h1>Your code has a<br /><em>hidden journey.</em><br />Explore every step.</h1>
          <p className="hero-sub">
            Paste a C or Python program and watch real compiler and interpreter artifacts
            unfold — tokens, syntax trees, LLVM IR, bytecode, recorded execution — in one
            connected, visual observatory.
          </p>
          <div className="hero-ctas">
            <Link to="/demos" className="btn primary big">Explore a Program</Link>
            <Link to="/workspace" className="btn big">Import Your Code</Link>
          </div>
          <p className="hero-meta">
            Clang/LLVM 18 · CPython 3.12 · restricted container execution · every view
            backed by digest-verified artifacts
          </p>
        </div>
        <HeroVisual />
      </section>

      {/* ——— CH1 The Hidden Journey ——— */}
      <section className="chapter ivory">
        <div className="chapter-inner">
          <p className="ch-no">01 · The Hidden Journey</p>
          <h2>Between your keystrokes and the machine’s answer, your code is transformed — twice.</h2>
          <p className="ch-lede">
            A compiler and an interpreter take different roads, but both begin the same way:
            reading your text, finding its structure, and rebuilding it into something a
            machine can run. CompileVista walks you down each road, stage by stage, with the
            real artifacts each tool produces.
          </p>
          <div className="two-worlds">
            <div className="world">
              <h3><span className="world-dot c" />C — compiled with Clang/LLVM</h3>
              <PipelineMap stages={C_STAGES} accent="var(--cyan)" />
              <p className="world-note">Your program becomes native machine instructions before it runs.
                Every stage is a real Clang 18 invocation inside a restricted container.</p>
            </div>
            <div className="world">
              <h3><span className="world-dot py" />Python — interpreted by CPython 3.12</h3>
              <PipelineMap stages={PY_STAGES} accent="var(--violet)" />
              <p className="world-note">Your program is compiled to bytecode and executed by the CPython
                virtual machine. Different road, same rigorous evidence.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ——— CH2 See the Structure ——— */}
      <section className="chapter">
        <div className="chapter-inner">
          <p className="ch-no">02 · See the Structure</p>
          <h2>Watch your text become structure you can click.</h2>
          <div className="feature-row">
            <div className="feature panel">
              <div className="feature-visual tok-demo" aria-hidden>
                <span className="tok tok-kw">for</span>
                <span className="tok tok-name">i</span>
                <span className="tok tok-op">in</span>
                <span className="tok tok-name">range</span>
                <span className="tok tok-op">(</span>
                <span className="tok tok-num">3</span>
                <span className="tok tok-op">)</span>
                <span className="tok tok-op">:</span>
              </div>
              <h3>Token Formation</h3>
              <p>Your source separates into the exact tokens the toolchain reports — with
                types, values and source positions. Hover a token, see where it lives.</p>
            </div>
            <div className="feature panel">
              <div className="feature-visual" aria-hidden>
                <svg viewBox="0 0 220 96" className="mini-ast">
                  <g className="ast-edge"><path d="M110 18 L55 52" /><path d="M110 18 L165 52" /></g>
                  <g className="ast-edge"><path d="M55 52 L30 86" /><path d="M55 52 L85 86" /><path d="M165 52 L140 86" /><path d="M165 52 L190 86" /></g>
                  <g className="ast-node">
                    <rect x="84" y="6" width="52" height="20" rx="6" /><text x="110" y="20">For</text>
                    <rect x="31" y="42" width="48" height="20" rx="6" /><text x="55" y="56">Call</text>
                    <rect x="141" y="42" width="48" height="20" rx="6" /><text x="165" y="56">Body</text>
                    <rect x="8" y="76" width="44" height="18" rx="6" /><text x="30" y="89">Name</text>
                    <rect x="63" y="76" width="44" height="18" rx="6" /><text x="85" y="89">Args</text>
                    <rect x="118" y="76" width="44" height="18" rx="6" /><text x="140" y="89">Expr</text>
                    <rect x="168" y="76" width="44" height="18" rx="6" /><text x="190" y="89">Inc</text>
                  </g>
                </svg>
              </div>
              <h3>Syntax Trees</h3>
              <p>Pan, zoom, expand and inspect the actual parse tree — every node linked
                back to the exact lines and columns that produced it.</p>
            </div>
            <div className="feature panel">
              <div className="feature-visual bc-demo" aria-hidden>
                <div className="bc-line"><code>0000</code><b>RESUME</b><span>0</span></div>
                <div className="bc-line"><code>0002</code><b>LOAD_CONST</b><span>0</span></div>
                <div className="bc-line"><code>0004</code><b>STORE_NAME</b><span>total</span></div>
                <div className="bc-line"><code>0012</code><b>LOAD_NAME</b><span>range</span></div>
              </div>
              <h3>IR &amp; Bytecode</h3>
              <p>LLVM’s intermediate representation for C, CPython bytecode for Python —
                the real instructions, version-pinned, never paraphrased.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ——— CH3 Watch It Execute ——— */}
      <section className="chapter ivory">
        <div className="chapter-inner">
          <p className="ch-no">03 · Watch It Execute</p>
          <h2>Execution isn’t a log file. It’s a landscape.</h2>
          <p className="ch-lede">
            Runs happen once, inside a restricted container, and every event is recorded and
            checksummed. Then the scene belongs to you: replay a recursive call tree, watch
            the stack tower grow and unwind, inspect the variables each frame held.
          </p>
          <div className="exec-teaser panel">
            <svg viewBox="0 0 640 170" className="exec-svg" aria-hidden>
              <g className="exec-tree">
                <path d="M80 30 L50 78" /><path d="M80 30 L110 78" />
                <path d="M50 78 L35 126" /><path d="M50 78 L70 126" />
                <path d="M110 78 L95 126" /><path d="M110 78 L130 126" />
              </g>
              <g className="exec-node">
                <rect x="52" y="12" width="58" height="24" rx="7" /><text x="81" y="28">fib(5)</text>
                <rect x="26" y="66" width="52" height="22" rx="7" /><text x="52" y="81">fib(4)</text>
                <rect x="88" y="66" width="48" height="22" rx="7" /><text x="112" y="81">fib(3)</text>
                <rect x="14" y="116" width="44" height="20" rx="6" /><text x="36" y="130">fib(3)</text>
                <rect x="58" y="116" width="40" height="20" rx="6" /><text x="78" y="130">fib(2)</text>
                <rect x="82" y="116" width="40" height="20" rx="6" /><text x="102" y="130">fib(2)</text>
                <rect x="126" y="116" width="40" height="20" rx="6" /><text x="146" y="130">fib(1)</text>
              </g>
              <g className="exec-tower">
                <rect x="420" y="118" width="150" height="22" rx="5" />
                <rect x="420" y="92" width="150" height="22" rx="5" />
                <rect x="420" y="66" width="150" height="22" rx="5" />
                <rect x="420" y="40" width="150" height="22" rx="5" />
                <text x="432" y="133">frame &lt;module&gt;</text>
                <text x="432" y="107">frame fib(5)</text>
                <text x="432" y="81">frame fib(4)</text>
                <text x="432" y="55" className="hot">frame fib(3) ← active</text>
              </g>
            </svg>
            <p className="exec-caption">
              Left: the recorded call tree of a recursion demo. Right: the live stack tower.
              Both are built from the actual events the run produced — call, line, return,
              exception — not a simulation.
            </p>
          </div>
        </div>
      </section>

      {/* ——— CH4 Compare Two Worlds ——— */}
      <section className="chapter">
        <div className="chapter-inner">
          <p className="ch-no">04 · Compare Two Worlds</p>
          <h2>The same idea, two machines.</h2>
          <div className="compare-teaser">
            <div className="ct-card panel">
              <span className="badge exact">C</span>
              <p>Solving the same problem in C means managing memory explicitly and trusting
                the optimizer. Compare the IR at -O0 and -O2, read the assembly, watch
                allocations and frees as they happen.</p>
            </div>
            <div className="ct-vs">vs</div>
            <div className="ct-card panel">
              <span className="badge exact">Python</span>
              <p>In Python, objects live on a reference-counted heap and frames are first-class.
                Inspect identity, aliasing, garbage collection and tracemalloc — the runtime
                itself reports what it observed.</p>
            </div>
          </div>
          <p className="ch-lede">
            Paired demo programs run both languages through their <em>own</em> pipeline —
            stages are synchronized by concept, never pretended equivalent.
          </p>
        </div>
      </section>

      {/* ——— CH5 Start Exploring ——— */}
      <section className="chapter start">
        <div className="chapter-inner">
          <p className="ch-no">05 · Start Exploring</p>
          <h2>Three ways in.</h2>
          <div className="start-row">
            <Link to="/demos" className="start-card panel">
              <h3>Demo Library</h3>
              <p>Twenty curated programs — recursion, pointers, sorting, closures — each with
                guided journeys through real artifacts.</p>
              <span className="start-cta">Open the gallery →</span>
            </Link>
            <Link to="/workspace" className="start-card panel">
              <h3>Source Workspace</h3>
              <p>Paste code, upload files or ZIPs, or import a public GitHub repo as a
                read-only, digest-pinned snapshot.</p>
              <span className="start-cta">Bring your code →</span>
            </Link>
            <Link to="/compare" className="start-card panel">
              <h3>Compare Languages</h3>
              <p>Run matched C/Python pairs through both pipelines and see each runtime
                report on the same concept.</p>
              <span className="start-cta">See both worlds →</span>
            </Link>
          </div>
        </div>
      </section>

      {/* ——— footer: system status, deliberately subordinate ——— */}
      <footer className="site-footer">
        <div className="footer-inner">
          <p className="prov">
            <span>
              system:{" "}
              {health
                ? <code>ok · python {health.python_version} · schema {health.schema_version}</code>
                : <code>backend unreachable</code>}
            </span>
            {toolLine && <span>tools: <code>{toolLine}</code></span>}
          </p>
          <p className="muted">
            Explore Mode shows the journey; Technical Mode (top right) reveals provenance,
            digests and raw artifacts. Execution is restricted to curated programs in
            sandboxed containers; imported repository code is never executed.
          </p>
        </div>
      </footer>
    </main>
  );
}
