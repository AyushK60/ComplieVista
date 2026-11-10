import { Link } from "react-router-dom";
import { Icon, InfoTip } from "../ui";

/**
 * About / Method. The place where the honesty contract, the measured results and the
 * limitations live, so the working views can stay clean. Every number here comes from a
 * file in the repository (eval/results, docs/REPORT.md); nothing is estimated.
 */

function Architecture() {
  const box = (x: number, y: number, w: number, h: number, title: string, sub: string, cls = "") => (
    <g className={`ar-box ${cls}`}>
      <rect x={x} y={y} width={w} height={h} rx={9} />
      <text x={x + w / 2} y={y + h / 2 - 4} textAnchor="middle" className="ar-t">{title}</text>
      <text x={x + w / 2} y={y + h / 2 + 14} textAnchor="middle" className="ar-s">{sub}</text>
    </g>
  );
  const arrow = (x1: number, y1: number, x2: number, y2: number) => (
    <path d={`M${x1} ${y1} L${x2} ${y2}`} className="ar-line" markerEnd="url(#ar-head)" />
  );
  return (
    <svg viewBox="0 0 760 300" className="arch" role="img"
         aria-label="Architecture: the browser app talks to a FastAPI backend, which stores results and runs the toolchains inside three Docker images.">
      <defs>
        <marker id="ar-head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" fill="currentColor" />
        </marker>
      </defs>
      {box(20, 110, 150, 70, "Browser app", "React · TypeScript", "ar-ui")}
      {box(230, 110, 170, 70, "FastAPI backend", "routes · services", "ar-api")}
      {box(230, 220, 170, 56, "Store", "SQLite + digest-addressed files", "ar-store")}
      {box(480, 20, 250, 62, "analyzer image", "Clang/LLVM 18 · CPython 3.12 (static)", "ar-box-run")}
      {box(480, 120, 250, 62, "runtime image", "restricted run · recorded events", "ar-box-run")}
      {box(480, 220, 250, 56, "debug image", "curated C fixtures only", "ar-box-run")}
      {arrow(170, 145, 228, 145)}
      {arrow(315, 182, 315, 218)}
      {arrow(400, 135, 478, 52)}
      {arrow(400, 145, 478, 151)}
      {arrow(400, 160, 478, 245)}
    </svg>
  );
}

export default function About() {
  return (
    <main className="about">
      <header className="about-head">
        <p className="dl-eyebrow">About and method</p>
        <h1>Real artifacts, labelled honestly.</h1>
        <p className="about-lede">
          CompileVista shows what Clang/LLVM 18 and CPython 3.12 actually produce for your program.
          When a tool does not provide something, the interface says so instead of filling the gap.
        </p>
      </header>

      <section aria-labelledby="ab-contract">
        <h2 id="ab-contract">The honesty contract</h2>
        <div className="about-grid three">
          <div className="about-card"><b>Recorded, never invented</b>
            <p>Tokens, syntax trees, IR, assembly, bytecode and execution events come from the tools themselves.
              Each stage records the tool and version, the invocation, the exit code and a SHA-256 of its output.</p></div>
          <div className="about-card"><b>Labelled by how we know</b>
            <p><span className="badge exact">Exact</span> is the tool's own output. <span className="badge derived">Derived</span> is
              computed from exact data. <span className="badge unavailable">Not available</span> means no source exists, so none is shown.</p></div>
          <div className="about-card"><b>Two pipelines, not one</b>
            <p>Python bytecode is not machine code, and Python has no LLVM optimization levels. The two languages
              are compared by concept and never pretended equal.</p></div>
        </div>
      </section>

      <section aria-labelledby="ab-fidelity">
        <h2 id="ab-fidelity">Fidelity result
          <InfoTip label="What does this measure?">For each demo program, CompileVista's displayed counts were compared with the same counts computed
            independently by the host toolchain. It checks counts, not that every character of the artifact is identical.</InfoTip></h2>
        <div className="about-stats">
          <div><strong>76 / 76</strong><span>metrics equal to an independent oracle</span></div>
          <div><strong>19</strong><span>single-file demo and pair programs, C and Python</span></div>
          <div><strong>0</strong><span>mismatches in the final run</span></div>
        </div>
        <p className="about-note">Counted: tokens, syntax-tree nodes, bytecode instructions and code objects for Python; tokens, IR functions
          at -O0 and -O2, and assembly lines for C. The C token view is capped at 8000 tokens by design (one program).
          The multi-file project (C-05) is not covered. Data and script: <code>eval/results/fidelity.md</code>, <code>eval/fidelity_study.py</code>.</p>
      </section>

      <section aria-labelledby="ab-arch">
        <h2 id="ab-arch">Architecture</h2>
        <div className="about-fig"><Architecture /></div>
        <p className="about-note">Your code is stored as an immutable snapshot. Analysis never executes it. Running happens only in containers with no network,
          a read-only filesystem, dropped capabilities, resource limits and a non-root user.</p>
      </section>

      <section aria-labelledby="ab-limits">
        <h2 id="ab-limits">What it does not do</h2>
        <ul className="about-limits">
          <li><Icon name="alert" size={15} /> C execution is recorded at function level only; line stepping is available for Python.</li>
          <li><Icon name="alert" size={15} /> The -O0 / -O2 comparison reports what changed per source line, never why the optimizer did it.</li>
          <li><Icon name="alert" size={15} /> Python memory and process views are observed during an instrumented run; they are not a debugger.</li>
          <li><Icon name="alert" size={15} /> It is a local, single-user tool, not a hosted service. Nothing is sent anywhere.</li>
          <li><Icon name="alert" size={15} /> Accessibility was checked by machine (axe-core, 0 violations on 12 screens); there was no manual screen-reader audit.</li>
          <li><Icon name="alert" size={15} /> No usability study with participants has been run yet; the protocol is in <code>docs/USABILITY_STUDY.md</code>.</li>
        </ul>
      </section>

      <section className="about-cta" aria-label="next steps">
        <Link className="btn primary" to="/demos">Open the Demo Library</Link>
        <Link className="btn" to="/workspace">Paste your own code</Link>
      </section>
    </main>
  );
}
