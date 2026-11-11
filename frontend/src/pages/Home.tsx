import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, Capabilities, Health } from "../api";
import TitleSequence from "../components/hero/TitleSequence";
import { AstFigure, LowerFigure, RunFigure, TokensFigure } from "../components/figures/Figures";

/**
 * Landing page. One real figure up top (the hero), then three short, quiet sections:
 * the two pipelines, what can be inspected, where to start. System diagnostics sit in
 * the footer, deliberately subordinate.
 */

const C_STAGES = ["Preprocess", "Tokens", "Syntax tree", "LLVM IR", "Optimization", "Assembly", "Object + link", "Execution"];
const PY_STAGES = ["Tokens", "Syntax tree", "Code objects", "Bytecode", "Execution", "Memory + processes"];

type Chapter = { n: string; title: string; text: string };
const INSPECT: Chapter[] = [
  { n: "01", title: "Tokens", text: "The exact pieces the lexer produces, each with the kind it recorded, in Python and in C." },
  { n: "02", title: "Syntax trees", text: "Clang's own tree for one function: pick a line and the nodes it became light up." },
  { n: "03", title: "IR and bytecode", text: "LLVM IR and assembly for C, bytecode for Python, linked to your source lines." },
  { n: "04", title: "Recorded runs", text: "A sandboxed run replayed event by event: the call stack, its variables and the output." },
];

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [tools, setTools] = useState<Capabilities | null>(null);
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    api.capabilities().then(setTools).catch(() => setTools(null));
  }, []);

  // the reels run: one frame lights at a time, like a projector gate moving along the strip
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const t = setInterval(() => setTick((n) => n + 1), 1300);
    return () => clearInterval(t);
  }, []);

  const toolLine = useMemo(() => {
    if (!tools) return null;
    const avail = Object.entries(tools.tools).filter(([, v]) => v.available);
    return avail.map(([k, v]) => `${k} ${v.version.split(" ").slice(-1)[0]}`).join(" · ");
  }, [tools]);

  return (
    <main className="landing">
      <header className="hero">
        <div className="hero-copy">
          <h1><span className="hl"><span>Your program,</span></span><span className="hl"><span>cut open.</span></span></h1>
          <p className="hero-lede">
            See how code becomes execution. Real Clang/LLVM and CPython output for C and Python you bring,
            stage by stage, nothing simulated.
          </p>
          <div className="hero-ctas">
            <Link to="/demos" className="btn primary big">Explore the demos</Link>
            <Link to="/workspace" className="btn big">Paste your own code</Link>
          </div>
        </div>
        <TitleSequence />
        <p className="credits" role="note">
          <span>Clang/LLVM 18</span><span>CPython 3.12</span><span>Docker sandbox</span><span>SHA-256 on every stage</span>
        </p>
      </header>

      <section className="strips" aria-labelledby="sec-roads">
        <h2 id="sec-roads">Compiled or interpreted, your code is transformed before it runs.</h2>
        {[["C", "Clang/LLVM 18", C_STAGES], ["Python", "CPython 3.12", PY_STAGES]].map(([name, tool, stages]) => (
          <div className="strip" key={name as string}>
            <p className="strip-h"><b>{name as string}</b> <span>{tool as string}</span></p>
            <ol className="frames">
              {(stages as string[]).map((st, i) => <li key={st} data-on={tick % (stages as string[]).length === i + (name === "C" ? 0 : 0) ? "" : undefined}><span>{st}</span></li>)}
            </ol>
          </div>
        ))}
      </section>

      <section className="cards" aria-labelledby="sec-inspect">
        <h2 id="sec-inspect" className="sr-only">What you can inspect</h2>
        {INSPECT.map((c, i) => (
          <article key={c.n} id={`stage-${c.n}`} className="card" data-wide={c.n === "02" ? "" : undefined} data-tone={["cream", "ink", "cobalt", "saffron"][i % 4]}>
            <div className="card-in">
              <div className="ch-text">
                <h3>{c.title}</h3>
                <p>{c.text}</p>
              </div>
              {c.n === "01" ? <TokensFigure /> : c.n === "02" ? <AstFigure /> : c.n === "03" ? <LowerFigure /> : <RunFigure />}
            </div>
          </article>
        ))}
      </section>

      <section className="roll" aria-label="what was measured">
        <p>
          <b>76 of 76</b> metrics match an independent oracle. <b>Twenty</b> real programs to take apart.
          <b> Zero</b> bytes leave your machine.
        </p>
      </section>

      <section className="sec" aria-labelledby="sec-start">
        <h2 id="sec-start">Pick a way in.</h2>
        <ul className="start start-row">
          <li><Link to="/demos"><span className="st-t">Demo Library</span><span className="st-d">Twenty curated programs, each with a guided path through real artifacts.</span><svg className="st-a" viewBox="0 0 24 24" aria-hidden><path d="M3 12h17M13 5l7 7-7 7" /></svg></Link></li>
          <li><Link to="/workspace"><span className="st-t">Workspace</span><span className="st-d">Paste code, upload files or import a public repository as a read-only snapshot.</span><svg className="st-a" viewBox="0 0 24 24" aria-hidden><path d="M3 12h17M13 5l7 7-7 7" /></svg></Link></li>
          <li><Link to="/compare"><span className="st-t">Compare</span><span className="st-d">The same idea in C and in Python, run through both pipelines side by side.</span><svg className="st-a" viewBox="0 0 24 24" aria-hidden><path d="M3 12h17M13 5l7 7-7 7" /></svg></Link></li>
          <li><Link to="/about"><span className="st-t">Method and limits</span><span className="st-d">How the honesty contract works, what was measured, and what it does not do.</span><svg className="st-a" viewBox="0 0 24 24" aria-hidden><path d="M3 12h17M13 5l7 7-7 7" /></svg></Link></li>
        </ul>
      </section>

      <section className="cta-band" aria-label="get started">
        <div className="cta-inner">
          <p className="cta-h">Open a program and look inside.</p>
          <Link to="/demos" className="btn big">Explore the demos</Link>
        </div>
      </section>

      <footer className="site-footer">
        <div className="footer-inner">
          <div className="foot-col foot-sys">
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
              Explore mode shows the journey; Technical mode (top right) reveals provenance, digests
              and raw artifacts. Execution is restricted to curated programs in sandboxed containers;
              imported repository code is never executed.
            </p>
          </div>
          <nav className="foot-col" aria-label="product">
            <span className="label">Product</span>
            <Link to="/demos">Demo Library</Link>
            <Link to="/workspace">Workspace</Link>
            <Link to="/compare">Compare</Link>
          </nav>
          <nav className="foot-col" aria-label="method">
            <span className="label">Method</span>
            <Link to="/about">About and limits</Link>
          </nav>
        </div>
      </footer>
    </main>
  );
}
