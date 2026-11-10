import StatusBadge from "../../ui/status";
import { InfoTip } from "../../ui";
import { useEffect, useState } from "react";
import { StageData } from "../../api";
import { confBadge, Selection, STAGE_BLURBS } from "./types";
import TokenFormation, { SourceSpan } from "./TokenFormation";
import BytecodeLanes from "./BytecodeLanes";
import GraphViewWithSel from "./GraphSelectionBridge";

/** StageCanvas — renders the selected compilation stage with the visualization
 * its data deserves. Availability is taken from the backend, never assumed. */
export default function StageCanvas({ analysisId, stageData, sourceText, language, onSelect, onSelectLine, activeLine, onHoverSpan, guided, onNavigateStage, fullscreen, sourceFocusLine }: {
  analysisId: string;
  stageData: StageData;
  sourceText: string;
  language: string;
  onSelect: (sel: Selection) => void;
  onSelectLine: (line: number) => void;
  activeLine?: number | null;
  onHoverSpan?: (span: SourceSpan | null) => void;
  guided?: boolean;
  onNavigateStage?: (stage: string) => void;
  fullscreen?: boolean;
  /** source-dock-initiated line selection (linked=false in Workspace) */
  sourceFocusLine?: number | null;
}) {
  const s = stageData;
  const blurb = STAGE_BLURBS[s.stage];
  const [view, setView] = useState<"visual" | "raw">("visual");

  useEffect(() => { setView("visual"); }, [s.stage]);

  const graphable = s.stage === "ast" || s.stage.startsWith("ir_");
  const isTokens = s.stage === "tokens";
  const isBytecode = s.stage === "bytecode";

  const items = s.items as Array<Record<string, unknown>>;

  return (
    <div className="stagecanvas">
      <div className="sc-head">
        <div className="sc-title">
          <h2>{blurb?.name ?? s.stage}</h2>
          {s.availability !== "AVAILABLE" && (
            <StatusBadge code={s.availability === "PARTIAL" ? "PARTIAL" : s.availability === "UNAVAILABLE" ? "UNAVAILABLE" : "BLOCKED"} />
          )}
          {s.truncated && <span className="badge partial">truncated</span>}
          {s.limitations.length > 0 && (
            <InfoTip label={`${s.limitations.length} limitation${s.limitations.length === 1 ? "" : "s"} of this stage`}>
              <b>Limits of this stage</b>
              <ul className="infotip-list">{s.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>
            </InfoTip>
          )}
          {(graphable || isBytecode) && (
            <div className="sc-viewtoggle" role="tablist" aria-label="stage view mode">
              <button role="tab" aria-selected={view === "visual"} className={view === "visual" ? "active" : ""}
                      onClick={() => setView("visual")}>{isBytecode ? "Lanes" : "Graph"}</button>
              <button role="tab" aria-selected={view === "raw"} className={view === "raw" ? "active" : ""}
                      onClick={() => setView("raw")}>Raw tool output</button>
            </div>
          )}
        </div>
        <p className="sc-what muted">{blurb?.what}</p>
        <div className="prov tech-only">
          <span>tool: <code>{s.invocation?.tool ?? s.invocation?.worker ?? "—"}</code></span>
          {s.invocation?.tool_versions && Object.entries(s.invocation.tool_versions).map(([k, v]) => (
            <span key={k}>{k}: <code>{v}</code></span>
          ))}
          <span>exit: <code>{s.exit_code ?? "—"}</code></span>
          <span>duration: <code>{s.duration_ms ?? "—"} ms</code></span>
          <span>observation: <code>{s.observation_class}</code></span>
          {s.raw_artifact_sha256 && <span>artifact: <code>{s.raw_artifact_sha256.slice(0, 20)}…</code></span>}
        </div>
      </div>

      {s.limitations.length > 0 && (
        <ul className="limits tech-only" aria-label="stage limitations">
          {s.limitations.map((l, i) => <li key={i}>{l}</li>)}
        </ul>
      )}

      {view === "raw" ? (
        <RawExcerpt analysisId={analysisId} stage={s.stage} />
      ) : isTokens ? (
        <TokenFormation
          tokens={items as never as Array<{ kind: string; text: string; line: number; col: number; mapping_confidence?: string }>}
          sourceText={sourceText} language={language} truncated={s.truncated}
          onSelect={onSelect} onSelectLine={onSelectLine} activeLine={activeLine}
          onHoverSpan={onHoverSpan} guided={guided} onNavigateStage={onNavigateStage} />
      ) : isBytecode && language === "python" ? (
        <BytecodeLanes items={items} language={language} onSelect={onSelect} onSelectLine={onSelectLine}
                       activeLine={activeLine} guided={guided} onNavigateStage={onNavigateStage}
                       analysisId={analysisId} />
      ) : graphable ? (
        <GraphViewWithSel analysisId={analysisId} stage={s.stage} onSelect={onSelect} onSelectLine={onSelectLine}
                          focusLine={sourceFocusLine} guided={guided} onNavigateStage={onNavigateStage}
                          fullscreen={fullscreen} />
      ) : s.stage === "code_object" ? (
        <CodeObjects items={items} onSelect={onSelect} language={language} />
      ) : s.stage === "assembly" ? (
        <AssemblyView items={items} counts={s.counts} onSelect={onSelect} language={language} />
      ) : s.stage === "disassembly" ? (
        <Disassembly items={items} onSelect={onSelect} />
      ) : s.stage === "symbols" ? (
        <Symbols items={items} onSelect={onSelect} />
      ) : s.stage === "diagnostics" ? (
        <Diagnostics items={items} onSelect={onSelect} onSelectLine={onSelectLine} />
      ) : s.stage === "preprocess" ? (
        <RawExcerpt analysisId={analysisId} stage={s.stage} intro="The preprocessor's output — one translation unit of expanded C source." />
      ) : s.stage === "object" ? (
        <div className="unavailable"><span className="glyph">◈</span>
          Object file recorded: <code>{String(s.counts.object_sha256 ?? "").slice(0, 24)}…</code> ·{" "}
          {String(s.counts.bytes ?? "?")} bytes. The binary is digest-recorded but never served
          for execution — see Disassembly for its instructions.</div>
      ) : (
        <div className="unavailable"><span className="glyph">◍</span>
          This stage produced no normalized items{items.length ? ` (${items.length} unhandled)` : ""} —
          check the raw tool output{Object.keys(s.counts).length ? ` or counts (${JSON.stringify(s.counts)})` : ""}.</div>
      )}
    </div>
  );
}

function RawExcerpt({ analysisId, stage, intro }: { analysisId: string; stage: string; intro?: string }) {
  const [text, setText] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    setText(null); setErr(null);
    fetch(`/api/v1/analyses/${analysisId}/stages/${stage}/raw`)
      .then((r) => r.json())
      .then((r: { excerpt?: string | null }) => { if (alive) setText(r.excerpt ?? null); })
      .catch((e) => { if (alive) setErr(String(e)); });
    return () => { alive = false; };
  }, [analysisId, stage]);
  if (err) return <p className="err">{err}</p>;
  if (text == null) return <p className="muted"><span className="spinner" /> loading raw artifact…</p>;
  if (!text) {
    return <div className="unavailable"><span className="glyph">◍</span>
      No raw excerpt is stored for this stage.</div>;
  }
  return (
    <>
      {intro && <p className="muted">{intro}</p>}
      <pre className="excerpt" tabIndex={0} aria-label="raw tool output">{text}</pre>
    </>
  );
}

