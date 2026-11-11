import { useEffect, useMemo, useRef, useState } from "react";
import data from "../../data/figures.json";

/**
 * Three home-page figures drawn from RECORDED tool output (src/data/figures.json, built by
 * scripts/media/build_figures.py from evidence/m0 and one real sandbox run). Nothing here is
 * invented; the single derived link (assembly to source) is labelled in the caption.
 */

const reduceMotion = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Advance an index on a timer until the user touches the figure. */
function useCycle(len: number, ms: number) {
  const [i, setI] = useState(0);
  const [auto, setAuto] = useState(() => !reduceMotion());
  useEffect(() => {
    if (!auto || len < 2) return;
    const t = setInterval(() => setI((n) => (n + 1) % len), ms);
    return () => clearInterval(t);
  }, [auto, len, ms]);
  return { i, set: (n: number) => { setAuto(false); setI(n); }, auto, setAuto };
}

function Cap({ lines }: { lines: string[] }) {
  return <figcaption className="fg-cap">{lines.map((l) => <span key={l}>{l}</span>)}</figcaption>;
}

/* ———————————————————— syntax tree ———————————————————— */
type TNode = { kind: string; name?: string; line: number; implicit?: boolean; children?: TNode[] };
type Placed = TNode & { x: number; y: number; id: number; parent?: number };

const COL = 150, ROW = 46, BW = 132, BH = 36;

function layout(root: TNode) {
  const out: Placed[] = [];
  let leaf = 0;
  const walk = (n: TNode, depth: number, parent?: number): number => {
    const id = out.length;
    const p: Placed = { ...n, x: depth * COL, y: 0, id, parent };
    out.push(p);
    if (!n.children?.length) p.y = leaf++ * ROW;
    else {
      const ys = n.children.map((c) => out[walk(c, depth + 1, id)].y);
      p.y = (ys[0] + ys[ys.length - 1]) / 2;
    }
    return id;
  };
  walk(root, 0);
  return { nodes: out, rows: leaf };
}

function category(k: string): "decl" | "stmt" | "expr" | "lit" {
  if (k.endsWith("Decl")) return "decl";
  if (k.endsWith("Stmt")) return "stmt";
  if (k === "IntegerLiteral") return "lit";
  return "expr";
}

export function AstFigure() {
  const d = data.ast;
  const { nodes, rows } = useMemo(() => layout(d.tree as TNode), [d.tree]);
  const stops = [8, 9, 10, 12];
  const cyc = useCycle(stops.length, 2600);
  const sel = stops[cyc.i];
  const w = 6 * COL, h = rows * ROW;
  return (
    <figure className="fg fg-ast">
      <div className="fg-body">
        <ol className="fg-src" aria-label="source lines">
          {d.source.map((s) => (
            <li key={s.n} data-on={s.n === sel ? "" : undefined}>
              <button type="button" disabled={!stops.includes(s.n)} onClick={() => cyc.set(stops.indexOf(s.n))}>
                <span className="n">{s.n}</span><code>{s.text}</code>
              </button>
            </li>
          ))}
        </ol>
        <svg className="fg-tree" viewBox={`-6 -6 ${w + 12 - (COL - BW)} ${h - (ROW - BH) + 12}`} role="img"
             aria-label={`Clang syntax tree for scale_and_adjust, line ${sel} selected`}>
          {nodes.filter((n) => n.parent !== undefined).map((n) => {
            const p = nodes[n.parent!];
            const on = n.line === sel && p.line === sel;
            return <path key={n.id} className={"edge" + (on ? " on" : "")}
                         d={`M${p.x + BW} ${p.y + BH / 2} H${p.x + BW + (COL - BW) / 2} V${n.y + BH / 2} H${n.x}`} />;
          })}
          {nodes.map((n) => (
            <g key={n.id} className={`node ${category(n.kind)}${n.implicit ? " implicit" : ""}${n.line === sel ? " on" : ""}`}
               transform={`translate(${n.x} ${n.y})`}
               onMouseEnter={() => stops.includes(n.line) && cyc.set(stops.indexOf(n.line))}>
              <rect width={BW} height={BH} />
              <text x={8} y={15} className="k">{n.kind}</text>
              {n.name && <text x={8} y={29} className="v">{n.name}</text>}
            </g>
          ))}
        </svg>
      </div>
      <Cap lines={[
        `Recorded output · ${d.provenance.tool}`,
        `${d.provenance.invocation} · source sha256 ${d.provenance.source_sha256.slice(0, 10)}…`,
        "Dashed nodes are implicit: Clang adds them, no token spells them.",
      ]} />
    </figure>
  );
}

/* ———————————————————— lowering: IR, assembly, bytecode ———————————————————— */
type Row = { text: string; line: number | null };
const TABS = [
  { id: "ir", label: "C · LLVM IR" },
  { id: "asm", label: "C · x86-64" },
  { id: "py", label: "Python · bytecode" },
] as const;

