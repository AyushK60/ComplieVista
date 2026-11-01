import { useCallback, useEffect, useState } from "react";
import { Experiment, experiments } from "../api";

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
 * M6-E OptimizationLab — real per-level build artifacts (ir/asm/symbols with
 * digests), an honest A/B assembly diff, and uninstrumented benchmark samples.
 * Static assembly is labeled as static: it is NOT an executed-instruction count.
 */
export default function OptimizationLab({ snapshotId, targetId, language }: {
  snapshotId: string; targetId: string; language: string;
}) {
  const [optId, setOptId] = useState<string | null>(null);
  const [opt, setOpt] = useState<Experiment | null>(null);
  const [benchId, setBenchId] = useState<string | null>(null);
  const [bench, setBench] = useState<Experiment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [levelA, setLevelA] = useState<string>("O0");
  const [levelB, setLevelB] = useState<string>("O2");
  const [asmA, setAsmA] = useState<string | null>(null);
  const [asmB, setAsmB] = useState<string | null>(null);

  if (language !== "c") {
    return (
      <div className="optlab" role="region" aria-label="OptimizationLab">
        <h3>OptimizationLab</h3>
        <p className="muted">LLVM -O levels apply to the C pipeline only. Python has
          no optimization levels — its bytecode comparison lives in the
          Compare view (CPython 3.12 compiler behavior, version-pinned).</p>
      </div>
    );
  }

  const poll = useCallback(async (id: string, set: (e: Experiment) => void) => {
    const e = await experiments.get(id);
    set(e);
    if (["QUEUED", "RUNNING"].includes(e.status)) setTimeout(() => poll(id, set), 1000);
  }, []);

  // M6QA-01: never show a previous target's experiments when the selection
  // changes (same staleness class fixed for executions in M5QA).
  useEffect(() => {
    setOptId(null); setOpt(null);
    setBenchId(null); setBench(null);
    setAsmA(null); setAsmB(null);
    setError(null);
  }, [snapshotId, targetId]);

  useEffect(() => {
    if (optId) poll(optId, setOpt).catch((e) => setError(String(e)));
  }, [optId, poll]);
  useEffect(() => {
    if (benchId) poll(benchId, setBench).catch((e) => setError(String(e)));
  }, [benchId, poll]);

  useEffect(() => {
    if (opt?.status !== "COMPLETED") return;
    (async () => {
      try {
        const [a, b] = await Promise.all([
          experiments.artifact(opt.id, levelA, "asm"),
          experiments.artifact(opt.id, levelB, "asm"),
        ]);
        setAsmA(a.excerpt); setAsmB(b.excerpt);
      } catch (e) { setError(String(e)); }
    })();
  }, [opt, levelA, levelB]);

  const start = async (kind: "opt" | "bench") => {
    setBusy(true); setError(null);
    try {
      const ref = await experiments.create(
        kind === "opt" ? { kind, snapshot_id: snapshotId, target_id: targetId }
          : { kind, snapshot_id: snapshotId, target_id: targetId,
              config: { repeats: 7 } });
      if (kind === "opt") { setOptId(ref.experiment_id ?? null); setOpt(null); }
      else { setBenchId(ref.experiment_id ?? null); setBench(null); }
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    setBusy(false);
  };

  const stageRow = (lvl: string) => {
    const s = opt?.stages.find((x) => x.stage === lvl);
    if (!s) return null;
    const r = s.result as Record<string, unknown>;
    const tool = r.tool as Record<string, string> | undefined;
    return (
      <tr key={lvl}>
        <td>-{lvl}</td>
        <td>{String(r.exe_bytes ?? "—")} B</td>
        <td>{r.ir ? "✓" : "—"}</td>
        <td>{r.asm ? "✓" : "—"}</td>
        <td>{r.symbols ? "✓" : "—"}</td>
        <td>{String((r.steps as Record<string, Record<string, number>> | undefined)
          ?.link?.duration_ms ?? "—")} ms</td>
        <td className="muted">{tool ? String(tool.clang) : ""}</td>
      </tr>
    );
  };

  return (
    <div className="optlab" role="region" aria-label="OptimizationLab">
      <h3>OptimizationLab (C · real Clang 18.1.3 builds)</h3>
      <p className="muted">Uninstrumented builds per level; static assembly is NOT an
        executed-instruction count. The same source snapshot is compiled under
        recorded allowlisted flags only.</p>
      <p>
        <button className="primary" disabled={busy} onClick={() => start("opt")}>
          Build -O0/-O1/-O2
        </button>{" "}
        <button disabled={busy} onClick={() => start("bench")}>
          Benchmark (uninstrumented, ≥5 repeats)
        </button>
      </p>
      {error && <p className="err">{error}</p>}
      {opt && opt.status !== "COMPLETED" && <p className="muted">Building… ({opt.status})</p>}
      {opt?.status === "COMPLETED" && (
        <>
          <table className="grid" aria-label="per-level build results">
            <thead><tr><th>level</th><th>exe size</th><th>IR</th><th>ASM</th>
              <th>symbols</th><th>link time</th><th>tool</th></tr></thead>
            <tbody>{LEVELS.map(stageRow)}</tbody>
          </table>
          <h4>Assembly diff (A/B, static artifacts)</h4>
          <p>
            A: <select value={levelA} onChange={(e) => setLevelA(e.target.value)}
                       aria-label="baseline level">
              {LEVELS.map((l) => <option key={l}>{l}</option>)}
            </select>{" "}
            B: <select value={levelB} onChange={(e) => setLevelB(e.target.value)}
                       aria-label="comparison level">
              {LEVELS.map((l) => <option key={l}>{l}</option>)}
            </select>
          </p>
          {asmA && asmB && (
            <pre className="excerpt diff" aria-label="assembly diff">
              {lineDiff(asmA, asmB).slice(0, 400).map(([mark, line], i) => (
                <div key={i} className={
                  mark === "-" ? "diff-del" : mark === "+" ? "diff-add" : ""}>
                  {mark} {line}
                </div>
              ))}
            </pre>
          )}
          <p className="muted">Digests: {opt.stages.map((s) =>
            `${s.stage}:${(s.result as Record<string, unknown>).exe_bytes}B`).join(" · ")}</p>
        </>
      )}
      {bench && bench.status !== "COMPLETED" && (
        <p className="muted">Benchmarking… ({bench.status})</p>)}
      {bench?.status === "COMPLETED" && (() => {
        const st = bench.stages.find((x) => x.stage === "bench");
        const r = st?.result as Record<string, unknown> | undefined;
        const levels = (r?.levels ?? {}) as Record<string, Record<string, unknown>>;
        const env = (r?.env ?? {}) as Record<string, string>;
        return (
          <>
            <h4>Benchmark (uninstrumented; warmup excluded)</h4>
            <table className="grid" aria-label="benchmark results">
              <thead><tr><th>level</th><th>wall median</th><th>min/max</th>
                <th>stdev</th><th>n</th><th>CPU median</th><th>checksums</th></tr></thead>
              <tbody>
                {Object.entries(levels).map(([lvl, rec]) => {
                  const wall = rec.wall as Record<string, number>;
                  return (
                    <tr key={lvl}>
                      <td>{lvl}</td><td>{wall.median_ms} ms</td>
                      <td>{wall.min_ms}/{wall.max_ms} ms</td>
                      <td>{wall.stdev_ms} ms</td><td>{wall.n}</td>
                      <td>{(rec.cpu as Record<string, number>).median_ms} ms</td>
                      <td>{rec.checksums_identical ? "identical ✓" : "DIFFER ✗"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="muted">
              env: {String(env.cpu_model ?? "cpu n/a")} · kernel {String(env.kernel)} ·
              cgroup cpu {String(env.cgroup_cpu_max)} / mem {String(env.cgroup_memory_max)} ·
              wall vs CPU are separate metrics · checksums guard semantics and
              dead-code elimination across levels.
              {Object.values(levels).some((l) => l.resolution_warning)
                ? " ⚠ Some samples are below reliable timer resolution — treat as indicative." : ""}
            </p>
          </>
        );
      })()}
    </div>
  );
}
