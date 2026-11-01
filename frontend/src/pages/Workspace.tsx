import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  AnalysisJob, ApiError, api, FileDetail, Project, Reason, SnapshotDetail,
  StageData, Target, demos, executions,
} from "../api";
import SourceDock from "../components/observatory/SourceDock";
import JourneyNavigator from "../components/observatory/JourneyNavigator";
import StageCanvas from "../components/observatory/StageCanvas";
import Inspector from "../components/observatory/Inspector";
import ExecutionDock from "../components/observatory/ExecutionDock";
import ProgramWalkthrough from "../components/observatory/ProgramWalkthrough";
import OptimizationExplorer from "../components/observatory/OptimizationExplorer";
import { SourceSpan } from "../components/observatory/TokenFormation";
import { Selection } from "../components/observatory/types";

/**
 * M8 Observatory — one cohesive source-to-execution environment.
 * Source Dock | Journey Navigator + Visual Canvas | Contextual Inspector,
 * with the Execution & Systems dock under the canvas. Stages and availability
 * always come from the real analysis job; nothing is invented or auto-run.
 */

type Mode = "paste" | "upload" | "github";

const STATUS_LABEL: Record<string, string> = {
  STATIC_ANALYZABLE: "static-analyzable",
  COMPILATION_CANDIDATE: "compiles",
  EXECUTABLE_CANDIDATE: "executable",
  READY_FOR_CONTROLLED_EXECUTION: "execution-ready",
  BLOCKED: "blocked",
  UNSUPPORTED: "unsupported",
};

function StatusChip({ status }: { status: string }) {
  const cls = status.startsWith("READY") ? "chip ok"
    : status === "BLOCKED" || status === "UNSUPPORTED" ? "chip blocked" : "chip partial";
  return <span className={cls}>{STATUS_LABEL[status] ?? status}</span>;
}