export function LowerFigure() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("ir");
  const c = data.c_lower, p = data.py_lower;
  const src = tab === "py" ? p.source : c.source;
  const rows: Row[] = tab === "ir"
    ? c.ir.map((r) => ({ text: r.text.replace(/:\s+;.*$/, ":"), line: r.line }))
    : tab === "asm"
      ? c.asm.map((r) => ({ text: r.text, line: r.line }))
      : p.dis.map((r) => ({ text: `${String(r.offset).padStart(3)}  ${r.op.padEnd(14)} ${r.arg}`, line: r.line }));
  const stops = tab === "py" ? [11, 12, 13, 14] : [8, 9, 10, 12, 13];
  const cyc = useCycle(stops.length, 2400);
  useEffect(() => { cyc.set(0); cyc.setAuto(!reduceMotion()); }, [tab]); // eslint-disable-line react-hooks/exhaustive-deps
  const sel = stops[cyc.i % stops.length];
  const caption = tab === "ir"
    ? [c.provenance.tool, c.provenance.invocations[0], c.provenance.ir_link]
    : tab === "asm"
      ? [c.provenance.tool, c.provenance.invocations[1], c.provenance.asm_link]
      : [p.provenance.tool, p.provenance.invocation, p.provenance.link];
  return (
    <figure className="fg fg-lower">
      <div className="fg-tabs" role="tablist" aria-label="Lowered forms">
        {TABS.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>
      <div className="fg-body fg-two">
        <ol className="fg-src" aria-label="source lines">
          {src.map((s) => (
            <li key={s.n} data-on={s.n === sel ? "" : undefined}>
              <button type="button" disabled={!stops.includes(s.n)} onClick={() => cyc.set(stops.indexOf(s.n))}>
                <span className="n">{s.n}</span><code>{s.text}</code>
              </button>
            </li>
          ))}
        </ol>
        <ol className="fg-list" aria-label="lowered instructions">
          {rows.map((r, i) => (
            <li key={i} data-on={r.line === sel ? "" : undefined} data-off={r.line == null ? "" : undefined}>
              <span className="n">{r.line ?? ""}</span><code>{r.text}</code>
            </li>
          ))}
        </ol>
      </div>
      <Cap lines={["Recorded output · " + caption[0], caption[1], caption[2]]} />
    </figure>
  );
}

/* ———————————————————— a recorded run ———————————————————— */
type Step = { kind: string; fn: string | null; line: number | null; depth: number; locals?: Record<string, string>; ret?: string };

export function RunFigure() {
  const d = data.run;
  const steps = d.steps as Step[];
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(() => !reduceMotion());
  const hold = useRef(false);
  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => { if (!hold.current) setI((n) => (n + 1) % (steps.length + 3)); }, 780);
    return () => clearInterval(t);
  }, [playing, steps.length]);
  const at = Math.min(i, steps.length - 1);
  const cur = steps[at];
  // call stack at this step, rebuilt from the recorded call/return events
  const stack = useMemo(() => {
    const st: Array<{ fn: string; locals: Record<string, string>; line: number | null }> = [];
    for (let k = 0; k <= at; k++) {
      const s = steps[k];
      if (s.kind === "call") st.push({ fn: s.fn ?? "?", locals: s.locals ?? {}, line: s.line });
      else if (s.kind === "return" && k < at) st.pop();
      if (st.length && s.line != null && s.fn === st[st.length - 1].fn) st[st.length - 1].line = s.line;
    }
    return st;
  }, [at, steps]);
  const src = d.source.slice(9, 22);
  const done = i >= steps.length;
  return (
    <figure className="fg fg-run" onPointerEnter={() => { hold.current = true; }} onPointerLeave={() => { hold.current = false; }}>
      <div className="fg-body fg-two">
        <ol className="fg-src" aria-label="source lines">
          {src.map((s) => (
            <li key={s.n} data-on={cur.line === s.n && !done ? "" : undefined}>
              <span className="btn-like"><span className="n">{s.n}</span><code>{s.text}</code></span>
            </li>
          ))}
        </ol>
        <div className="fg-state" aria-live="off">
          <p className="fg-h">Call stack</p>
          <ul className="fg-stack">
            {stack.slice().reverse().map((f, k) => (
              <li key={`${f.fn}-${stack.length - k}`} data-top={k === 0 ? "" : undefined}>
                <b>{f.fn === "<module>" ? "module" : `${f.fn}()`}</b>
                <span>{Object.entries(f.locals).map(([a, v]) => `${a}=${v}`).join("  ")}</span>
              </li>
            ))}
          </ul>
          <p className="fg-h">Event</p>
          <p className="fg-ev"><b>{cur.kind}</b> {cur.fn === "<module>" ? "module" : cur.fn}{cur.line ? ` · line ${cur.line}` : ""}{cur.ret ? ` → ${cur.ret}` : ""}</p>
          <p className="fg-h">Output</p>
          <pre className="fg-out">{done ? d.stdout : "…"}</pre>
        </div>
      </div>
      <div className="fg-scrub">
        <button type="button" onClick={() => setPlaying((p) => !p)} aria-label={playing ? "Pause the replay" : "Play the replay"}>{playing ? "Pause" : "Play"}</button>
        <input type="range" min={0} max={steps.length - 1} value={at} onChange={(e) => { setPlaying(false); setI(+e.target.value); }} aria-label="Replay position" />
        <span>{at + 1} / {steps.length}</span>
      </div>
      <Cap lines={[
        `Recorded output · ${d.provenance.tool}`,
        `${d.provenance.demo} · ${d.provenance.events} events · exit ${d.provenance.exit_code} · trace sha256 ${d.provenance.trace_sha256.slice(0, 10)}…`,
      ]} />
    </figure>
  );
}
