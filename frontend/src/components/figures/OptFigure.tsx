import { useState } from "react";
import data from "../../data/optDiff.json";

/** Home figure: what -O2 did to each line of a real C demo, from recorded compiler output
 * (scripts/media/build_opt_figure.py). Counts and instructions only; no reasons are claimed. */
type Row = { line: number; text: string; asm: number[]; ir: number[]; o0: string[]; o2: string[] };
const rows = data.rows as Row[];

export default function OptFigure() {
  const first = rows.find((r) => r.asm[1] === 0) ?? rows[0];
  const [sel, setSel] = useState<number>(first.line);
  const r = rows.find((x) => x.line === sel) ?? first;
  const max = Math.max(...rows.map((x) => Math.max(x.asm[0], x.asm[1])));
  const p = data.provenance;
  return (
    <figure className="optfig">
      <div className="optfig-rows" role="listbox" aria-label="source lines, -O0 to -O2 instruction counts">
        {rows.map((x) => (
          <button key={x.line} role="option" aria-selected={x.line === sel} className={x.line === sel ? "on" : ""}
                  onClick={() => setSel(x.line)}>
            <span className="n">{x.line}</span>
            <code>{x.text.trim()}</code>
            <span className="bars" aria-hidden="true">
              <i className="b0" style={{ width: `${(x.asm[0] / max) * 100}%` }} />
              <i className="b2" style={{ width: `${(x.asm[1] / max) * 100}%` }} />
            </span>
            <span className="c">{x.asm[0]} → {x.asm[1]}</span>
          </button>
        ))}
      </div>
      <div className="optfig-asm" aria-live="polite">
        <div><h4>-O0 · {r.asm[0]} instructions</h4><pre tabIndex={0}>{r.o0.join("\n") || "(none)"}</pre></div>
        <div><h4>-O2 · {r.asm[1]} instructions</h4><pre tabIndex={0}>{r.o2.join("\n") || "(none: no code emitted for this line)"}</pre></div>
      </div>
      <figcaption>
        Demo {p.demo}. Total linked assembly {data.totals.asm[0]} → {data.totals.asm[1]}. {p.tool}, {p.levels.O0.flags.join(" ")} vs{" "}
        {p.levels.O2.flags.join(" ")}; asm SHA-256 {p.levels.O0.asm_sha256.slice(0, 10)}… / {p.levels.O2.asm_sha256.slice(0, 10)}…
      </figcaption>
    </figure>
  );
}