function CodeObjects({ items, onSelect, language }: {
  items: Array<Record<string, unknown>>; onSelect: (s: Selection) => void; language: string;
}) {
  if (!items.length) return <div className="unavailable"><span className="glyph">◍</span>No code objects reported.</div>;
  return (
    <div className="codeobjects">
      {items.map((co, i) => (
        <button key={i} className="co-card panel"
                onClick={() => onSelect({
                  id: `co:${co.id}`,
                  title: `code object “${String(co.qualname ?? co.name ?? co.id)}”`,
                  subtitle: "CPython code object",
                  stage: "code_object", language,
                  what: "A code object is CPython's compiled unit of scope: the constants its bytecode uses, the names it looks up, and its local variables. Functions, classes and the module each get one.",
                  fields: [
                    ["id", String(co.id)],
                    ["name", String(co.name ?? "—")],
                    ["qualname", String(co.qualname ?? "—")],
                    ["args", String(co.argcount ?? 0)],
                    ["locals (varnames)", (co.varnames as string[] | undefined)?.join(", ") || "—"],
                    ["global names", (co.names as string[] | undefined)?.join(", ") || "—"],
                    ["non-code consts", (co.consts_noncode as string[] | undefined)?.join(", ") || "—"],
                    ["nesting depth", String(co.depth ?? 0)],
                  ],
                  confidence: "EXACT",
                  raw: co,
                })}>
          <div className="co-head">
            <b>{String(co.qualname ?? co.name ?? co.id)}</b>
            {Number(co.argcount ?? 0) > 0 && <span className="chip">{String(co.argcount)} args</span>}
            {Number(co.depth ?? 0) > 0 && <span className="chip">depth {String(co.depth)}</span>}
          </div>
          <p className="muted">
            {(co.varnames as string[] | undefined)?.length ?? 0} locals ·{" "}
            {(co.names as string[] | undefined)?.length ?? 0} name lookups ·{" "}
            {(co.consts_noncode as string[] | undefined)?.length ?? 0} consts
          </p>
        </button>
      ))}
    </div>
  );
}

