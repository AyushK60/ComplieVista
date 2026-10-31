import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api, FileDetail, Project, Reason, SnapshotDetail, StageData, Target } from "../api";
import type { GraphSelection } from "../components/GraphView";
import AnalysisPanel from "../components/AnalysisPanel";
import CodeView from "../components/CodeView";
import Inspector from "../components/Inspector";

type Mode = "paste" | "upload" | "github";

const STATUS_CLASS: Record<string, string> = {
  STATIC_ANALYZABLE: "chip ok",
  COMPILATION_CANDIDATE: "chip partial",
  EXECUTABLE_CANDIDATE: "chip partial",
  READY_FOR_CONTROLLED_EXECUTION: "chip ok",
  BLOCKED: "chip blocked",
  UNSUPPORTED: "chip blocked",
};

function StatusChip({ status }: { status: string }) {
  return <span className={STATUS_CLASS[status] ?? "chip"}>{status}</span>;
}

export default function Workspace() {
  const [mode, setMode] = useState<Mode>("paste");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // paste inputs
  const [language, setLanguage] = useState("python");
  const [filename, setFilename] = useState("demo.py");
  const [content, setContent] = useState("x = 41\nx += 1\nif __name__ == '__main__':\n    print(x)\n");
  // github inputs
  const [ghUrl, setGhUrl] = useState("https://github.com/antirez/kilo");
  const [ghRef, setGhRef] = useState("");

  const [project, setProject] = useState<Project | null>(null);
  const [snapshot, setSnapshot] = useState<SnapshotDetail | null>(null);
  const [targets, setTargets] = useState<Target[]>([]);
  const [selected, setSelected] = useState<FileDetail | null>(null);
  const [tools, setTools] = useState<Record<string, { available: boolean; version: string }>>({});
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [highlightLine, setHighlightLine] = useState<number | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [selection, setSelection] = useState<GraphSelection>(null);
  const [stageData, setStageData] = useState<StageData | null>(null);

  useEffect(() => {
    api.capabilities().then((c) => setTools(c.tools)).catch(() => setTools({}));
  }, []);

  async function loadProject(pid: string) {
    const [proj, tgts] = await Promise.all([api.project(pid), api.targets(pid)]);
    const sid = proj.snapshots[0]?.id;
    if (!sid) throw new ApiError({ code: "NO_SNAPSHOT", message: "project has no snapshot" });
    const snap = await api.snapshot(pid, sid);
    setProject(proj);
    setTargets(tgts);
    setSnapshot(snap);
    const preferred =
      snap.files.find((f) => f.language === "python") ?? snap.files.find((f) => f.language === "c") ?? snap.files[0];
    if (preferred) setSelected(await api.file(pid, sid, preferred.id));
  }

  async function runIngest(action: () => Promise<{ project_id: string; rejected_count: number; existed: boolean }>) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const r = await action();
      await loadProject(r.project_id);
      setNotice(
        `${r.existed ? "Existing snapshot returned (idempotent)" : "Snapshot created"} · ` +
          `${r.rejected_count} archive entr${r.rejected_count === 1 ? "y" : "ies"} rejected` +
          (r.rejected_count ? ` (see diagnostics)` : ""),
      );
    } catch (e) {
      if (e instanceof ApiError) setError({ code: e.code, message: e.body.message });
      else setError({ code: "CLIENT", message: String(e) });
    } finally {
      setBusy(false);
    }
  }

  const fileTargets = (rel: string) => targets.filter((t) => t.primary_file === rel);
  const orderedFiles = snapshot
    ? [...snapshot.files].sort((a, b) => {
        const rank = (f: { language: string; rel_path: string }) =>
          (f.language === "python" ? 0 : f.language === "c" ? 1 : 2) + f.rel_path.localeCompare(b.rel_path) * 0;
        const r = rank(a) - rank(b);
        return r !== 0 ? r : a.rel_path.localeCompare(b.rel_path);
      })
    : [];

  async function selectFile(id: string) {
    if (!project || !snapshot) return;
    setSelected(await api.file(project.id, snapshot.id, id));
    setAnalysisId(null);
    setHighlightLine(null);
    setAnalyzeError(null);
    setSelection(null);
    setStageData(null);
  }

  const selectedTargets = selected ? fileTargets(selected.rel_path) : [];
  const ANALYZABLE = new Set(["STATIC_ANALYZABLE", "COMPILATION_CANDIDATE", "EXECUTABLE_CANDIDATE"]);
  const analyzableTarget = selectedTargets.find(
    (t) => ANALYZABLE.has(t.status) && selected?.language !== "other");

  async function startAnalysis() {
    if (!snapshot || !analyzableTarget) return;
    setAnalyzeError(null);
    setAnalysisId(null);
    try {
      const ref = await api.createAnalysis(snapshot.id, analyzableTarget.target_id);
      setAnalysisId(ref.analysis_id);
    } catch (e) {
      setAnalyzeError(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <main>
      <nav className="topnav">
        <strong>CompileVista</strong>
        <Link to="/">Home</Link>
        <Link to="/workspace">Source Workspace</Link>
        <span className="muted" style={{ marginLeft: "auto" }}>
          {Object.entries(tools)
            .filter(([, v]) => v.available)
            .map(([k, v]) => `${k} ${v.version.split(" ").slice(-1)[0]}`)
            .join(" · ")}
        </span>
      </nav>
      <h1>Source Workspace</h1>
      <p className="muted">
        Paste, upload or import public GitHub repositories. Sources become immutable SHA-256
        snapshots; nothing is ever executed just by being added.
      </p>

      <section className="ingest">
        <div className="tabs" role="tablist">
          {(["paste", "upload", "github"] as Mode[]).map((m) => (
            <button key={m} role="tab" aria-selected={mode === m}
                    className={mode === m ? "tab active" : "tab"}
                    onClick={() => setMode(m)} disabled={busy}>
              {m === "paste" ? "Paste" : m === "upload" ? "Upload" : "GitHub import"}
            </button>
          ))}
        </div>

        {mode === "paste" && (
          <div>
            <div className="row">
              <label>
                Language{" "}
                <select value={language}
                        onChange={(e) => {
                          setLanguage(e.target.value);
                          setFilename(e.target.value === "python" ? "demo.py" : "demo.c");
                        }}>
                  <option value="python">Python</option>
                  <option value="c">C</option>
                </select>
              </label>
              <label>
                Filename <input value={filename} onChange={(e) => setFilename(e.target.value)} />
              </label>
            </div>
            <textarea className="paste" rows={10} value={content}
                      onChange={(e) => setContent(e.target.value)}
                      aria-label="paste source code" />
            <button className="primary" disabled={busy}
                    onClick={() => runIngest(() => api.paste(language, filename, content))}>
              Create snapshot
            </button>
          </div>
        )}

        {mode === "upload" && (
          <div>
            <p className="muted">
              Individual <code>.c</code> <code>.h</code> <code>.py</code> files or one bounded
              <code> .zip</code> (≤ 25 MB compressed; hostile entries are rejected and reported).
            </p>
            <input type="file" multiple
                   accept=".c,.h,.py,.zip"
                   aria-label="upload source files"
                   disabled={busy}
                   onChange={(e) => {
                     const files = Array.from(e.target.files ?? []);
                     if (files.length) runIngest(() => api.upload(files));
                   }} />
          </div>
        )}

        {mode === "github" && (
          <div>
            <div className="row">
              <label style={{ flex: 1 }}>
                Public repository URL{" "}
                <input style={{ width: "100%" }} value={ghUrl}
                       onChange={(e) => setGhUrl(e.target.value)}
                       placeholder="https://github.com/OWNER/REPO" />
              </label>
              <label>
                Ref (optional) <input value={ghRef} onChange={(e) => setGhRef(e.target.value)}
                                       placeholder="branch/tag/sha" />
              </label>
            </div>
            <button className="primary" disabled={busy}
                    onClick={() => runIngest(() => api.importGithub(ghUrl, ghRef || undefined))}>
              Import pinned revision
            </button>
          </div>
        )}

        {busy && <p className="notice">Working…</p>}
        {notice && <p className="notice">{notice}</p>}
        {error && (
          <p className="err">
            {error.code}: {error.message}
          </p>
        )}
      </section>

      {project && snapshot && (
        <section className="workspace">
          <h2>{project.name}</h2>
          <p className="muted">
            snapshot <code>{snapshot.combined_sha256.slice(0, 24)}…</code> · origin{" "}
            <code>{snapshot.origin}</code> · {snapshot.files.length} file(s)
            {snapshot.diagnostics.length > 0 && <> · {snapshot.diagnostics.length} recorded intake diagnostics</>}
          </p>
          <div className="cols">
            <div className="filelist" role="list">
              {orderedFiles.map((f) => {
                const tg = fileTargets(f.rel_path);
                const status = tg[0]?.status;
                return (
                  <button key={f.id} role="listitem"
                          className={selected?.id === f.id ? "fileitem active" : "fileitem"}
                          onClick={() => selectFile(f.id)}>
                    <span className="fname">{f.rel_path}</span>
                    <span className="fmeta">{f.language} · {f.size} B</span>
                    {status && <StatusChip status={status} />}
                  </button>
                );
              })}
            </div>
            <div className="detail">
              {selected ? (
                <>
                  <CodeView text={selected.text ?? "(binary content not previewable)"}
                            path={selected.rel_path}
                            language={selected.language}
                            highlightLine={highlightLine} />
                  <p className="muted">
                    sha256 <code>{selected.content_sha256.slice(0, 32)}…</code> · encoding{" "}
                    <code>{selected.encoding}</code>
                  </p>
                  <h3>Targets for this file</h3>
                  {selectedTargets.length === 0 && (
                    <p className="muted">No compilation targets detected for this file.</p>
                  )}
                  {selectedTargets.map((t) => (
                    <div className="target" key={t.target_id}>
                      <p>
                        <code>{t.kind}</code> <StatusChip status={t.status} />{" "}
                        {t.ready_for_controlled_execution ? null : (
                          <span className="chip blocked">execution: gated by M4</span>
                        )}
                      </p>
                      <ul className="reasons">
                        {t.reasons.map((r: Reason, i: number) => (
                          <li key={i}>
                            <code>{r.code}</code> — {r.detail}{" "}
                            <em className={r.verified ? "ok" : "unverified"}>
                              [{r.verified ? "verified" : "detected"}]
                            </em>
                          </li>
                        ))}
                      </ul>
                      {t === analyzableTarget && (
                        <button className="primary" onClick={startAnalysis} disabled={!snapshot}>
                          Analyze with real {selected.language === "c" ? "Clang/LLVM 18" : "CPython 3.12"} (static)
                        </button>
                      )}
                      {t !== analyzableTarget && (
                        <button className="analyze" disabled title=
                          "No bounded analysis path for this target yet; execution requires the M4 security gate.">
                          Analyze
                        </button>
                      )}
                    </div>
                  ))}
                  {analyzeError && <p className="err">Analyze failed: {analyzeError}</p>}
                  {analysisId && <AnalysisPanel analysisId={analysisId}
                                                onSelectLine={(l) => setHighlightLine(l)}
                                                onSelectNode={setSelection}
                                                onSelectStageData={setStageData} />}
                  {analysisId && selection && (
                    <Inspector selection={selection} stageData={stageData}
                               onClose={() => setSelection(null)} />
                  )}
                </>
              ) : (
                <p className="muted">Select a file.</p>
              )}
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
