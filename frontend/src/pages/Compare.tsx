import { useState } from "react";
import { Link } from "react-router-dom";
import { PairSpec, api, experiments, pairs } from "../api";

/**
 * Dual-Language Observatory — the two pipelines shown as what they are: two
 * independent machines synchronized by concept, never by equivalence. The C
 * rail (Source → Tokens → AST → LLVM IR → Assembly → Runtime, Clang/LLVM) and
 * the Python rail (Source → Tokens → AST → Bytecode → Interpreter, CPython)
 * are drawn as separate chains with an explicitly UNALIGNED middle. Sources,
 * run outputs and observatory deep-links let the user inspect each language's
 * real artifacts on its own terms.
 */

const C_STAGES = ["Source", "Tokens", "AST", "LLVM IR", "Assembly", "Runtime"];
const PY_STAGES = ["Source", "Tokens", "AST", "Bytecode", "Interpreter"];

/** Honest per-concept semantic notes (static copy — no data claims). */
function diffNote(concept: string): string {
  const c = concept.toLowerCase();
  if (c.includes("recursion")) {
    return "C recursion uses the native call stack with a fixed depth budget; Python raises RecursionError at its own (higher, adjustable) limit. Frames carry different data — C locals live in stack memory, Python frames are heap objects.";
  }
  if (c.includes("branch") || c.includes("conditional")) {
    return "C branching compiles to conditional jumps in machine code; Python compiles to POP_JUMP_* bytecodes over an evaluation stack. Same semantics, different machines.";
  }
  if (c.includes("collection") || c.includes("list") || c.includes("loop")) {
    return "C loops index raw memory with an integer; Python lists are heap objects of object references looped by the iterator protocol. Bounds behavior differs: C does not check, Python raises IndexError.";
  }
  if (c.includes("sort")) {
    return "The C side shows explicit swap logic over an array; Python's sort lives in the runtime (Timsort). Comparing 'the same algorithm' here means the same observable behavior, not the same code path.";
  }
  return "Integer width, memory management and error behavior differ: C's int is a fixed-width machine word, Python's int is arbitrary precision; C memory is yours to manage, Python's is reference-counted and garbage-collected.";
}

