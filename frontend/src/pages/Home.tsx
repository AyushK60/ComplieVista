import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, Capabilities, Health } from "../api";
import SpecimenHero from "../components/hero/SpecimenHero";

/**
 * Landing page. One real figure up top (the hero), then three short, quiet sections:
 * the two pipelines, what can be inspected, where to start. System diagnostics sit in
 * the footer, deliberately subordinate.
 */

const C_STAGES = ["Preprocess", "Tokens", "Syntax tree", "LLVM IR", "Optimization", "Assembly", "Object + link", "Execution"];
const PY_STAGES = ["Tokens", "Syntax tree", "Code objects", "Bytecode", "Execution", "Memory + processes"];

type Chapter = { n: string; title: string; text: string; src: string; w: number; h: number; alt: string; cap: string; dark?: string };
const INSPECT: Chapter[] = [
  { n: "01", title: "Tokens", text: "The exact pieces the lexer produces, each with its kind and source position.",
    src: "/media/tokens.jpg", w: 966, h: 163, alt: "Python source line 9 to 11 split into tokens: def, accumulate, parentheses, names and numbers, each in its own box.",
    cap: "Real output · PY-02 · CPython tokenize" },
  { n: "02", title: "Syntax trees", text: "The parser's tree, laid out so you can zoom, collapse and click a node back to its line.",
    src: "/media/ast.jpg", w: 1012, h: 829, alt: "A syntax tree graph: a FunctionDef node named accumulate selected, with its children Assign, For and Return on the right.",
    cap: "Real output · PY-02 · ast.parse" },
  { n: "03", title: "IR and bytecode", text: "LLVM IR and assembly for C, code objects and bytecode for Python, linked to your source lines.",
    src: "/media/bytecode.jpg", w: 958, h: 481, alt: "Python bytecode instructions grouped by source line, with jump arcs on the left.",
    cap: "Real output · PY-02 · dis (C shows IR and assembly the same way)" },
  { n: "04", title: "Recorded runs", text: "A sandboxed run replayed event by event: call stack, variables, memory and output.",
    src: "/media/run-light.jpg", dark: "/media/run-dark.jpg", w: 1000, h: 470, alt: "The execution observatory: a call structure with the module and accumulate calls, a stack scene and a replay bar.",
    cap: "Real output · PY-02 · sys.settrace in a sandbox" },
];

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [tools, setTools] = useState<Capabilities | null>(null);
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    api.capabilities().then(setTools).catch(() => setTools(null));
  }, []);

  // sections fade up once as they enter the view (honours reduced motion through the base rule)
  useEffect(() => {
    if (!("IntersectionObserver" in window)) return;
    const els = Array.from(document.querySelectorAll<HTMLElement>(".landing .reveal"));
    els.forEach((e) => e.classList.add("rv-hide"));
    const io = new IntersectionObserver((entries) => entries.forEach((en) => {
      if (en.isIntersecting) { en.target.classList.remove("rv-hide"); io.unobserve(en.target); }
    }), { threshold: 0.12 });
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  }, []);

  const toolLine = useMemo(() => {
    if (!tools) return null;
    const avail = Object.entries(tools.tools).filter(([, v]) => v.available);
    return avail.map(([k, v]) => `${k} ${v.version.split(" ").slice(-1)[0]}`).join(" · ");
  }, [tools]);

  return (
    <main className="landing">
      <SpecimenHero />

      <div className="builton" role="note">
        <span className="label">Built on</span>
        <span>Clang/LLVM 18</span><span>CPython 3.12</span><span>Docker sandbox</span><span>SHA-256 per stage</span>
      </div>

      <section className="proof" aria-label="the numbers">
        <dl>
          <div><dt>76 / 76</dt><dd>metrics match an independent oracle</dd></div>
          <div><dt>20</dt><dd>real programs to take apart</dd></div>
          <div><dt>0</dt><dd>bytes leave your machine</dd></div>
        </dl>
      </section>

      <section className="sec reveal" aria-labelledby="sec-roads">
        <p className="sec-no">01 — The pipelines</p>
        <h2 id="sec-roads">Compiled or interpreted, your code is transformed before it runs.</h2>
        <dl className="roads">
          <div>
            <dt>C <span>Clang/LLVM 18</span></dt>
            <dd>{C_STAGES.map((s, i) => <span key={s}>{i > 0 && <i aria-hidden>→</i>}{s}</span>)}</dd>
          </div>
          <div>
            <dt>Python <span>CPython 3.12</span></dt>
            <dd>{PY_STAGES.map((s, i) => <span key={s}>{i > 0 && <i aria-hidden>→</i>}{s}</span>)}</dd>
          </div>
        </dl>
      </section>

      <section className="sec" aria-labelledby="sec-inspect">
        <div className="sec-head">
          <p className="sec-no">02 — What you can inspect</p>
          <h2 id="sec-inspect">Each stage is the tool's own output, never a redrawing.</h2>
        </div>
        <ol className="inspect">
          {INSPECT.map((c) => (
            <li key={c.n} className="reveal">
              <div className="ch-text">
                <span className="ins-n">{c.n}</span><h3>{c.title}</h3><p>{c.text}</p>
              </div>
              <figure className="ch-fig">
                <img className={c.dark ? "fig-light" : undefined} src={c.src} width={c.w} height={c.h} alt={c.alt} loading="lazy" decoding="async" />
                {c.dark && <img className="fig-dark" src={c.dark} width={c.w} height={c.h} alt="" aria-hidden loading="lazy" decoding="async" />}
                <figcaption>{c.cap}</figcaption>
              </figure>
            </li>
          ))}
        </ol>
      </section>

      <section className="sec reveal" aria-labelledby="sec-start">
        <p className="sec-no">03 — Start</p>
        <h2 id="sec-start">Pick a way in.</h2>
        <ul className="start start-row">
          <li><Link to="/demos"><span className="st-t">Demo Library</span><span className="st-d">Twenty curated programs, each with a guided path through real artifacts.</span><span className="st-a" aria-hidden>→</span></Link></li>
          <li><Link to="/workspace"><span className="st-t">Workspace</span><span className="st-d">Paste code, upload files or import a public repository as a read-only snapshot.</span><span className="st-a" aria-hidden>→</span></Link></li>
          <li><Link to="/compare"><span className="st-t">Compare</span><span className="st-d">The same idea in C and in Python, run through both pipelines side by side.</span><span className="st-a" aria-hidden>→</span></Link></li>
          <li><Link to="/about"><span className="st-t">Method and limits</span><span className="st-d">How the honesty contract works, what was measured, and what it does not do.</span><span className="st-a" aria-hidden>→</span></Link></li>
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
