import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, Capabilities, Health } from "../api";
import HeroWow from "../components/hero/HeroWow";

/**
 * CompileVista landing — "The Living Compiler" (porcelain revision).
 * One continuous porcelain composition; every machine artifact lives on an
 * ink screen set into an instrument bezel. Hero: conceptual, choreographed
 * source→tokens→AST→bytecode→execution loop (educational only; never claims
 * measured compiler timing). System diagnostics live in the footer.
 */

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
      <HeroWow />

      {/* ——— CH1 The Hidden Journey ——— */}
      <section className="chapter">
        <div className="chapter-inner">
          <p className="ch-no">Two roads</p>
          <h2>Compiled or interpreted, your code is transformed first.</h2>
          <div className="two-worlds">
            <div className="world">
              <h3><span className="world-dot c" />C — compiled with Clang/LLVM</h3>
              <PipelineMap stages={C_STAGES} accent="var(--clay)" />
            </div>
            <div className="world">
              <h3><span className="world-dot py" />Python — interpreted by CPython 3.12</h3>
              <PipelineMap stages={PY_STAGES} accent="var(--plum)" />
            </div>
          </div>
        </div>
      </section>

      {/* ——— CH2 See the Structure ——— */}
      <section className="chapter">
        <div className="chapter-inner">
          <p className="ch-no">What you can inspect</p>
          <h2>Watch your text become structure you can click.</h2>
          <div className="feature-row">
            <div className="feature panel">
              <div className="feature-visual screen" aria-hidden>
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
              <div className="feature-visual screen" aria-hidden>
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
              <div className="feature-visual screen bc-demo" aria-hidden>
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

      {/* ——— CH5 Start Exploring ——— */}
      <section className="chapter">
        <div className="chapter-inner">
          <p className="ch-no">Start</p>
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
