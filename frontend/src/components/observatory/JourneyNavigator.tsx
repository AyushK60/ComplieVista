import { AnalysisJob } from "../../api";
import { STAGE_BLURBS } from "./types";

/**
 * Journey Navigator - the spatially-ordered pipeline of the selected program.
 * Stages come verbatim from the analysis job (never invented); availability
 * and observation class are shown honestly. Stages are grouped into real
 * pipeline phases so the navigator reads as a journey, not a row of tabs.
 * Guided mode steps concept-level through AVAILABLE stages.
 */
const STAGE_ORDER_HINT = [
  "preprocess", "tokens", "ast", "code_object", "bytecode",
  "ir_o0", "ir_o2", "assembly", "disassembly", "object", "symbols", "diagnostics",
];

const C_PHASES: Array<[string, string[]]> = [
  ["Frontend - reading your C", ["preprocess", "tokens", "ast", "diagnostics"]],
  ["Middle end - LLVM IR", ["ir_o0", "ir_o2"]],
  ["Backend - machine code", ["assembly", "disassembly", "object", "symbols"]],
];
const PY_PHASES: Array<[string, string[]]> = [
  ["Frontend - reading your Python", ["tokens", "ast", "diagnostics"]],
  ["Compiler - bytecode", ["code_object", "bytecode"]],
];

export default function JourneyNavigator({ job, stageName, onSelectStage, guided, onToggleGuided, language }: {
  job: AnalysisJob;
  stageName: string | null;
  onSelectStage: (s: string) => void;
  guided: boolean;
  onToggleGuided: (g: boolean) => void;
  language: string;
}) {
  const stages = [...job.stages].sort((a, b) => {
    const ia = STAGE_ORDER_HINT.indexOf(a.stage);
    const ib = STAGE_ORDER_HINT.indexOf(b.stage);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });
  const blurb = stageName ? STAGE_BLURBS[stageName] : null;
  const availableIdx = stages.findIndex((s) => s.availability === "AVAILABLE");
  const byStage = new Map(stages.map((s) => [s.stage, s]));
  const phases = language === "c" ? C_PHASES : PY_PHASES;

  const step = (d: number) => {
    // guided stepping skips to the next AVAILABLE stage (concept-level)
    const idx = stages.findIndex((s) => s.stage === stageName);
    let j = idx + d;
    while (j >= 0 && j < stages.length && stages[j].availability !== "AVAILABLE") j += d;
    if (j >= 0 && j < stages.length) onSelectStage(stages[j].stage);
  };

  return (
    <div className="journey" role="navigation" aria-label="compilation journey">
      <div className="journey-rail">
        <span className="journey-cap">{language === "c" ? "Clang/LLVM pipeline" : "CPython pipeline"}</span>
        {phases.map(([phaseLabel, phaseStages]) => {
          const present = phaseStages.filter((s) => byStage.has(s));
          if (!present.length) return null;
          return (
            <div className="journey-phase" key={phaseLabel}>
              <span className="journey-phase-label">{phaseLabel}</span>
              <ol className="journey-stages">
                {present.map((stageId, i) => {
                  const st = byStage.get(stageId)!;
                  const avail = st.availability;
                  const active = st.stage === stageName;
                  const cls = [
                    "jstage",
                    active ? "active" : "",
                    avail === "AVAILABLE" ? "ok" : avail === "PARTIAL" ? "partial" : "off",
                  ].join(" ");
                  return (
                    <li key={st.stage}>
                      <button className={cls}
                              title={`${st.stage} - ${avail}`}
                              aria-current={active ? "step" : undefined}
                              disabled={avail === "ERROR"}
                              onClick={() => onSelectStage(st.stage)}>
                        <span className="jstage-dot" />
                        <span className="jstage-name">{STAGE_BLURBS[st.stage]?.name ?? st.stage}</span>
                        {avail !== "AVAILABLE" && (
                          <span className={`badge ${avail === "PARTIAL" ? "partial" : "blocked"}`}>{avail === "PARTIAL" ? "Partial" : avail === "UNAVAILABLE" ? "Not available" : avail}</span>
                        )}
                      </button>
                      {i < present.length - 1 && <span className="jstage-link" aria-hidden />}
                    </li>
                  );
                })}
              </ol>
            </div>
          );
        })}
        <div className="journey-actions">
          <button className={`btn ghost guided-toggle ${guided ? "on" : ""}`}
                  aria-pressed={guided}
                  onClick={() => onToggleGuided(!guided)}
                  disabled={availableIdx < 0}>
            {guided ? "✓ Guided journey on" : "Guided journey"}
          </button>
          {guided && (
            <span className="guided-steps">
              <button className="btn ghost" onClick={() => step(-1)} aria-label="previous stage">←</button>
              <button className="btn ghost" onClick={() => step(1)} aria-label="next stage">→</button>
            </span>
          )}
        </div>
      </div>
      {guided && blurb && (
        <div className="guided-narration" role="note">
          <b>{blurb.name}.</b> {blurb.what}
        </div>
      )}
    </div>
  );
}
