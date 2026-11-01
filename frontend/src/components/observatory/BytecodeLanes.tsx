import { useEffect, useMemo, useState } from "react";
import { Selection } from "./types";

interface BcItem {
  code_object_id: string;
  code_object: string;
  offset: number;
  opname: string;
  arg: number | null;
  argval: string | null;
  branch_targets: string[];
  fallthrough: string | null;
  starts_line: number | null;
  positions: number[] | null;
  mapping_confidence?: string;
}

interface CodeObjectRec {
  id?: string;
  qualname?: string;
  name?: string;
  argcount?: number;
  varnames?: string[];
  names?: string[];
  consts_noncode?: string[];
}

/**
 * Bytecode Observatory — the real CPython instruction stream, grouped by code
 * object, with branch-target arcs drawn only from the disassembler's recorded
 * branch_targets. Offsets, opcodes and positions are EXACT. The code object's
 * constants and name tables come from the real code_object stage. Selecting a
 * source line highlights the instructions the tool maps to it; selecting an
 * instruction highlights its source line. No operand-stack simulation is shown.
 */
export default function BytecodeLanes({ items, language, onSelect, onSelectLine, activeLine, guided, onNavigateStage, analysisId }: {
  items: Array<Record<string, unknown>>;
  language: string;
  onSelect: (sel: Selection) => void;
  onSelectLine: (line: number) => void;
  activeLine?: number | null;
  guided?: boolean;
  onNavigateStage?: (stage: string) => void;
  analysisId?: string;
}) {
  const [activeCo, setActiveCo] = useState<string | null>(null);
  const [coDetails, setCoDetails] = useState<Map<string, CodeObjectRec>>(new Map());

  const groups = useMemo(() => {
    const g = new Map<string, BcItem[]>();
    for (const raw of items) {
      const it = raw as unknown as BcItem;
      if (!g.has(it.code_object_id)) g.set(it.code_object_id, []);
      g.get(it.code_object_id)!.push(it);
    }
    return [...g.entries()];
  }, [items]);

  // real code-object metadata (constants, names, varnames) from its own stage
  useEffect(() => {
    if (!analysisId) return;
    let alive = true;
    fetch(`/api/v1/analyses/${analysisId}/stages/code_object`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!alive || !d?.items) return;
        const m = new Map<string, CodeObjectRec>();
        for (const it of d.items as Array<Record<string, unknown>>) {
          m.set(String(it.id ?? it.qualname ?? it.name), it as CodeObjectRec);
        }
        setCoDetails(m);
      })
      .catch(() => { /* honest absence: panel just doesn't render */ });
    return () => { alive = false; };
  }, [analysisId]);

  if (!groups.length) {
    return <div className="unavailable"><span className="glyph">◍</span>
      No bytecode instructions were reported for this program.</div>;
  }

  const current = groups.find(([id]) => id === activeCo) ?? groups[0];
  const [coId, instrs] = current;

  // offset → index map for arc drawing
  const offsetIndex = new Map<number, number>();
  instrs.forEach((it, i) => offsetIndex.set(Number(it.offset), i));

  const targetOf = (it: BcItem): number[] => {
    const out: number[] = [];
    for (const t of it.branch_targets ?? []) {
      const n = parseInt(String(t).replace(/[^0-9]/g, ""), 10);
      if (!Number.isNaN(n)) out.push(n);
    }
    return out;
  };

  const rowH = 26;
  const lineOf = (it: BcItem) => (it.positions ? it.positions[0] : it.starts_line);
  const activeLineSet = useMemo(() => {
    if (activeLine == null) return null;
    const s = new Set<number>();
    instrs.forEach((it, i) => { if (lineOf(it) === activeLine) s.add(i); });
    return s;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeLine, coId, instrs]);

  const detail = [...coDetails.entries()].find(([, v]) =>
    (v.qualname ?? v.name) === coId.split(":").slice(1).join(":"))?.[1]
    ?? coDetails.get(coId.split(":").slice(1).join(":"));

  const GUIDED_STEPS = [
    "CPython does not run your text: it compiles each scope into a code object. This selector lists the real ones.",
    "Inside a code object, your program is a list of stack-machine instructions. Offsets and opcodes come from the disassembler of the running Python.",
    "Green and red arcs are real jumps recorded by the disassembler — this is how if/else and loops become control flow.",
    "Select a line of your source in the dock: the tool's line table shows which instructions implement it. Not every token maps to one instruction.",
    "The interpreter executes these instructions one at a time on an evaluation stack. Continue to the recorded run to watch frames grow and shrink.",
  ];
  const [guidedStep, setGuidedStep] = useState(0);
  useEffect(() => {
    if (!guided) return;
    if (guidedStep === 2) {
      // focus a branch instruction if this object has one
      const branch = instrs.find((it) => targetOf(it).length > 0);
      if (branch) {
        setActiveCo(branch.code_object_id);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guidedStep, guided]);

  return (
    <div className="bclanes">
      <div className="bclanes-toolbar">
        <label className="muted" htmlFor="bc-co">code object:</label>
        <select id="bc-co" className="input" style={{ width: "auto" }}
                value={coId} onChange={(e) => setActiveCo(e.target.value)}>
          {groups.map(([id, its]) => (
            <option key={id} value={id}>{id.split(":").slice(1).join(":") || id} ({its.length} instr)</option>
          ))}
        </select>
        <span className="spacer" />
        <span className="muted">{instrs.length} instructions ·
          branch arcs from dis branch_targets · CPython bytecode</span>
      </div>

      {guided && (
        <div className="tf-guided" role="note" aria-live="polite">
          <div className="tf-guided-h"><span>guided · bytecode · step {guidedStep + 1}/5</span></div>
          <p className="tf-guided-step">{GUIDED_STEPS[Math.min(guidedStep, GUIDED_STEPS.length - 1)]}</p>
          <div className="tf-guided-actions">
            <button className="btn ghost" onClick={() => setGuidedStep((s) => Math.max(0, s - 1))} disabled={guidedStep === 0}>← back</button>
            {guidedStep < GUIDED_STEPS.length - 1
              ? <button className="btn primary" onClick={() => setGuidedStep((s) => s + 1)}>continue →</button>
              : <button className="btn primary" onClick={() => onNavigateStage?.("code_object")}>open the code-object inventory →</button>}
            <div className="tf-guided-dots" aria-hidden>
              {GUIDED_STEPS.map((_, i) => <span key={i} className={i === guidedStep ? "on" : ""} />)}
            </div>
          </div>
        </div>
      )}

      {detail && (
        <div className="bc-co-meta">
          <div className="bc-co-meta-h">code object · {detail.qualname ?? detail.name}</div>
          <div className="bc-co-meta-body">
            {detail.argcount != null && detail.argcount > 0 && <span className="chip">{detail.argcount} args</span>}
            {detail.varnames?.length ? <span className="chip" title="local variables">locals: {detail.varnames.join(", ")}</span> : null}
            {detail.names?.length ? <span className="chip" title="global/loaded names">names: {detail.names.slice(0, 8).join(", ")}{detail.names.length > 8 ? "…" : ""}</span> : null}
            {detail.consts_noncode?.length ? <span className="chip" title="constants captured at compile time">consts: {detail.consts_noncode.slice(0, 6).join(", ")}{detail.consts_noncode.length > 6 ? "…" : ""}</span> : null}
          </div>
        </div>
      )}

      <div className="bc-canvas on-ink" style={{ ["--row-h" as string]: `${rowH}px` }}>
        <svg className="bc-arcs" aria-hidden
             width={64} height={instrs.length * rowH}>
          {instrs.map((it, i) => targetOf(it).map((t, k) => {
            const j = offsetIndex.get(t);
            if (j == null) return null;
            const y1 = i * rowH + rowH / 2;
            const y2 = j * rowH + rowH / 2;
            const back = j < i;
            const reach = Math.abs(j - i);
            const bulge = Math.min(30 + reach * 2.2, 52);
            const d = `M ${back ? 60 : 4} ${y1} C ${back ? 60 - bulge : 4 + bulge} ${y1}, ${back ? 60 - bulge : 4 + bulge} ${y2}, ${back ? 60 : 4} ${y2}`;
            return <path key={`${i}-${k}`} d={d}
                         className={`bc-arc ${back ? "back" : "fwd"}`}
                         data-from={it.offset} data-to={t} />;
          }))}
        </svg>
        <div className="bc-rows">
          {instrs.map((it, i) => {
            const line = lineOf(it);
            const newLine = i === 0 || lineOf(instrs[i - 1]) !== line;
            const isActive = activeLineSet?.has(i);
            const sel = () => {
              onSelect({
                id: `bc:${coId}:${it.offset}`,
                title: `${it.opname}${it.arg != null ? ` ${it.arg}` : ""}`,
                subtitle: `bytecode · offset ${it.offset}`,
                stage: "bytecode",
                language,
                what: BC_WHAT(it.opname),
                fields: [
                  ["code object", String(it.code_object)],
                  ["offset", String(it.offset)],
                  ["opname", String(it.opname)],
                  ["arg", it.arg != null ? String(it.arg) : "—"],
                  ["argval", it.argval ?? "—"],
                  ["branch targets", (it.branch_targets ?? []).length ? (it.branch_targets ?? []).join(", ") : "—"],
                  ["fallthrough", it.fallthrough ?? "—"],
                  ["source line", line != null ? String(line) : "—"],
                  ["positions", it.positions ? it.positions.join(":") : "—"],
                  ["mapping", String(it.mapping_confidence ?? "—")],
                ],
                sourceLine: line != null ? Number(line) : null,
                confidence: it.mapping_confidence,
                raw: it as unknown as Record<string, unknown>,
              });
              if (line != null) onSelectLine(Number(line));
            };
            const hasArc = targetOf(it).length > 0 || it.fallthrough;
            return (
              <div key={i}>
                {newLine && line != null && (
                  <div className="bc-linesepr" title={`instructions mapped to source line ${line}`}>
                    <span>line {line}</span>
                  </div>
                )}
                <button className={"bc-row" + (hasArc ? " has-arc" : "") + (isActive ? " active" : "")}
                        onClick={sel}
                        style={{ height: rowH }}
                        title={`offset ${it.offset} · ${it.opname}${it.arg != null ? " " + it.arg : ""}`}>
                  <code className="bc-off">{String(it.offset).padStart(4, "0")}</code>
                  <b className="bc-op">{it.opname}</b>
                  <span className="bc-arg">{it.argval && it.argval !== "None" ? it.argval : it.arg != null ? it.arg : ""}</span>
                  {line != null && <span className="bc-line">:{line}</span>}
                </button>
              </div>
            );
          })}
        </div>
      </div>
      <p className="muted bc-note">
        This is interpreter bytecode, not machine code — CPython 3.12 executes each
        instruction on an evaluation stack. Jump arcs are drawn only where the
        disassembler reported branch targets. A source line usually maps to several
        instructions; the stack itself is not simulated here.
      </p>
    </div>
  );
}

function BC_WHAT(op: string): string {
  if (op.startsWith("LOAD_")) return "Pushes a value onto the evaluation stack — a constant, a name lookup, or an attribute.";
  if (op.startsWith("STORE_")) return "Pops the top of the stack and binds it to a name, attribute or subscript.";
  if (op.startsWith("CALL")) return "Invokes a callable, consuming the pushed arguments from the stack.";
  if (op.startsWith("COMPARE") || op.startsWith("CONTAINS") || op.startsWith("IS_OP")) return "Comparison instruction: pops two operands, pushes a boolean result.";
  if (op.startsWith("BINARY") || op.startsWith("INPLACE") || op === "UNARY_NEGATIVE" || op.startsWith("UNARY_")) return "Arithmetic/logic on stack operands — the actual computation of your expressions.";
  if (op.startsWith("JUMP") || op === "FOR_ITER" || op.startsWith("POP_JUMP")) return "Control flow: moves the instruction pointer, implementing if/else, loops and short-circuit logic. The arc shows the disassembler-verified target.";
  if (op === "GET_ITER" || op === "FOR_ITER") return "Iteration protocol: obtains an iterator / advances it, jumping back while elements remain.";
  if (op.startsWith("RETURN") || op === "RETURN_VALUE" || op === "RETURN_CONST") return "Returns from the current frame, handing a value (or None) to the caller.";
  if (op === "RESUME") return "Frame bookkeeping inserted by CPython 3.11+ — marks where execution can resume/yield for the debugger and generators.";
  if (op === "PUSH_NULL" || op === "PRECALL" || op === "CACHE" || op.startsWith("KW_NAMES")) return "Calling-convention plumbing of the CPython 3.11+ instruction set.";
  if (op === "BUILD_LIST" || op === "BUILD_MAP" || op === "BUILD_TUPLE" || op === "BUILD_SET") return "Constructs a collection object from stack items.";
  if (op === "IMPORT_NAME" || op === "IMPORT_FROM") return "The import machinery: resolves and loads a module, binding names.";
  if (op === "MAKE_FUNCTION") return "Creates a function object from a code object captured as a constant.";
  return "An instruction of the CPython evaluation stack, reported verbatim by the disassembler.";
}
