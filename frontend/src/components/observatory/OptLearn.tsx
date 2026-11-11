import { useEffect, useMemo, useState } from "react";
import { experiments, LineMap } from "../../api";
import { asmSentence, irSentence, Kind, kindOf, KIND_LABEL, lessonSteps, quizRows as pickQuizRows } from "./optLearnModel";

/**
 * Learning layer over the real -O0 vs -O2 line map: a per-line diff, a step-by-step lesson
 * and a predict-then-reveal quiz. Every number and every instruction shown comes from the
 * compiler output already stored for this experiment (debug-info line map). The lesson text
 * states WHAT changed (counts, instructions) and never claims WHY: the compiler does not
 * record per-pass reasons in this data.
 */
export type LearnView = "off" | "diff" | "lesson" | "quiz";
type Cmp = NonNullable<LineMap["compare_O0_O2"]>;
const KIND_BADGE: Record<Kind, string> = {
  removed: "blocked", shrunk: "derived", grown: "ok", new: "ok", same: "",
};

/** Real asm/IR text for the lines a source line produced at one level. */
function useLevelText(experimentId: string, level: string) {
  const [t, setT] = useState<{ ir: string[]; asm: string[] } | null>(null);
  useEffect(() => {
    let alive = true;
    setT(null);
    Promise.all([
      experiments.artifact(experimentId, level, "ir").then((a) => a.excerpt.split("\n")),
      experiments.artifact(experimentId, level, "asm").then((a) => a.excerpt.split("\n")),
    ]).then(([ir, asm]) => { if (alive) setT({ ir, asm }); }).catch(() => { if (alive) setT(null); });
    return () => { alive = false; };
  }, [experimentId, level]);
  return t;
}

export function shareLink(view: LearnView, line: number | null, step?: number): string {
  const u = new URL(window.location.href);
  u.searchParams.set("view", view);
  if (line != null) u.searchParams.set("line", String(line)); else u.searchParams.delete("line");
  if (step != null) u.searchParams.set("step", String(step)); else u.searchParams.delete("step");
  return u.toString();
}