export default function Workspace() {
  const [params, setParams] = useSearchParams();
  // ——— ingest ———
  const [mode, setMode] = useState<Mode>("paste");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [language, setLanguage] = useState("python");
  const [filename, setFilename] = useState("demo.py");
  const [content, setContent] = useState(
    "def area(base, height):\n    return base * height / 2\n\n\ndef main():\n    print(area(3, 4))\n\n\nif __name__ == '__main__':\n    main()\n");
  const [ghUrl, setGhUrl] = useState("https://github.com/antirez/kilo");
  const [ghRef, setGhRef] = useState("");

  // ——— observatory state ———
  const [project, setProject] = useState<Project | null>(null);
  const [snapshot, setSnapshot] = useState<SnapshotDetail | null>(null);
  const [targets, setTargets] = useState<Target[]>([]);
  const [selected, setSelected] = useState<FileDetail | null>(null);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [stageName, setStageName] = useState<string | null>(null);
  const [stageData, setStageData] = useState<StageData | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [highlightLine, setHighlightLine] = useState<number | null>(null);
  const [linked, setLinked] = useState(false);
  const [executionId, setExecutionId] = useState<string | null>(null);
  const [guided, setGuided] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [demoMeta, setDemoMeta] = useState<string | null>(null);
  const [optPair, setOptPair] = useState<{ snapshotId: string; targetId: string } | null>(null);
  const [hoverSpan, setHoverSpan] = useState<SourceSpan | null>(null);
  // starts collapsed; opens automatically when something is selected (1.3)
  const [inspectorOpen, setInspectorOpen] = useState(() =>
    localStorage.getItem("cv.inspector") === "open");
  const [sourceW, setSourceW] = useState(() => {
    const v = Number(localStorage.getItem("cv.sourceW"));
    return v >= 260 && v <= 560 ? v : 340;
  });
  const [canvasFull, setCanvasFull] = useState(false);
  // view switch: compilation stages, the recorded run, or the optimization lab —
  // siblings in one viewport-oriented workspace instead of a scrolling page
  const [view, setView] = useState<"compile" | "execution" | "walkthrough" | "optimization">(
    () => (new URLSearchParams(window.location.search).get("walkthrough") ? "walkthrough"
      : new URLSearchParams(window.location.search).get("execution") ? "execution" : "compile"));
  const dragRef = useRef<{ startX: number; startW: number } | null>(null);
  const stageSeqRef = useRef(0);

  const startDockDrag = (e: React.MouseEvent) => {
    dragRef.current = { startX: e.clientX, startW: sourceW };
    const move = (ev: MouseEvent) => {
      if (!dragRef.current) return;
      const w = Math.max(260, Math.min(560, dragRef.current.startW + ev.clientX - dragRef.current.startX));
      setSourceW(w);
    };
    const up = () => {
      dragRef.current = null;
      setSourceW((w) => { localStorage.setItem("cv.sourceW", String(w)); return w; });
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  };

  // full-screen exploration locks page scroll
  useEffect(() => {
    document.body.classList.toggle("fs-lock", canvasFull);
    return () => document.body.classList.remove("fs-lock");
  }, [canvasFull]);

  // Entering the Syntax Tree stage opens the existing canvas focus once per
  // navigation into AST view. A manual exit stays respected while the user
  // remains on the stage; leaving the stage re-arms it for the next visit.
  const astFocusArmedRef = useRef(true);
  useEffect(() => {
    if (stageName === "ast") {
      if (astFocusArmedRef.current) {
        astFocusArmedRef.current = false;
        setCanvasFull(true);
      }
    } else {
      astFocusArmedRef.current = true;
    }
  }, [stageName]);

  // The watch scene produces no inspector selections and needs the width;
  // collapse the inspector when the user enters it (the rail can reopen it).
  useEffect(() => {
    if (view === "walkthrough" && inspectorOpen) {
      setInspectorOpen(false);
      localStorage.setItem("cv.inspector", "collapsed");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);

  const showLine = useCallback((line: number | null, isLinked = true) => {
    setHighlightLine(line);
    setLinked(isLinked);
  }, []);

  /* ——— demo deep-link: /workspace?analysis=&execution=&snapshot=&target= ——— */
  useEffect(() => {
    const aId = params.get("analysis");
    const eId = params.get("execution");
    const sId = params.get("snapshot");
    const tId = params.get("target");
    if (aId) setAnalysisId(aId);
    if (eId) setExecutionId(eId);
    if (tId && sId) setOptPair({ snapshotId: sId, targetId: tId });
    if (sId) {
      (async () => {
        try {
          // demo snapshots live under the fixed 'demo-library' project id
          // (backend demos.py); personal snapshots use their real project id.
          const pid = params.get("project") ?? (await api.projects()
            .then((ps) => ps.find((p) => p.snapshot_id === sId)?.id) ?? "demo-library");
          const proj: Project = { id: pid, name: pid === "demo-library" ? "Demo Library" : pid,
            created_utc: "", snapshots: [{ id: sId, origin: "demo", combined_sha256: "" }] };
          const snap = await api.snapshot(pid, sId);
          setProject(proj); setSnapshot(snap); setTargets(await api.targets(pid));
          const want = params.get("file") ?? "";
          const primary = snap.files.find((f) => f.rel_path === want)
            ?? snap.files.find((f) => f.rel_path.endsWith(want)) ?? snap.files[0];
          if (primary) setSelected(await api.file(pid, sId, primary.id));
          const demoId = params.get("demo");
          if (demoId) {
            const all = await demos.list();
            const d = all.demos.find((x) => x.id === demoId);
            if (d) setDemoMeta(`${d.id} — ${d.title}`);
          }
        } catch { /* demo deep-link best effort */ }
      })();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ——— analysis job polling ——— */
  useEffect(() => {
    if (!analysisId) { setJob(null); return; }
    let alive = true;
    const poll = async () => {
      try {
        const j = await api.analysis(analysisId);
        if (!alive) return;
        setJob(j);
        if (["QUEUED", "RUNNING"].includes(j.status)) setTimeout(poll, 800);
        else if (j.stages.length && !stageName) {
          const first = j.stages.find((s) => s.availability === "AVAILABLE")
            ?? j.stages.find((s) => s.stage === "tokens") ?? j.stages[0];
          setStageName(first.stage);
        }
      } catch (e) { if (alive) setAnalyzeError(String(e)); }
    };
    poll();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysisId]);

  /* ——— stage data (stale-result guarded) ——— */
  useEffect(() => {
    if (!analysisId || !stageName || !job || ["QUEUED", "RUNNING"].includes(job.status)) return;
    const seq = ++stageSeqRef.current;
    setStageData(null);
    setSelection(null);
    api.stage(analysisId, stageName).then((sd) => {
      if (seq === stageSeqRef.current) setStageData(sd);
    }).catch(() => { if (seq === stageSeqRef.current) setStageData(null); });
  }, [stageName, analysisId, job?.status]);

  async function loadProject(pid: string) {
    const [proj, tgts] = await Promise.all([api.project(pid), api.targets(pid)]);
    const sid = proj.snapshots[0]?.id;
    if (!sid) throw new ApiError({ code: "NO_SNAPSHOT", message: "project has no snapshot" });
    const snap = await api.snapshot(pid, sid);
    setProject(proj); setTargets(tgts); setSnapshot(snap);
    const preferred = snap.files.find((f) => f.language === "python")
      ?? snap.files.find((f) => f.language === "c") ?? snap.files[0];
    if (preferred) setSelected(await api.file(pid, sid, preferred.id));
    setAnalysisId(null); setJob(null); setStageName(null); setStageData(null);
    setExecutionId(null); setSelection(null); setOptPair(null);
  }

  async function runIngest(action: () => Promise<{ project_id: string }>) {
    setBusy(true); setError(null);
    try { await loadProject((await action()).project_id); }
    catch (e) { setError(e instanceof ApiError ? `${e.code}: ${e.body.message}` : String(e)); }
    setBusy(false);
  }

  function selectFile(id: string) {
    if (!project || !snapshot) return;
    (async () => {
      setSelected(await api.file(project.id, snapshot.id, id));
      setAnalysisId(null); setJob(null); setStageName(null); setStageData(null);
      setExecutionId(null); setSelection(null); setOptPair(null);
      showLine(null, false);
    })();
  }

  const fileTargets = (rel: string) => targets.filter((t) => t.primary_file === rel);
  const ANALYZABLE = new Set(["STATIC_ANALYZABLE", "COMPILATION_CANDIDATE", "EXECUTABLE_CANDIDATE"]);
  const selectedTargets = selected ? fileTargets(selected.rel_path) : [];
  const runnableTarget = selectedTargets.find(
    (t) => (t.status === "EXECUTABLE_CANDIDATE" || t.status === "COMPILATION_CANDIDATE")
      && snapshot?.origin !== "github");
  const analyzableTarget = selectedTargets.find(
    (t) => ANALYZABLE.has(t.status) && selected?.language !== "other");

  async function startRun(profile?: string) {
    if (!snapshot || !runnableTarget) return;
    setRunError(null);
    try {
      const ref = await executions.create(snapshot.id, runnableTarget.target_id, profile);
      setExecutionId(ref.execution_id);
      // the user asked to run: the run becomes the visible view (1.5 mapping)
      setView(profile === "debug" ? "execution" : "execution");
      if (profile !== "debug") setOptPair({ snapshotId: snapshot.id, targetId: runnableTarget.target_id });
      const next = new URLSearchParams(params);
      next.set("execution", ref.execution_id);
      next.set("snapshot", snapshot.id);
      next.set("target", runnableTarget.target_id);
      if (!next.get("project")) next.set("project", project?.id ?? "");
      setParams(next, { replace: true });
    } catch (e) { setRunError(e instanceof ApiError ? e.message : String(e)); }
  }

  async function startAnalysis() {
    if (!snapshot || !analyzableTarget) return;
    setAnalyzeError(null);
    try {
      const ref = await api.createAnalysis(snapshot.id, analyzableTarget.target_id);
      setStageName(null);
      setAnalysisId(ref.analysis_id);
      // persist so reload keeps the journey
      const next = new URLSearchParams(params);
      next.set("analysis", ref.analysis_id);
      setParams(next, { replace: true });
    } catch (e) { setAnalyzeError(e instanceof ApiError ? e.message : String(e)); }
  }

  const sourceText = selected?.text ?? "";
  const lang = selected?.language ?? job?.language ?? "python";

  const header = useMemo(() => {
    if (!project || !snapshot) return null;
    return (
      <div className="obs-head">
        <div className="obs-title">
          <h1>{demoMeta ?? project.name}</h1>
          {demoMeta && <span className="chip ok">demo program</span>}
          <span className="chip">{lang === "c" ? "C · Clang/LLVM 18" : "Python · CPython 3.12"}</span>
          <span className="chip">{snapshot.origin}</span>
        </div>
        <p className="muted tech-only">
          snapshot <code>{snapshot.combined_sha256.slice(0, 24)}…</code> ·{" "}
          {snapshot.files.length} file(s) · nothing executes by being added
        </p>
      </div>
    );
  }, [project, snapshot, lang, demoMeta]);

  /* ——— ingest (empty state) ——— */
  if (!project || !snapshot) {
    return (
      <main className="obs obs-empty">
        <div className="obs-ingest panel">
          <h1>Bring a program to the observatory</h1>
          <p className="muted">
            Paste source, upload files, or import a public GitHub repository. Everything
            becomes an immutable SHA-256 snapshot. Nothing is ever executed just by being added.
          </p>
          <div className="ingest-tabs" role="tablist">
            {(["paste", "upload", "github"] as Mode[]).map((m) => (
              <button key={m} role="tab" aria-selected={mode === m}
                      className={mode === m ? "active" : ""} onClick={() => setMode(m)} disabled={busy}>
                {m === "paste" ? "Paste code" : m === "upload" ? "Upload files" : "GitHub import"}
              </button>
            ))}
          </div>
          {mode === "paste" && (
            <div className="ingest-body">
              <div className="row2">
                <label>Language
                  <select className="input" value={language}
                          onChange={(e) => {
                            setLanguage(e.target.value);
                            setFilename(e.target.value === "python" ? "demo.py" : "demo.c");
                          }}>
                    <option value="python">Python</option>
                    <option value="c">C</option>
                  </select>
                </label>
                <label>Filename
                  <input className="input" value={filename} onChange={(e) => setFilename(e.target.value)} />
                </label>
              </div>
              <textarea className="input paste-area" rows={12} value={content} aria-label="paste source code"
                        spellCheck={false}
                        onChange={(e) => setContent(e.target.value)} />
              <button className="btn primary" disabled={busy}
                      onClick={() => runIngest(() => api.paste(language, filename, content))}>
                Create snapshot
              </button>
            </div>
          )}
          {mode === "upload" && (
            <div className="ingest-body">
              <p className="muted">
                Individual <code>.c</code> <code>.h</code> <code>.py</code> files or one bounded
                <code> .zip</code> (≤ 25 MB). Hostile archive entries are rejected and reported.
              </p>
              <input type="file" multiple accept=".c,.h,.py,.zip" aria-label="upload source files"
                     disabled={busy}
                     onChange={(e) => {
                       const files = Array.from(e.target.files ?? []);
                       if (files.length) runIngest(() => api.upload(files));
                     }} />
            </div>
          )}
          {mode === "github" && (
            <div className="ingest-body">
              <div className="row2">
                <label style={{ flex: 1 }}>Public repository URL
                  <input className="input" value={ghUrl} placeholder="https://github.com/OWNER/REPO"
                         onChange={(e) => setGhUrl(e.target.value)} />
                </label>
                <label>Ref (optional)
                  <input className="input" value={ghRef} placeholder="branch/tag/sha"
                         onChange={(e) => setGhRef(e.target.value)} />
                </label>
              </div>
              <button className="btn primary" disabled={busy}
                      onClick={() => runIngest(() => api.importGithub(ghUrl, ghRef || undefined))}>
                Import pinned revision
              </button>
              <p className="muted">Imported repositories are analyzed read-only; their code is
                never compiled or executed.</p>
            </div>
          )}
          {busy && <p className="notice"><span className="spinner" /> Working…</p>}
          {error && <p className="err">{error}</p>}
          <p className="muted">Looking for a quick start? Pick a program in the{" "}
            <Link to="/demos">Demo Library</Link>.</p>
        </div>
      </main>
    );
  }

  /* ——— observatory (viewport-oriented app) ——— */
  return (
    <main className="obs obs-app">
      {header}
      <div className="obs-filebar" role="list" aria-label="snapshot files">
        {[...snapshot.files]
          .sort((a, b) => a.rel_path.localeCompare(b.rel_path))
          .map((f) => {
            const st = fileTargets(f.rel_path)[0]?.status;
            return (
              <button key={f.id} role="listitem"
                      className={"filechip" + (selected?.id === f.id ? " active" : "")}
                      onClick={() => selectFile(f.id)}>
                <code>{f.rel_path}</code>
                {st && <StatusChip status={st} />}
              </button>
            );
          })}
        <span className="spacer" />
        {analyzableTarget && (
          <button className="btn primary" onClick={startAnalysis} disabled={!!analysisId && ["QUEUED", "RUNNING"].includes(job?.status ?? "")}>
            {analysisId && job && ["QUEUED", "RUNNING"].includes(job.status)
              ? <><span className="spinner" /> analyzing…</>
              : `Analyze with ${lang === "c" ? "Clang/LLVM 18" : "CPython 3.12"}`}
          </button>
        )}
        {runnableTarget && (
          <>
            <button className="btn run" onClick={() => startRun()}>Run in restricted container</button>
            <button className="btn" onClick={() => startRun("debug")}
                    title="MemoryScope debugger capture — curated allowlisted C fixtures only (ADR-0008); other code is refused with an explanation.">
              Debug run (curated)
            </button>
          </>
        )}
      </div>
      {analyzableTarget && analyzableTarget !== runnableTarget && analyzableTarget.reasons.length > 0 && (
        <ul className="obs-reasons tech-only">
          {analyzableTarget.reasons.slice(0, 3).map((r: Reason, i: number) => (
            <li key={i}><code>{r.code}</code> — {r.detail} <em>[{r.verified ? "verified" : "detected"}]</em></li>
          ))}
        </ul>
      )}
      {analyzeError && <p className="err">Analyze failed: {analyzeError}</p>}
      {runError && <p className="err">Run failed: {runError}</p>}
      {job && ["BLOCKED", "FAILED", "TIMEOUT"].includes(job.status) && (
        <p className="err">Analysis {job.status}: {job.error_code ?? "no stage output"}</p>
      )}

      {job && ["QUEUED", "RUNNING"].includes(job.status) && (
        <p className="notice"><span className="spinner" /> Analysis {job.status.toLowerCase()}… bounded container run
          <button className="btn ghost" onClick={() => api.cancelAnalysis(analysisId!)}>Cancel</button>
        </p>
      )}

      {(job?.status === "COMPLETED" || (executionId && !analysisId)) && (
        <>
        <div className="obs-viewtabs" role="tablist" aria-label="workspace views">
          <button role="tab" aria-selected={view === "compile"} className={view === "compile" ? "active" : ""}
                  onClick={() => setView("compile")}>Compilation journey</button>
          {executionId && (
            <button role="tab" aria-selected={view === "execution"} className={view === "execution" ? "active" : ""}
                    onClick={() => setView("execution")}>Execution observatory</button>
          )}
          {executionId && (
            <button role="tab" aria-selected={view === "walkthrough"} className={view === "walkthrough" ? "active" : ""}
                    onClick={() => setView("walkthrough")}>Watch it work</button>
          )}
          {optPair && (
            <button role="tab" aria-selected={view === "optimization"} className={view === "optimization" ? "active" : ""}
                    onClick={() => setView("optimization")}>Optimization lab</button>
          )}
        </div>
        <div className={"obs-grid" + (inspectorOpen ? "" : " insp-collapsed")}>
          <div className="obs-left" style={{ width: sourceW, flex: `0 0 ${sourceW}px` }}>
            <SourceDock text={sourceText} path={selected?.rel_path ?? "?"} language={lang}
                        activeLine={highlightLine} linked={linked} activeSpan={hoverSpan}
                        onSelectLine={(l) => showLine(l, false)} />
            <div className="obs-filemeta muted tech-only">
              sha256 <code>{selected?.content_sha256.slice(0, 32)}…</code> · encoding <code>{selected?.encoding}</code>
            </div>
            <div className="dock-handle" role="separator" aria-orientation="vertical"
                 aria-label="resize source dock" onMouseDown={startDockDrag} />
          </div>

          <div className={"obs-center" + (view === "walkthrough" ? " obs-center-flow" : "")}>
            {view === "compile" && job?.status === "COMPLETED" && (
              <JourneyNavigator job={job} stageName={stageName} language={lang}
                                guided={guided} onToggleGuided={setGuided}
                                onSelectStage={(s) => setStageName(s)} />
            )}
            {view === "compile" && stageData ? (
              <div className={"obs-canvas panel" + (canvasFull ? " fullscreen" : "")}>
                <button className={"btn ghost fs-toggle" + (canvasFull ? " fs-exit" : "")}
                        onClick={() => setCanvasFull((v) => !v)}
                        title={canvasFull ? "exit full-screen exploration" : "expand the canvas to full screen"}
                        aria-pressed={canvasFull}>
                  {canvasFull ? "✕ exit focus" : "⤢ focus"}
                </button>
                {canvasFull && (() => {
                  const order = (job?.stages ?? [])
                    .filter((s) => s.availability !== "ERROR")
                    .map((s) => s.stage);
                  const i = order.indexOf(stageName ?? "");
                  const lineText = highlightLine != null
                    ? (sourceText.split("\n")[highlightLine - 1] ?? "").trim() : null;
                  return (
                    <>
                      <div className="fs-bar">
                        <button className="btn ghost" disabled={i <= 0}
                                onClick={() => i > 0 && setStageName(order[i - 1])} aria-label="previous stage">←</button>
                        <b>{stageName}</b>
                        <button className="btn ghost" disabled={i < 0 || i >= order.length - 1}
                                onClick={() => i >= 0 && i < order.length - 1 && setStageName(order[i + 1])} aria-label="next stage">→</button>
                        {lineText != null && (
                          <span className="fs-srcline muted">
                            line {highlightLine}: <code>{lineText.slice(0, 80) || "—"}</code>
                          </span>
                        )}
                      </div>
                      {selection && (
                        <div className="fs-inspector">
                          <Inspector selection={selection} onClose={() => setSelection(null)}
                                     onShowSource={(l) => showLine(l, true)} />
                        </div>
                      )}
                    </>
                  );
                })()}
                <StageCanvas analysisId={analysisId!} stageData={stageData} sourceText={sourceText}
                             language={lang} onSelect={(sel) => {
                               setSelection(sel);
                               if (sel) { setInspectorOpen(true); localStorage.setItem("cv.inspector", "open"); }
                             }}
                             onSelectLine={(l) => showLine(l, true)} activeLine={highlightLine}
                             onHoverSpan={setHoverSpan} guided={guided}
                             onNavigateStage={(st) => setStageName(st)}
                             fullscreen={canvasFull}
                             sourceFocusLine={linked ? null : highlightLine} />
              </div>
            ) : view === "compile" && job?.status === "COMPLETED" ? (
              <div className="obs-canvas panel canvas-loading">
                <p className="muted"><span className="spinner" /> loading stage…</p>
              </div>
            ) : view === "compile" ? (
              <div className="obs-canvas panel canvas-loading">
                <p className="muted">
                  This run is loaded in the <b>Execution observatory</b> view (tab above).
                  Click <b>Analyze</b> in the header to open the static compilation journey
                  (tokens → AST → {lang === "c" ? "IR → assembly" : "bytecode"}).
                </p>
              </div>
            ) : null}
            {view === "execution" && executionId && (
              <ExecutionDock executionId={executionId} onSelectLine={(l) => showLine(l, true)}
                             activeLine={highlightLine} />
            )}
            {view === "walkthrough" && executionId && (
              <ProgramWalkthrough executionId={executionId} sourceText={sourceText}
                                  onSelectLine={(l) => showLine(l, true)} />
            )}
            {view === "optimization" && optPair && (
              <OptimizationExplorer snapshotId={optPair.snapshotId} targetId={optPair.targetId} language={lang} />
            )}
          </div>

          {inspectorOpen ? (
            <div className="obs-right">
              <Inspector selection={selection} onClose={() => { setInspectorOpen(false); localStorage.setItem("cv.inspector", "collapsed"); }}
                         onShowSource={(l) => showLine(l, true)} />
            </div>
          ) : (
            <div className="obs-right-rail">
              <button onClick={() => setInspectorOpen(true)}>contextual inspector</button>
            </div>
          )}
        </div>
        </>
      )}
    </main>
  );
}