function AssemblyView({ items, counts, onSelect, language }: {
  items: Array<Record<string, unknown>>; counts: Record<string, unknown>;
  onSelect: (s: Selection) => void; language: string;
}) {
  return (
    <div className="asmview">
      <p className="muted">
        {String(counts.function_labels ?? items.length)} function labels ·{" "}
        {String(counts.lines ?? "—")} lines of assembly (static artifact — not an
        executed-instruction count). Source→assembly mapping is{" "}
        <StatusBadge code="UNAVAILABLE" /> in this pipeline; the
        full listing is in the raw view.
      </p>
      <div className="asmfuncs">
        {items.map((f, i) => (
          <button key={i} className="asm-func panel"
                  onClick={() => onSelect({
                    id: `asm:${f.label}`,
                    title: `function ${String(f.label)}`,
                    subtitle: "assembly label",
                    stage: "assembly", language,
                    what: "One emitted function in target assembly. The label is where the linker and calls will jump to; the instructions live in the raw listing.",
                    fields: [["label", String(f.label)], ["mapping", String(f.mapping_confidence ?? "—")]],
                    confidence: String(f.mapping_confidence ?? "DERIVED"),
                    raw: f,
                  })}>
            <code>{String(f.label)}</code>
            <span className="badge derived">{String(f.mapping_confidence ?? "DERIVED")}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function Disassembly({ items, onSelect }: {
  items: Array<Record<string, unknown>>; onSelect: (s: Selection) => void;
}) {
  const [limit, setLimit] = useState(300);
  if (!items.length) return <div className="unavailable"><span className="glyph">◍</span>No disassembly items.</div>;
  const shown = items.slice(0, limit);
  return (
    <div className="disasm">
      <table className="disasm-table" role="table" aria-label="disassembly">
        <thead><tr><th>addr</th><th>bytes</th><th>mnemonic</th><th>operands</th></tr></thead>
        <tbody>
          {shown.map((it, i) => (
            <tr key={i} onClick={() => onSelect({
              id: `dis:${it.addr}:${i}`,
              title: `${String(it.mnemonic)} ${String(it.operands ?? "")}`,
              subtitle: "object disassembly",
              stage: "disassembly", language: "c",
              what: "A machine instruction of the compiled object file, with its virtual address and encoded bytes. This is the closest view to what the CPU executes after linking.",
              fields: [
                ["address", `0x${String(it.addr)}`],
                ["bytes", String(it.bytes ?? "")],
                ["mnemonic", String(it.mnemonic)],
                ["operands", String(it.operands ?? "")],
              ],
              confidence: String(it.mapping_confidence ?? "UNAVAILABLE"),
              raw: it,
            })}>
              <td><code>0x{String(it.addr)}</code></td>
              <td><code className="muted">{String(it.bytes ?? "")}</code></td>
              <td><b className="dis-mn">{String(it.mnemonic)}</b></td>
              <td><code>{String(it.operands ?? "")}</code></td>
            </tr>
          ))}
        </tbody>
      </table>
      {items.length > limit && (
        <button className="btn" style={{ marginTop: 10 }} onClick={() => setLimit((l) => l + 500)}>
          Show more ({items.length - limit} remaining)
        </button>
      )}
    </div>
  );
}

function Symbols({ items, onSelect }: {
  items: Array<Record<string, unknown>>; onSelect: (s: Selection) => void;
}) {
  if (!items.length) return <div className="unavailable"><span className="glyph">◍</span>No symbols reported.</div>;
  return (
    <div className="symbols">
      {items.map((s, i) => (
        <button key={i} className="sym panel"
                onClick={() => onSelect({
                  id: `sym:${i}`,
                  title: `${String(s.name)}`,
                  subtitle: `${String(s.binding)} ${String(s.type)} symbol`,
                  stage: "symbols", language: "c",
                  what: "An entry of the ELF symbol table: a name the object file defines (GLOBAL) or references, with its type and size in bytes.",
                  fields: [
                    ["name", String(s.name)], ["type", String(s.type)],
                    ["binding", String(s.binding)], ["size", `${String(s.size)} B`],
                  ],
                  confidence: String(s.mapping_confidence ?? "DERIVED"),
                  raw: s,
                })}>
          <code>{String(s.name)}</code>
          <span className="chip">{String(s.binding)} {String(s.type)}</span>
          <span className="muted">{String(s.size)} B</span>
        </button>
      ))}
    </div>
  );
}

function Diagnostics({ items, onSelect, onSelectLine }: {
  items: Array<Record<string, unknown>>;
  onSelect: (s: Selection) => void; onSelectLine: (l: number) => void;
}) {
  if (!items.length) {
    return (
      <div className="diag-clean">
        <span className="badge ok">clean</span> The toolchain reported no diagnostics for this program.
      </div>
    );
  }
  return (
    <div className="diags">
      {items.map((d, i) => {
        const isPy = "error_type" in d;
        const line = isPy ? d.lineno : d.line;
        const sev = isPy ? "error" : d.severity;
        return (
          <button key={i} className={`diag ${sev}`}
                  onClick={() => {
                    onSelectLine(Number(line));
                    onSelect({
                      id: `diag:${i}`,
                      title: String(isPy ? d.error_type : d.message).slice(0, 80),
                      subtitle: `diagnostic · ${String(sev)}`,
                      stage: "diagnostics", language: isPy ? "python" : "c",
                      what: "A diagnostic the real toolchain emitted while reading your program, with the position that triggered it.",
                      fields: isPy
                        ? [["error_type", String(d.error_type)], ["line", String(d.lineno)], ["offset", String(d.offset)], ["msg", String(d.msg)]]
                        : [["file", String(d.file)], ["line", String(d.line)], ["col", String(d.col)], ["severity", String(d.severity)], ["message", String(d.message)]],
                      sourceLine: line != null ? Number(line) : null,
                      confidence: "EXACT",
                      raw: d,
                    });
                  }}>
            <span className={`sev ${sev}`}>{isPy ? "error" : String(d.severity)}</span>
            <code>{isPy ? `line ${d.lineno}` : `${d.file}:${d.line}:${d.col}`}</code>
            <span className="diag-msg">{String(isPy ? d.msg : d.message)}</span>
          </button>
        );
      })}
    </div>
  );
}

export { confBadge };
