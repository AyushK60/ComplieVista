import { useEffect, useMemo, useRef, useState } from "react";
import { experiments, LineMap } from "../../api";
import OptLearn, { LearnView } from "./OptLearn";

/**
 * Source <-> LLVM IR <-> assembly linking (Stage C).
 * Every link comes from the compiler's own debug info (`!dbg` / `.loc`), computed
 * server-side from the stored real artifacts. Nothing here is inferred: a source line
 * with no IR/asm simply has no link, and the -O0 vs -O2 table reports counts, not reasons.
 */
const LEVELS = ["O0", "O1", "O2"] as const;
const MAX_LINES = 600;

export default function SourceLinkView({ experimentId }: { experimentId: string }) {
  const [map, setMap] = useState<LineMap | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [level, setLevel] = useState<string>("O2");
  const qs = new URLSearchParams(window.location.search);
  const initView = qs.get("view");
  const [view, setView] = useState<LearnView>(
    initView === "diff" || initView === "lesson" || initView === "quiz" ? initView : "off");
  const [line, setLine] = useState<number | null>(() => Number(qs.get("line")) || null);
  const [focus, setFocus] = useState<"source" | "ir" | "asm" | null>(null);
  const [ir, setIr] = useState<string[] | null>(null);
  const [asm, setAsm] = useState<string[] | null>(null);
  const [onlyLinked, setOnlyLinked] = useState(true);
  const irRef = useRef<HTMLDivElement>(null);
  const asmRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    experiments.linemap(experimentId)
      .then((m) => { if (alive) setMap(m); })
      .catch((e) => { if (alive) setErr(String(e)); });
    return () => { alive = false; };
  }, [experimentId]);

  useEffect(() => {
    let alive = true;
    setIr(null); setAsm(null);
    Promise.all([
      experiments.artifact(experimentId, level, "ir").then((a) => a.excerpt.split("\n")),
      experiments.artifact(experimentId, level, "asm").then((a) => a.excerpt.split("\n")),
    ]).then(([i, a]) => { if (alive) { setIr(i); setAsm(a); } })
      .catch((e) => { if (alive) setErr(String(e)); });
    return () => { alive = false; };
  }, [experimentId, level]);

  const lm = map?.levels[level];
  const srcLines = useMemo(() => (map?.source ?? "").split("\n"), [map]);
  const linked = line != null ? lm?.by_source[String(line)] : undefined;
  const irSet = useMemo(() => new Set(linked?.ir ?? []), [linked]);
  const asmSet = useMemo(() => new Set(linked?.asm ?? []), [linked]);

  // scroll the first linked line of each pane into view when the selection changes
  useEffect(() => {
    const scroll = (root: HTMLDivElement | null, lines: number[]) => {
      if (!root || !lines.length) return;
      const el = root.querySelector<HTMLElement>(`[data-ln="${Math.min(...lines)}"]`);
      if (el) root.scrollTop = Math.max(el.offsetTop - 40, 0);
    };
    scroll(irRef.current, linked?.ir ?? []);
    scroll(asmRef.current, linked?.asm ?? []);
  }, [linked]);

  if (err) return <p className="err">Line linking: {err}</p>;
  if (!map) return <p className="muted"><span className="spinner" /> loading line links…</p>;
  if (!lm?.has_debug_info) {
    return <p className="muted">No debug-info line links are available for {level} in this build,
      so the source cannot be linked to its IR or assembly.</p>;
  }

  const paneLines = (text: string[] | null, map: Record<string, number>, hits: Set<number>) => {
    if (!text) return <p className="muted"><span className="spinner" /> loading…</p>;
    const rows: JSX.Element[] = [];
    for (let i = 1; i <= text.length && rows.length < MAX_LINES; i++) {
      const isLinked = String(i) in map;
      if (onlyLinked && !isLinked) continue;
      const srcLn = map[String(i)];
      rows.push(
        <div key={i} data-ln={i}
             className={"slv-row" + (hits.has(i) ? " hit" : "") + (isLinked ? " linked" : "")}
             onClick={isLinked ? () => setLine(srcLn) : undefined}
             title={isLinked ? `from source line ${srcLn}` : undefined}>
          <span className="slv-n">{i}</span>
          <code>{text[i - 1] || " "}</code>
          {isLinked && <span className="slv-src">L{srcLn}</span>}
        </div>);
    }
    return rows;
  };

  const cmp = map.compare_O0_O2;
  return (
    <div className="slv">
      <div className="slv-head">
        <b>Source ↔ IR ↔ assembly</b>
        <span className="muted">links come from the compiler's debug info; a line with no code has no link</span>
        <span className="spacer" />
        <label className="muted">level{" "}
          <select className="input" style={{ width: "auto" }} value={level} aria-label="level for line links"
                  onChange={(e) => { setLevel(e.target.value); setLine(null); }}>
            {LEVELS.filter((l) => map.levels[l]).map((l) => <option key={l}>{l}</option>)}
          </select>
        </label>
        <label className="muted">
          <input type="checkbox" checked={onlyLinked} onChange={(e) => setOnlyLinked(e.target.checked)} />{" "}
          only lines linked to source
        </label>
      </div>
      <div className="ol-tabs" role="group" aria-label="learning view">
        {([["off", "Explore links"], ["diff", "-O0 vs -O2 diff"], ["lesson", "Guided lesson"], ["quiz", "Quiz"]] as const).map(([v, l]) => (
          <button key={v} className="btn" aria-pressed={view === v} onClick={() => setView(v)}>{l}</button>
        ))}
        <button className="btn" onClick={() => window.print()} title="Print or save as PDF for lecture slides">Print / PDF</button>
      </div>
      <OptLearn experimentId={experimentId} map={map} srcLines={srcLines} view={view}
                line={line} setLine={setLine} setFocus={setFocus} />
      {lm.artifacts_truncated && (
        <p className="notice">The stored artifact for this level was truncated; links beyond the cut are not shown.</p>
      )}
      <div className={"slv-grid" + (focus ? " focus-" + focus : "")}>
        <section aria-label="source">
          <h5>Source</h5>
          <div className="slv-pane" tabIndex={0} role="region" aria-label="source lines">
            {srcLines.map((t, i) => {
              const n = i + 1;
              const b = lm.by_source[String(n)];
              const has = !!b && (b.ir.length > 0 || b.asm.length > 0);
              return (
                <div key={n} className={"slv-row" + (line === n ? " hit" : "") + (has ? " linked" : " nolink")}
                     onClick={() => setLine(n)} role="button" tabIndex={0}
                     onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setLine(n); } }}
                     aria-pressed={line === n}>
                  <span className="slv-n">{n}</span>
                  <code>{t || " "}</code>
                  {has && <span className="slv-cnt" title="IR instructions / asm instructions">{b.ir.length}·{b.asm.length}</span>}
                </div>
              );
            })}
          </div>
        </section>
        <section aria-label="LLVM IR">
          <h5>LLVM IR <span className="muted">{linked ? `${linked.ir.length} linked` : ""}</span></h5>
          <div className="slv-pane" ref={irRef} tabIndex={0} role="region" aria-label="LLVM IR lines">{paneLines(ir, lm.ir_to_source, irSet)}</div>
        </section>
        <section aria-label="assembly">
          <h5>Assembly <span className="muted">{linked ? `${linked.asm.length} linked` : ""}</span></h5>
          <div className="slv-pane" ref={asmRef} tabIndex={0} role="region" aria-label="assembly lines">{paneLines(asm, lm.asm_to_source, asmSet)}</div>
        </section>
      </div>
      <p className="muted">
        {line == null
          ? "Click a source line (or any highlighted IR/asm line) to see what it became."
          : linked && (linked.ir.length || linked.asm.length)
            ? `Source line ${line} produced ${linked.ir.length} IR and ${linked.asm.length} assembly instruction(s) at ${level}.`
            : `Source line ${line} has no code at ${level} (nothing was emitted for it).`}
        {lm.ir_inlined.length ? ` ${lm.ir_inlined.length} IR instructions come from inlined calls and are attributed to the callee's source line.` : ""}
      </p>

      {cmp && (
        <div className="slv-cmp">
          <h5>What -O2 did to each source line, compared with -O0 <span className="muted">(instruction counts, not reasons)</span></h5>
          <div className="optdiff-legend">
            <span className="badge blocked">no code at -O2 ×{cmp.removed.length}</span>
            <span className="badge derived">fewer asm ×{cmp.shrunk.length}</span>
            <span className="badge ok">more asm ×{cmp.grown.length}</span>
            <span className="muted">
              total asm instructions linked: {cmp.totals.asm[0]} → {cmp.totals.asm[1]}
            </span>
          </div>
          <table className="insp-fields" aria-label="per-line comparison">
            <thead><tr><td>line</td><td>source</td><td>IR O0→O2</td><td>asm O0→O2</td><td></td></tr></thead>
            <tbody>
              {cmp.rows.map((r) => {
                const tag = cmp.removed.includes(r.line) ? ["blocked", "no code at -O2"]
                  : cmp.new.includes(r.line) ? ["ok", "only at -O2"]
                  : cmp.grown.includes(r.line) ? ["ok", "more asm"]
                  : cmp.shrunk.includes(r.line) ? ["derived", "fewer asm"] : null;
                return (
                  <tr key={r.line} className={"slv-cmprow" + (line === r.line ? " hit" : "")}
                      onClick={() => setLine(r.line)} style={{ cursor: "pointer" }}>
                    <td>{r.line}</td>
                    <td><code>{(srcLines[r.line - 1] ?? "").trim().slice(0, 48)}</code></td>
                    <td>{r.ir[0]} → {r.ir[1]}</td>
                    <td>{r.asm[0]} → {r.asm[1]}</td>
                    <td>{tag && <span className={`badge ${tag[0]}`}>{tag[1]}</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
