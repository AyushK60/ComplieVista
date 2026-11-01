import { AnalysisJob } from "../../api";
import { STAGE_BLURBS } from "./types";

/**
 * Journey Navigator — the spatially-ordered pipeline of the selected program.
 * Stages come verbatim from the analysis job (never invented); availability
 * and observation class are shown honestly. Guided mode steps concept-level
 * through the same stages with narrated explanations.
 */
const STAGE_ORDER_HINT = [
  "preprocess", "tokens", "ast", "code_object", "bytecode",
  "ir_o0", "ir_o2", "assembly", "disassembly", "object", "symbols", "diagnostics",
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
  const idx = stages.findIndex((s) => s.stage === stageName);
  const blurb = stageName ? STAGE_BLURBS[stageName] : null;
  const availableIdx = stages.findIndex((s) => s.availability === "AVAILABLE");

  const step = (d: number) => {
    // guided stepping skips to the next AVAILABLE stage (concept-level, not micro-steps)
    let j = idx + d;
    while (j >= 0 && j < stages.length && stages[j].availability !== "AVAILABLE") j += d;
    if (j >= 0 && j < stages.length) onSelectStage(stages[j].stage);
  };

  return (
    <div className="journey" role="navigation" aria-label="compilation journey">
      <div className="journey-rail">
        <span className="journey-cap">{language === "c" ? "Clang/LLVM pipeline" : "CPython pipeline"}</span>
        <ol className="journey-stages">
          {stages.map((s, i) => {
            const avail = s.availability;
            const active = s.stage === stageName;
            const cls = [
              "jstage",
              active ? "active" : "",
              avail === "AVAILABLE" ? "ok" : avail === "PARTIAL" ? "partial" : "off",
            ].join(" ");
            return (
              <li key={s.stage}>
                <button className={cls}
                        title={`${s.stage} — ${avail}`}
                        aria-current={active ? "step" : undefined}
                        disabled={avail === "ERROR"}
                        onClick={() => onSelectStage(s.stage)}>
                  <span className="jstage-dot" />
                  <span className="jstage-name">{STAGE_BLURBS[s.stage]?.name ?? s.stage}</span>
                  {avail !== "AVAILABLE" && (
                    <span className={`badge ${avail === "PARTIAL" ? "partial" : "blocked"}`}>{avail}</span>
                  )}
                </button>
                {i < stages.length - 1 && <span className="jstage-link" aria-hidden />}
              </li>
            );
          })}
        </ol>
        <div className="journey-actions">
          <button className={`btn ghost guided-toggle ${guided ? "on" : ""}`}
                  aria-pressed={guided}
                  onClick={() => onToggleGuided(!guided)}
                  disabled={availableIdx < 0}>
            {guided ? "✓ Guided journey on" : "Guided journey"}
          </button>
          {guided && (
            <span className="guided-steps">
              <button className="btn ghost" onClick={() => step(-1)} disabled={idx <= 0 && availableIdx !== -1}
                      aria-label="previous stage">←</button>
              <button className="btn ghost" onClick={() => step(1)}
                      aria-label="next stage">→</button>
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