export default function Compare() {
  const [specs, setSpecs] = useState<PairSpec[] | null>(null);
  const [selected, setSelected] = useState<PairSpec | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [expId, setExpId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deepLinks, setDeepLinks] = useState<{ c: string | null; py: string | null }>({ c: null, py: null });

  if (specs === null) {
    pairs.list().then((p) => setSpecs(p.pairs)).catch((e) => setError(String(e)));
    return <main className="compare"><p className="muted"><span className="spinner" /> loading pair specs…</p></main>;
  }

  const runPair = async (pair: PairSpec) => {
    setError(null); setResult(null); setStatus("running"); setDeepLinks({ c: null, py: null });
    setSelected(pair);
    try {
      if (!pair.c_source || !pair.py_source) throw new Error("pair sources unavailable");
      const c = await api.createSnapshotFromPaste("c", pair.c_file, pair.c_source);
      const py = await api.createSnapshotFromPaste("python", pair.py_file, pair.py_source);
      // analysis deep-links: both sides analyzed so every stage is inspectable
      const link = async (snap: { snapshot_id: string; target_id: string }, file: string, lang: string) => {
        try {
          const a = await api.createAnalysis(snap.snapshot_id, snap.target_id);
          return `/workspace?analysis=${a.analysis_id}&snapshot=${snap.snapshot_id}&file=${encodeURIComponent(file)}&side=${lang}`;
        } catch { return null; }
      };
      const [cl, pyl] = await Promise.all([link(c, pair.c_file, "c"), link(py, pair.py_file, "python")]);
      setDeepLinks({ c: cl, py: pyl });
      const ref = await experiments.create({
        kind: "compare", config: {
          pair_id: pair.id,
          c: { snapshot_id: c.snapshot_id, target_id: c.target_id },
          python: { snapshot_id: py.snapshot_id, target_id: py.target_id },
        },
      });
      const id = ref.experiment_id ?? "";
      setExpId(id);
      for (let i = 0; i < 300; i++) {
        const e = await experiments.get(id);
        setStatus(e.status);
        if (["COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BLOCKED"].includes(e.status)) {
          setResult((e.stages.find((s) => s.stage === "compare")?.result ?? {}) as Record<string, unknown>);
          return;
        }
        await new Promise((r) => setTimeout(r, 1000));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStatus(null);
    }
  };

  const sides = (result?.sides ?? {}) as Record<string, Record<string, unknown>>;

  const StageChain = ({ stages, side }: { stages: string[]; side: "c" | "py" }) => (
    <ol className={`stagechain ${side}`} aria-label={`${side} pipeline`}>
      {stages.map((s, i) => (
        <li key={s}>
          {i > 0 && <span className="sc-arrow" aria-hidden>→</span>}
          <span className="sc-stage">{s}</span>
        </li>
      ))}
    </ol>
  );

  const SourcePane = ({ src, file, side }: { src: string; file: string; side: "c" | "py" }) => (
    <div className={`srcpane ${side}`} aria-label={`${side} source`}>
      <div className="srcpane-h">
        <span className={`langbadge ${side === "c" ? "c" : "python"}`}>{side}</span>
        <code>{file}</code>
      </div>
      <div className="srcpane-body">
        {src.split("\n").map((l, i) => (
          <div key={i} className="srcpane-row">
            <span className="srcpane-no">{i + 1}</span>
            <code>{l || "\u200b"}</code>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <main className="compare">
      <div className="cmp-head">
        <p className="dl-eyebrow">Dual-Language Observatory</p>
        <h1>The same idea, two machines.</h1>
        <p className="muted">
          Two <b>independent</b> pipelines — Clang/LLVM 18 and CPython 3.12 — synchronized by
          concept. The middle stages are deliberately <b>not aligned</b>: LLVM IR is a typed SSA
          representation for a compiler backend; CPython bytecode is a stack-machine program for
          an interpreter. Pretending otherwise would be the most misleading thing this page
          could do. Python has no LLVM -O levels.
        </p>
      </div>

      <div className="cmp-pairs">
        {specs.map((p) => (
          <button key={p.id} className={"paircard panel" + (selected?.id === p.id ? " active" : "")}
                  onClick={() => runPair(p)} disabled={status === "running"}>
            <code>{p.id}</code>
            <h3>{p.concept}</h3>
            <p className="muted">expected output: <code>{p.expected_stdout}</code></p>
            <span className="dc-open">{status === "running" && selected?.id === p.id ? "running both pipelines…" : "Run both pipelines →"}</span>
          </button>
        ))}
      </div>

      {error && <p className="err" role="alert">{error}</p>}
      {status && status !== "COMPLETED" && (
        <p className="notice"><span className="spinner" /> experiment: {status}…</p>
      )}

      {selected && (
        <section className="cmp-dual">
          <h2>Two pipelines, one concept <span className="chip">{selected.id}</span></h2>
          <div className="dualmap bezel">
            <div className="dualmap-row">
              <div className="dualmap-label"><span className="world-dot c" />C — compiled</div>
              <StageChain stages={C_STAGES} side="c" />
            </div>
            <div className="dualmap-gap" aria-hidden>
              <span className="dm-note">concept sync</span>
              <span className="dm-noalign">— no equivalent stage —</span>
            </div>
            <div className="dualmap-row">
              <div className="dualmap-label"><span className="world-dot py" />Python — interpreted</div>
              <StageChain stages={PY_STAGES} side="py" />
            </div>
          </div>
          <p className="muted dualmap-note">
            Source, tokens and AST exist in both languages and are compared by concept. The middle
            rows cannot be aligned: <b>LLVM IR / assembly</b> describe one compilation strategy,
            <b> CPython bytecode</b> another. Click a rail below to inspect either pipeline's real
            artifacts in the observatory.
          </p>

          <div className="cmp-sources">
            {selected.c_source && <SourcePane src={selected.c_source} file={selected.c_file} side="c" />}
            {selected.py_source && <SourcePane src={selected.py_source} file={selected.py_file} side="py" />}
          </div>
          <div className="cmp-diffnote panel">
            <div className="panel-h">What actually differs here</div>
            <p style={{ padding: "10px 16px 14px" }}>{diffNote(selected.concept)}</p>
          </div>
        </section>
      )}

      {result && selected && (
        <div className="cmp-rails">
          <p className={"cmp-verdict " + (result.match ? "ok" : "err")}>
            {result.match ? "✓ both rails produced the expected output" : "✗ mismatch — inspect the rails"}
            {expId ? <span className="muted"> · experiment {expId}</span> : null}
          </p>
          <div className="cmp-grid">
            {(["c", "python"] as const).map((side) => {
              const s = sides[side] ?? {};
              const link = side === "c" ? deepLinks.c : deepLinks.py;
              return (
                <div className={"rail panel " + side} key={side} role="group" aria-label={`${side} rail`}>
                  <div className="rail-h">
                    <span className={`langbadge ${side === "c" ? "c" : "python"}`}>{side}</span>
                    <h3>{side === "c" ? "Clang 18.1.3 pipeline" : "CPython 3.12 pipeline"}</h3>
                    <span className="spacer" />
                    {s.expected_match
                      ? <span className="badge ok">matches expected</span>
                      : <span className="badge blocked">mismatch/absent</span>}
                  </div>
                  <div className="rail-stats">
                    <span className="chip">status {String(s.status ?? "—")}</span>
                    <span className="chip">exit {String(s.exit_code ?? "—")}</span>
                    <span className="chip">{String(s.duration_ms ?? "—")} ms container wall</span>
                  </div>
                  <pre className="excerpt">{String(s.stdout ?? "(no stdout)")}</pre>
                  <p className="muted rail-note">
                    Container wall time includes runtime startup — <b>not comparable</b> between
                    languages and <b>not</b> an algorithm benchmark.
                    {link
                      ? <> <Link to={link}>Open the {side === "c" ? "C" : "Python"} pipeline in the observatory →</Link></>
                      : null}
                  </p>
                </div>
              );
            })}
          </div>
          <p className="muted">
            Both rails must produce the expected output for a match — but the languages remain
            independently implemented: different runtimes, different memory models, different
            compilation stories. Timing comparisons belong to OptimizationLab benchmarks (C only)
            or the recorded per-run durations, never container wall clocks.
          </p>
        </div>
      )}
    </main>
  );
}
