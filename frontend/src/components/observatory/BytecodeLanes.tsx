import { useMemo, useState } from "react";
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

/**
 * Bytecode Explorer — the real CPython instruction stream, grouped by code
 * object, with branch-target arcs drawn from the disassembler's own
 * hasjabs/hasjrel data. Offsets, opcodes and positions are EXACT; the arcs are
 * a rendering of recorded branch_targets, never guessed jumps.
 */
export default function BytecodeLanes({ items, language, onSelect, onSelectLine }: {
  items: Array<Record<string, unknown>>;
  language: string;
  onSelect: (sel: Selection) => void;
  onSelectLine: (line: number) => void;
}) {
  const [activeCo, setActiveCo] = useState<string | null>(null);

  const groups = useMemo(() => {
    const g = new Map<string, BcItem[]>();
    for (const raw of items) {
      const it = raw as unknown as BcItem;
      if (!g.has(it.code_object_id)) g.set(it.code_object_id, []);
      g.get(it.code_object_id)!.push(it);
    }
    return [...g.entries()];
  }, [items]);

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
    // branch_targets are stringified offsets ("12", "to 12") — parse numbers
    const out: number[] = [];
    for (const t of it.branch_targets ?? []) {
      const n = parseInt(String(t).replace(/[^0-9]/g, ""), 10);
      if (!Number.isNaN(n)) out.push(n);
    }
    return out;
  };

  const rowH = 26;

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
          branch arcs from dis branch_targets · {language === "python" ? `CPython bytecode` : language}</span>
      </div>

      <div className="bc-canvas" style={{ ["--row-h" as string]: `${rowH}px` }}>
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
            const line = it.positions ? it.positions[0] : it.starts_line;
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
              <button key={i} className={"bc-row" + (hasArc ? " has-arc" : "")}
                      onClick={sel}
                      style={{ height: rowH }}
                      title={`offset ${it.offset} · ${it.opname}${it.arg != null ? " " + it.arg : ""}`}>
                <code className="bc-off">{String(it.offset).padStart(4, "0")}</code>
                <b className="bc-op">{it.opname}</b>
                <span className="bc-arg">{it.argval && it.argval !== "None" ? it.argval : it.arg != null ? it.arg : ""}</span>
                {line != null && <span className="bc-line">:{line}</span>}
              </button>
            );
          })}
        </div>
      </div>
      <p className="muted bc-note">
        This is interpreter bytecode, not machine code — CPython 3.12 executes each
        instruction on an evaluation stack. Jump arcs are drawn only where the
        disassembler reported branch targets.
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
  if (op === "MAKE_FUNCTION" || op === "LOAD_CONST" && false) return "Creates a function object from a code object captured as a constant.";
  return "An instruction of the CPython evaluation stack, reported verbatim by the disassembler.";
}
