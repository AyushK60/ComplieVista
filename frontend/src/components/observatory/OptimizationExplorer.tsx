import { useCallback, useEffect, useState } from "react";
import { Experiment, experiments } from "../../api";

/** Minimal LCS line diff for asm/IR comparison (bounded inputs ≤ 24 KB). */
function lineDiff(a: string, b: string): Array<[" " | "-" | "+", string]> {
  const la = a.split("\n");
  const lb = b.split("\n");
  const n = Math.min(la.length, 400), m = Math.min(lb.length, 400);
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      dp[i][j] = la[i] === lb[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const out: Array<[" " | "-" | "+", string]> = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (la[i] === lb[j]) { out.push([" ", la[i]]); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { out.push(["-", la[i]]); i++; }
    else { out.push(["+", lb[j]]); j++; }
  }
  while (i < n) { out.push(["-", la[i]]); i++; }
  while (j < m) { out.push(["+", lb[j]]); j++; }
  return out;
}

const LEVELS = ["O0", "O1", "O2"] as const;

/**
 * Optimization Explorer — genuine per-level Clang builds (recorded flags only),
 * side-by-side static artifact comparison and uninstrumented benchmarks.
 * Python honestly has no O-levels; its comparison story lives in the Compare view.
 */
export default function OptimizationExplorer({ snapshotId, targetId, language }: {
  snapshotId: string; targetId: string; language: string;
}) {
  const [optId, setOptId] = useState<string | null>(null);
  const [opt, setOpt] = useState<Experiment | null>(null);
  const [benchId, setBenchId] = useState<string | null>(null);
  const [bench, setBench] = useState<Experiment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [levelA, setLevelA] = useState("O0");
  const [levelB, setLevelB] = useState("O2");
  const [artA, setArtA] = useState<string | null>(null);
  const [artB, setArtB] = useState<string | null>(null);
  const [kind, setKind] = useState<"asm" | "ir">("asm");

  const poll = useCallback(async (id: string, set: (e: Experiment) => void) => {
    const e = await experiments.get(id);
    set(e);
    if (["QUEUED", "RUNNING"].includes(e.status)) setTimeout(() => poll(id, set), 1000);
  }, []);

  useEffect(() => {
    setOptId(null); setOpt(null); setBenchId(null); setBench(null);
    setArtA(null); setArtB(null); setError(null);
  }, [snapshotId, targetId]);

  useEffect(() => { if (optId) poll(optId, setOpt).catch((e) => setError(String(e))); }, [optId, poll]);
  useEffect(() => { if (benchId) poll(benchId, setBench).catch((e) => setError(String(e))); }, [benchId, poll]);

  useEffect(() => {
    if (opt?.status !== "COMPLETED") return;
    (async () => {
      try {
        const [a, b] = await Promise.all([
          experiments.artifact(opt.id, levelA, kind),
          experiments.artifact(opt.id, levelB, kind),
        ]);
        setArtA(a.excerpt); setArtB(b.excerpt);
      } catch (e) { setError(String(e)); }
    })();
  }, [opt, levelA, levelB, kind]);

  const start = async (k: "opt" | "bench") => {
    setBusy(true); setError(null);
    try {
      const ref = await experiments.create(
        k === "opt" ? { kind: k, snapshot_id: snapshotId, target_id: targetId }
          : { kind: k, snapshot_id: snapshotId, target_id: targetId, config: { repeats: 7 } });
      if (k === "opt") { setOptId(ref.experiment_id ?? null); setOpt(null); }
      else { setBenchId(ref.experiment_id ?? null); setBench(null); }
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(false);
  };

  if (language !== "c") {
    return (
      <div className="optexplorer panel">
        <div className="panel-h">Optimization Explorer</div>
        <div className="unavailable" style={{ margin: 16 }}>
          <span className="glyph">◈</span>
          <div>LLVM -O levels apply to the C pipeline only. <b>Python has no optimization
            levels</b> — its CPython 3.12 compiler behavior is version-pinned, and
            cross-language comparison lives in the Compare view.</div>
        </div>
      </div>
    );
  }

  const exeBytes = (lvl: string) => {
    const s = opt?.stages.find((x: { stage: string }) => x.stage === lvl);
    return s ? Number((s.result as Record<string, unknown>).exe_bytes) : null;
  };

  return (
    <div className="optexplorer panel">
      <div className="panel-h">Optimization Explorer
        <span className="spacer" />
        <span className="muted">real Clang builds · recorded flags only · static artifacts, never executed-instruction counts</span>
      </div>
      <div className="optactions">
        <button className="btn primary" disabled={busy} onClick={() => start("opt")}>
          Build -O0 / -O1 / -O2
        </button>
        <button className="btn" disabled={busy} onClick={() => start("bench")}>
          Benchmark (uninstrumented, ≥5 repeats)
        </button>
        {opt?.status === "COMPLETED" && (
          <div className="optsizebars">
            {LEVELS.map((l) => {
              const b = exeBytes(l);
              const max = Math.max(...LEVELS.map(exeBytes).map((v) => v ?? 0), 1);
              return b != null ? (
                <span key={l} className="sizebar" title={`-O${l.slice(1)}: ${b} bytes`}>
                  <span className="muted">-{l}</span>
                  <span className="sb-track"><span className="sb-fill"
                    style={{ width: `${(b / max) * 100}%` }} /></span>
                  <span className="muted">{b} B</span>
                </span>
              ) : null;
            })}
          </div>
        )}
      </div>
      {error && <p className="err" style={{ padding: "0 16px" }}>{error}</p>}
      {opt && opt.status !== "COMPLETED" && (
        <p className="notice" style={{ padding: "0 16px" }}><span className="spinner" /> Building… ({opt.status})</p>
      )}

      {opt?.status === "COMPLETED" && (
        <div className="optbody">
          <div className="optab-head">
            <b>{levelA}</b>
            <select className="input" style={{ width: "auto" }} value={levelA} aria-label="baseline level"
                    onChange={(e) => setLevelA(e.target.value)}>
              {LEVELS.map((l) => <option key={l}>{l}</option>)}
            </select>
            <span className="opt-vs">vs</span>
            <b>{levelB}</b>
            <select className="input" style={{ width: "auto" }} value={levelB} aria-label="comparison level"
                    onChange={(e) => setLevelB(e.target.value)}>
              {LEVELS.map((l) => <option key={l}>{l}</option>)}
            </select>
            <span className="spacer" />
            <div className="sc-viewtoggle" role="tablist">
              <button role="tab" aria-selected={kind === "asm"} className={kind === "asm" ? "active" : ""}
                      onClick={() => setKind("asm")}>Assembly</button>
              <button role="tab" aria-selected={kind === "ir"} className={kind === "ir" ? "active" : ""}
                      onClick={() => setKind("ir")}>LLVM IR</button>
            </div>
          </div>
          {artA && artB ? (
            <div className="optdiff">
              <pre className="excerpt diff">{lineDiff(artA, artB).slice(0, 400).map(([mark, line], i) => (
                <div key={i} className={mark === "-" ? "diff-del" : mark === "+" ? "diff-add" : ""}>
                  {mark} {line}
                </div>
              ))}</pre>
            </div>
          ) : <p className="muted"><span className="spinner" /> loading artifacts…</p>}
          <p className="muted">
            What this can tell you: how the emitted {kind === "asm" ? "assembly" : "IR"} differs
            between levels (fewer instructions, hoisted constants, eliminated work) and code
            size changes. What it cannot: per-pass decisions or wall-clock speed — use the
            benchmark for measured timing on this machine only.
          </p>
        </div>
      )}

      {bench && bench.status !== "COMPLETED" && (
        <p className="notice" style={{ padding: "0 16px" }}><span className="spinner" /> Benchmarking… ({bench.status})</p>
      )}
      {bench?.status === "COMPLETED" && (() => {
        const st = bench.stages.find((x: { stage: string }) => x.stage === "bench");
        const r = st?.result as Record<string, unknown> | undefined;
        const levels = (r?.levels ?? {}) as Record<string, Record<string, unknown>>;
        const env = (r?.env ?? {}) as Record<string, string>;
        return (
          <div className="optbody">
            <h4>Benchmark <span className="badge derived">uninstrumented · container-throttled</span></h4>
            <table className="insp-fields">
              <thead><tr><td></td><td>wall median</td><td>min / max</td><td>stdev</td><td>n</td><td>CPU median</td><td>checksums</td></tr></thead>
              <tbody>
                {Object.entries(levels).map(([lvl, rec]) => {
                  const wall = rec.wall as Record<string, number>;
                  return (
                    <tr key={lvl}>
                      <td><b>-{lvl}</b></td>
                      <td><code>{wall.median_ms} ms</code></td>
                      <td><code>{wall.min_ms} / {wall.max_ms} ms</code></td>
                      <td><code>{wall.stdev_ms} ms</code></td>
                      <td>{wall.n}</td>
                      <td><code>{(rec.cpu as Record<string, number>).median_ms} ms</code></td>
                      <td>{rec.checksums_identical
                        ? <span className="badge ok">identical</span>
                        : <span className="badge blocked">DIFFER — outputs vary</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="muted">
              {String(env.cpu_model ?? "cpu n/a")} · kernel {String(env.kernel)} · cgroup cpu {String(env.cgroup_cpu_max)} / mem {String(env.cgroup_memory_max)} ·
              wall and CPU are separate metrics · checksums guard semantics across levels.
              {Object.values(levels).some((l) => l.resolution_warning)
                ? " ⚠ Some samples are below reliable timer resolution — treat as indicative." : ""}
              {" "}Numbers describe this container on this machine — never universal speed claims.
            </p>
          </div>
        );
      })()}
    </div>
  );
}