export default function OptLearn({ experimentId, map, srcLines, view, line, setLine, setFocus }: {
  experimentId: string; map: LineMap; srcLines: string[]; view: LearnView;
  line: number | null; setLine: (n: number | null) => void;
  setFocus: (f: "source" | "ir" | "asm" | null) => void;
}) {
  const cmp = map.compare_O0_O2;
  const o0 = useLevelText(experimentId, "O0");
  const o2 = useLevelText(experimentId, "O2");
  const [copied, setCopied] = useState(false);
  const params = new URLSearchParams(window.location.search);
  const [stepIdx, setStepIdx] = useState(() => Number(params.get("step")) || 0);
  const [phase, setPhase] = useState(0); // 0 source, 1 IR, 2 asm
  const [quizPos, setQuizPos] = useState(0);
  const [picked, setPicked] = useState<Kind | null>(null);
  const [score, setScore] = useState<[number, number]>([0, 0]);
  const [onlyChanged, setOnlyChanged] = useState(true);

  const changed = useMemo(() => (cmp?.rows ?? []).filter((r) => kindOf(cmp!, r.line) !== "same"), [cmp]);
  const steps = useMemo(() => (cmp ? lessonSteps(cmp) : []), [cmp]);
  // quiz: lines that have asm at -O0 (so a prediction is meaningful)
  const quizRows = useMemo(() => (cmp ? pickQuizRows(cmp) : []), [cmp]);
  const qRow = quizRows.length ? quizRows[(quizPos * 7 + 3) % quizRows.length] : undefined;

  // keep the shared line/focus in step with the lesson
  useEffect(() => {
    if (view !== "lesson") return;
    const s = steps[stepIdx];
    setLine(s ? s.line : null);
    setFocus(phase === 0 ? "source" : phase === 1 ? "ir" : "asm");
    return () => setFocus(null);
  }, [view, stepIdx, phase, steps]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (view !== "quiz") return;
    setLine(picked && qRow ? qRow.line : null);
    setFocus(null);
  }, [view, picked, qRow]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!cmp || view === "off") return null;

  const copy = async (step?: number) => {
    try {
      await navigator.clipboard.writeText(shareLink(view, line, step));
      setCopied(true); setTimeout(() => setCopied(false), 1800);
    } catch { window.prompt("Copy this link", shareLink(view, line, step)); }
  };

  const lineText = (n: number) => (srcLines[n - 1] ?? "").trim();
  const instrs = (t: { asm: string[] } | null, lm: LineMap["levels"][string] | undefined, n: number) => {
    if (!t || !lm) return null;
    const idx = lm.by_source[String(n)]?.asm ?? [];
    return idx.slice(0, 14).map((i) => (t.asm[i - 1] ?? "").trim());
  };
  const side = (n: number) => {
    const a = instrs(o0, map.levels.O0, n), b = instrs(o2, map.levels.O2, n);
    const ca = map.levels.O0?.by_source[String(n)]?.asm.length ?? 0;
    const cb = map.levels.O2?.by_source[String(n)]?.asm.length ?? 0;
    return (
      <div className="ol-side" aria-label={`assembly for source line ${n}`}>
        <div><h6>-O0 · {ca} asm</h6>
          <pre tabIndex={0}>{a ? (a.length ? a.join("\n") + (ca > a.length ? `\n… +${ca - a.length} more` : "") : "(no instructions)") : "loading…"}</pre></div>
        <div><h6>-O2 · {cb} asm</h6>
          <pre tabIndex={0}>{b ? (b.length ? b.join("\n") + (cb > b.length ? `\n… +${cb - b.length} more` : "") : "(no instructions)") : "loading…"}</pre></div>
      </div>
    );
  };

  if (view === "diff") {
    const rows = onlyChanged ? changed : cmp.rows;
    const max = Math.max(1, ...cmp.rows.map((r) => Math.max(r.asm[0], r.asm[1])));
    return (
      <section className="ol" aria-label="-O0 versus -O2 per-line diff">
        <div className="ol-head">
          <h5>What -O2 did to every source line</h5>
          <span className="muted">asm instructions linked to each line, -O0 vs -O2 (counts, not reasons)</span>
          <span className="spacer" />
          <label className="muted"><input type="checkbox" checked={onlyChanged}
            onChange={(e) => setOnlyChanged(e.target.checked)} /> only changed lines</label>
          <button className="btn" onClick={() => copy()}>{copied ? "Link copied" : "Copy link to this view"}</button>
        </div>
        <div className="ol-sum">
          <span className="badge blocked">no code ×{cmp.removed.length}</span>
          <span className="badge derived">fewer ×{cmp.shrunk.length}</span>
          <span className="badge ok">more ×{cmp.grown.length}</span>
          <span className="badge ok">new ×{cmp.new.length}</span>
          <span className="muted">total asm {cmp.totals.asm[0]} → {cmp.totals.asm[1]} · IR {cmp.totals.ir[0]} → {cmp.totals.ir[1]}</span>
        </div>
        <div className="ol-rows" role="list">
          {rows.map((r) => {
            const k = kindOf(cmp, r.line);
            return (
              <button key={r.line} role="listitem" className={"ol-row k-" + k + (line === r.line ? " hit" : "")}
                      onClick={() => setLine(line === r.line ? null : r.line)} aria-pressed={line === r.line}>
                <span className="ol-n">{r.line}</span>
                <code className="ol-src">{lineText(r.line) || " "}</code>
                <span className="ol-bars" aria-hidden="true">
                  <i className="b0" style={{ width: `${(r.asm[0] / max) * 100}%` }} />
                  <i className="b2" style={{ width: `${(r.asm[1] / max) * 100}%` }} />
                </span>
                <span className="ol-num">{r.asm[0]} → {r.asm[1]}</span>
                <span className={"badge " + KIND_BADGE[k]}>{KIND_LABEL[k]}</span>
              </button>
            );
          })}
          {rows.length === 0 && <p className="muted">No line changed its assembly count between -O0 and -O2.</p>}
        </div>
        {line != null && side(line)}
      </section>
    );
  }

  if (view === "lesson") {
    if (!steps.length) {
      return <section className="ol"><p className="muted">This program has no per-line differences between -O0 and -O2 to walk through.</p></section>;
    }
    const s = steps[Math.min(stepIdx, steps.length - 1)];
    const k = kindOf(cmp, s.line);
    const phaseText = [
      `Source line ${s.line}: ${lineText(s.line) || "(blank)"}`,
      irSentence(s),
      asmSentence(s, k),
    ];
    const last = stepIdx >= steps.length - 1 && phase === 2;
    const next = () => { if (phase < 2) setPhase(phase + 1); else if (stepIdx < steps.length - 1) { setStepIdx(stepIdx + 1); setPhase(0); } };
    const prev = () => { if (phase > 0) setPhase(phase - 1); else if (stepIdx > 0) { setStepIdx(stepIdx - 1); setPhase(2); } };
    return (
      <section className="ol" aria-label="guided lesson">
        <div className="ol-head">
          <h5>Guided lesson: what did -O2 change?</h5>
          <span className="muted">step {stepIdx + 1} of {steps.length} · stage {phase + 1} of 3 (source → IR → assembly)</span>
          <span className="spacer" />
          <button className="btn" onClick={() => copy(stepIdx)}>{copied ? "Link copied" : "Copy link to this step"}</button>
        </div>
        <ol className="ol-phases" aria-label="stages">
          {["Source", "LLVM IR", "Assembly"].map((p, i) => (
            <li key={p} className={i === phase ? "on" : i < phase ? "done" : ""}>{p}</li>
          ))}
        </ol>
        <p className="ol-say" aria-live="polite">{phaseText[phase]}</p>
        {phase === 2 && side(s.line)}
        <div className="ol-nav">
          <button className="btn" onClick={prev} disabled={stepIdx === 0 && phase === 0}>← Back</button>
          <button className="btn primary" onClick={next} disabled={last}>{last ? "End of lesson" : "Next →"}</button>
          <button className="btn" onClick={() => { setStepIdx(0); setPhase(0); }}>Restart</button>
        </div>
      </section>
    );
  }

  // quiz
  if (!qRow) return <section className="ol"><p className="muted">No lines with code to quiz on.</p></section>;
  const truth = kindOf(cmp, qRow.line);
  const options: Kind[] = ["removed", "shrunk", "same", "grown"];
  const answer = (k: Kind) => {
    if (picked) return;
    setPicked(k);
    setScore(([r, n]) => [r + (k === truth ? 1 : 0), n + 1]);
  };
  return (
    <section className="ol" aria-label="predict then reveal quiz">
      <div className="ol-head">
        <h5>Predict, then reveal</h5>
        <span className="muted">score {score[0]} / {score[1]}</span>
        <span className="spacer" />
        <button className="btn" onClick={() => copy()}>{copied ? "Link copied" : "Copy link"}</button>
      </div>
      <p className="ol-say">Source line {qRow.line}: <code>{lineText(qRow.line)}</code></p>
      <p>At -O2, compared with -O0, how many assembly instructions does this line link to?</p>
      <div className="ol-opts" role="group" aria-label="your prediction">
        {options.map((k) => (
          <button key={k} className={"btn" + (picked === k ? " picked" : "") + (picked && k === truth ? " right" : "")}
                  disabled={!!picked} onClick={() => answer(k)}>{KIND_LABEL[k]}</button>
        ))}
      </div>
      {picked && (
        <div aria-live="polite">
          <p className={picked === truth ? "ol-ok" : "ol-no"}>
            {picked === truth ? "Correct." : "Not quite."} The real build shows {qRow.asm[0]} → {qRow.asm[1]} asm
            instructions ({KIND_LABEL[truth]}) and {qRow.ir[0]} → {qRow.ir[1]} IR instructions.
          </p>
          {side(qRow.line)}
          <button className="btn primary" onClick={() => { setPicked(null); setQuizPos(quizPos + 1); }}>Next question →</button>
        </div>
      )}
    </section>
  );
}
