import { useState } from "react";
import type { GraphSelection } from "./GraphView";
import type { StageData } from "../api";

/**
 * M3-D technical inspector + Evidence Ledger V1. Three explanation levels are
 * deterministic derivations from REAL fields — no invented runtime claims.
 */
type Level = "simple" | "detailed" | "technical";

function explanations(sel: NonNullable<GraphSelection>, stage: string, language: string) {
  const n = sel.node;
  const kind = String(n.kind ?? "?");
  const name = n.name ? String(n.name) : "";
  const line = n.line as number | null;
  const conf = String(n.confidence ?? "UNAVAILABLE");
  // CV-07: confidence-specific language — never overstate what the tool reported.
  const confidenceText: Record<string, string> = {
    EXACT: "reported directly by the tool (EXACT).",
    DERIVED: "derived by CompileVista from tool-reported data (DERIVED) — computed from exact offsets, not directly printed as a line by the tool.",
    APPROXIMATE: "an approximation over tool data (APPROXIMATE).",
    UNAVAILABLE: "not reliably mappable (UNAVAILABLE) — no direct source link is claimed.",
  };
  const simple = name
    ? `${kind} ${name}${line ? ` (source line ${line})` : ""} — a real ${language} representation captured from the toolchain.`
    : `${kind}${line ? ` at source line ${line}` : ""} — a real ${language} representation captured from the toolchain.`;
  const detailed =
    `${kind} is part of the ${stage} stage for this ${language} snapshot. ` +
    `Its position (line ${line ?? "unavailable"}, column ${n.col ?? "unavailable"}) is ${confidenceText[conf] ?? conf} ` +
    `${sel.incoming.length} incoming and ${sel.outgoing.length} outgoing recorded relations.`;
  const technical = JSON.stringify({
    id: n.id, kind, name, line, col: n.col, offset: n.offset,
    confidence: conf, incoming: sel.incoming.length, outgoing: sel.outgoing.length,
    opname: n.opname, argval: n.argval, group: n.group,
  });
  return { simple, detailed, technical };
}

export default function Inspector({ selection, stageData, onClose }: {
  selection: GraphSelection;
  stageData: StageData | null;
  onClose: () => void;
}) {
  const [level, setLevel] = useState<Level>("detailed");
  if (!selection) {
    return (
      <div className="inspector">
        <p className="muted">Select a graph node, token, or instruction to inspect its
          provenance, source range and mapping confidence.</p>
      </div>
    );
  }
  const language = stageData?.language ?? "?";
  const stage = stageData?.stage ?? "?";
  const exp = explanations(selection, stage, language);
  const n = selection.node;
  const prov: NonNullable<StageData["provenance"]> = stageData?.provenance ?? {
    source_combined_sha256: "", raw_artifact_sha256: null,
    stderr_artifact_sha256: null, invocation: {},
  };
  const raw = {
    ...(stageData ? {
      raw_artifact_sha256: stageData.raw_artifact_sha256,
      stderr_artifact_sha256: stageData.stderr_artifact_sha256,
      observation_class: stageData.observation_class,
      availability: stageData.availability,
      limitations: stageData.limitations,
    } : {}),
  };
  return (
    <div className="inspector">
      <div className="insp-head">
        <strong>{String(n.kind ?? "?")}{n.name ? ` · ${String(n.name)}` : ""}</strong>
        <button className="cancel" onClick={onClose} aria-label="close inspector">✕</button>
      </div>
      <div className="levels" role="tablist">
        {(["simple", "detailed", "technical"] as Level[]).map((l) => (
          <button key={l} role="tab" aria-selected={level === l}
                  className={level === l ? "tab active" : "tab"}
                  onClick={() => setLevel(l)}>{l}</button>
        ))}
      </div>
      <p className="explanation">{exp[level]}</p>
      <table className="grid inspgrid">
        <tbody>
          <tr><td>source line</td><td>{String(n.line ?? "—")}{n.col != null ? `:${n.col}` : ""}</td></tr>
          <tr><td>mapping</td><td>{String(n.confidence ?? "UNAVAILABLE")}</td></tr>
          <tr><td>in / out edges</td><td>{selection.incoming.length} / {selection.outgoing.length}</td></tr>
          <tr><td>incoming</td><td>{selection.incoming.map((e) => e.kind).join(", ") || "—"}</td></tr>
          <tr><td>outgoing</td><td>{selection.outgoing.map((e) => e.kind).join(", ") || "—"}</td></tr>
          {n.opname != null && <tr><td>opcode</td><td>{String(n.opname)}</td></tr>}
          {n.argval != null && n.argval !== "None" && <tr><td>argval</td><td>{String(n.argval)}</td></tr>}
          <tr><td>snapshot</td><td><code>{String(prov.source_combined_sha256 ?? "").slice(0, 20)}…</code></td></tr>
          {raw.raw_artifact_sha256 && (
            <tr><td>raw artifact</td><td><code>{String(raw.raw_artifact_sha256).slice(0, 24)}…</code></td></tr>)}
          {raw.observation_class && <tr><td>observation</td><td>{String(raw.observation_class)} · {String(raw.availability)}</td></tr>}
        </tbody>
      </table>
      {raw.limitations && (
        <ul className="limits">{(raw.limitations as string[]).map((l, i) => <li key={i}>{l}</li>)}</ul>
      )}
      <p className="muted copyref" title="provenance reference">
        evidence: {String(prov.source_combined_sha256 ?? "").slice(0, 12)} / {stage} /{" "}
        {String(n.id).slice(-18)}
      </p>
    </div>
  );
}
