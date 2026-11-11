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

const INSPECT: Array<[string, string, string]> = [
  ["01", "Tokens", "The exact pieces the lexer produces, each with its kind and source position."],
  ["02", "Syntax trees", "The parser's tree, laid out so you can zoom, collapse and click a node back to its line."],
  ["03", "IR and bytecode", "LLVM IR and assembly for C, code objects and bytecode for Python, linked to your source lines."],
  ["04", "Recorded runs", "A sandboxed run replayed event by event: call stack, variables, memory and output."],
];

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
      <SpecimenHero />

      <section className="sec" aria-labelledby="sec-roads">
        <p className="sec-no">The pipelines</p>
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
        <p className="sec-no">What you can inspect</p>
        <h2 id="sec-inspect">Each stage is the tool's own output, never a redrawing.</h2>
        <ol className="inspect">
          {INSPECT.map(([n, t, d]) => (
            <li key={n}><span className="ins-n">{n}</span><h3>{t}</h3><p>{d}</p></li>
          ))}
        </ol>
      </section>

      <section className="sec" aria-labelledby="sec-start">
        <p className="sec-no">Start</p>
        <h2 id="sec-start">Pick a way in.</h2>
        <ul className="start">
          <li><Link to="/demos"><span className="st-t">Demo Library</span><span className="st-d">Twenty curated programs, each with a guided path through real artifacts.</span><span className="st-a" aria-hidden>→</span></Link></li>
          <li><Link to="/workspace"><span className="st-t">Workspace</span><span className="st-d">Paste code, upload files or import a public repository as a read-only snapshot.</span><span className="st-a" aria-hidden>→</span></Link></li>
          <li><Link to="/compare"><span className="st-t">Compare</span><span className="st-d">The same idea in C and in Python, run through both pipelines side by side.</span><span className="st-a" aria-hidden>→</span></Link></li>
          <li><Link to="/about"><span className="st-t">Method and limits</span><span className="st-d">How the honesty contract works, what was measured, and what it does not do.</span><span className="st-a" aria-hidden>→</span></Link></li>
        </ul>
      </section>

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
            Explore mode shows the journey; Technical mode (top right) reveals provenance, digests
            and raw artifacts. Execution is restricted to curated programs in sandboxed containers;
            imported repository code is never executed.
          </p>
        </div>
      </footer>
    </main>
  );
}
