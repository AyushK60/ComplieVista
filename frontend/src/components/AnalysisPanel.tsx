import { useEffect, useState } from "react";
import { ApiError, AnalysisJob, api, Reason, StageData } from "../api";

/**
 * M2 analysis panel: real job lifecycle + language-specific stage views backed by
 * genuine container-run toolchain outputs. Clicking a token/AST node/bytecode
 * instruction with a known source line calls onSelectLine for source highlighting.
 * Mapping honesty: EXACT positions are clickable; IR/assembly are DERIVED/UNAVAILABLE.
 */

const AVAIL_CLASS: Record<string, string> = {
  AVAILABLE: "chip ok", PARTIAL: "chip partial", ERROR: "chip blocked",
  UNSUPPORTED: "chip blocked", BLOCKED: "chip blocked", NOT_REQUESTED: "chip",
};

type Item = Record<string, unknown>;

function AsTree({ nodes, onSelect }: { nodes: Item[]; onSelect: (n: Item) => void }) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const byParent = new Map<string | null, Item[]>();
  for (const n of nodes) {
    const p = (n.parent as string | null) ?? null;
    if (!byParent.has(p)) byParent.set(p, []);
    byParent.get(p)!.push(n);
  }
  const toggle = (id: string) => {
    const next = new Set(collapsed);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setCollapsed(next);
  };
  const render = (n: Item, depth: number): React.ReactNode => {
    const id = n.id as string;
    const kids = byParent.get(id) ?? [];
    const open = depth < 1 || !collapsed.has(id);
    const line = n.line as number | null;
    return (
      <div key={id} style={{ marginLeft: depth * 14 }}>
        <span className="astnode" onClick={() => onSelect(n)}>
          <button className="tw" onClick={(e) => { e.stopPropagation(); toggle(id); }}>
            {kids.length ? (open ? "▾" : "▸") : "·"}
          </button>
          <code>{n.kind as string}</code>
          {n.name ? <strong> {n.name as string}</strong> : null}
          {line ? <span className="muted"> :{line}:{n.col as number}</span> : null}
        </span>
        {open && kids.map((k) => render(k, depth + 1))}
      </div>
    );
  };
  const roots = byParent.get(null) ?? [];
  return <div className="tree">{roots.map((r) => render(r, 0))}</div>;
}

export default function AnalysisPanel({
  analysisId, onSelectLine,
}: { analysisId: string; onSelectLine: (line: number | null) => void }) {
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [stageName, setStageName] = useState<string | null>(null);
  const [stageData, setStageData] = useState<StageData | null>(null);
  const [raw, setRaw] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const j = await api.analysis(analysisId);
        if (!alive) return;
        setJob(j);
        if (["QUEUED", "RUNNING"].includes(j.status)) {
          setTimeout(poll, 800);
        } else if (j.stages.length && !stageName) {
          const first = j.stages.find((s) => s.availability === "AVAILABLE") ?? j.stages[0];
          setStageName(first.stage);
        }
      } catch (e) {
        if (alive) setError(String(e));
      }
    };
    poll();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysisId]);

  useEffect(() => {
    if (!stageName || !job || ["QUEUED", "RUNNING"].includes(job.status)) return;
    setRaw(null);
    api.stage(analysisId, stageName).then(setStageData).catch((e) => {
      setStageData(null);
      setError(e instanceof ApiError ? e.message : String(e));
    });
  }, [stageName, analysisId, job?.status]);

  if (!job) return <p className="muted">Loading analysis…</p>;
  if (["QUEUED", "RUNNING"].includes(job.status)) {
    return (
      <div className="analysis">
        <p className="notice">Analysis {job.status.toLowerCase()}… (bounded container run)
          <button className="cancel" onClick={() => api.cancelAnalysis(analysisId)}>Cancel</button>
        </p>
      </div>
    );
  }
  if (job.status === "BLOCKED") {
    return <p className="err">Analysis BLOCKED: {job.error_code} (Docker unavailable in this environment)</p>;
  }
  if (job.status !== "COMPLETED") {
    return <p className="err">Analysis {job.status}: {job.error_code ?? "no stage output produced"}</p>;
  }

  const selectLine = (line: unknown) => {
    onSelectLine(typeof line === "number" ? line : null);
  };

  const renderItems = () => {
    const s = stageData;
    if (!s) return null;
    const items = s.items;
    if (s.stage === "tokens") {
      return (
        <div className="tokenRibbon">
          {items.map((t, i) => (
            <span key={i} className="token clickable" title={`${t.file}:${t.line}:${t.col}`}
                  onClick={() => selectLine(t.line)}>
              {String(t.text ?? "")}
            </span>
          ))}
          {s.truncated && <span className="muted"> …truncated</span>}
        </div>
      );
    }
    if (s.stage === "ast") {
      if (items.length && "parent" in items[0]) {
        return <AsTree nodes={items} onSelect={(n) => selectLine(n.line)} />;
      }
      return <p className="muted">No AST nodes available (see raw output).</p>;
    }
    if (s.stage.startsWith("ir_")) {
      return (
        <div>
          <p className="muted">Basic blocks and edges are DERIVED from real terminators;
            source→IR mapping is UNAVAILABLE in M2.</p>
          {(items as Array<Record<string, unknown>>).map((f, i) => (
            <div key={i} className="irfunc">
              <p><code>define @{String(f.name)}</code></p>
              <ol className="blocks">
                {(f.blocks as Array<Record<string, unknown>>).map((b, j) => (
                  <li key={j}>
                    <code>{String(b.label)}</code>
                    {((b.terminators as string[]) ?? []).length > 0 && (
                      <span className="muted"> → {((b.successors as string[]) ?? []).join(", ") || "exit"}</span>)}
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </div>
      );
    }
    if (s.stage === "assembly") {
      return <p className="muted">{JSON.stringify(s.counts)} — full raw listing available below.</p>;
    }
    if (s.stage === "object") {
      return <p className="muted">object sha256 <code>{String(s.counts.object_sha256)}</code> · {String(s.counts.bytes)} bytes</p>;
    }
    if (s.stage === "code_object") {
      // CV-06: real code-object metadata explorer (version-pinned CPython 3.12).
      return (
        <table className="grid">
          <thead>
            <tr><th>id</th><th>name</th><th>qualname</th><th>argcount</th><th>varnames</th><th>consts</th></tr>
          </thead>
          <tbody>
            {items.map((it, i) => (
              <tr key={i}>
                <td><code>{String(it.id)}</code></td>
                <td>{String(it.name)}</td>
                <td>{String(it.qualname)}</td>
                <td>{String(it.argcount)}</td>
                <td>{(it.varnames as string[] | undefined)?.join(", ") || "—"}</td>
                <td>{(it.consts_noncode as string[] | undefined)?.length ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      );
    }
    if (s.stage === "symbols" || s.stage === "disassembly" || s.stage === "bytecode") {
      return (
        <table className="grid">
          <tbody>
            {items.map((it, i) => (
              <tr key={i} onClick={() => selectLine(
                s.stage === "bytecode" ? (it.positions ? (it.positions as number[])[0] : null) : null)}
                  className={s.stage === "bytecode" ? "clickable" : ""}>
                {Object.entries(it).slice(0, 6).map(([k, v]) => (
                  <td key={k}><span className="k">{k}</span> {String(v)?.slice(0, 60)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      );
    }
    if (items.length && ("severity" in items[0] || "error_type" in items[0])) {
      if ("error_type" in items[0]) {
        const d = items[0];
        return (
          <div className="diags">
            <div className="diag error" onClick={() => selectLine(d.lineno)}>
              <span className="sev error">{String(d.error_type)}</span>{" "}
              line {String(d.lineno)}:{String(d.offset)} — <code>{String(d.msg)}</code>
              {d.text ? <pre className="excerpt">{String(d.text)}</pre> : null}
            </div>
          </div>
        );
      }
      return (
        <ul className="diags">
          {(items as Array<Record<string, unknown>>).filter((d) => "severity" in d).map((d, i) => (
            <li key={i} className={`diag ${d.severity as string}`} onClick={() => selectLine(d.line)}>
              <code>{String(d.file)}:{String(d.line)}:{String(d.col)}</code>{" "}
              <span className={`sev ${d.severity as string}`}>{String(d.severity)}</span>{" "}
              {String(d.message)}
            </li>
          ))}
        </ul>
      );
    }
    return <p className="muted">Stage produced no normalized items — check raw output.</p>;
  };

  return (
    <div className="analysis">
      <div className="stagenav" role="tablist">
        {job.stages.map((s) => (
          <button key={s.stage} role="tab" aria-selected={stageName === s.stage}
                  className={stageName === s.stage ? "tab active" : "tab"}
                  onClick={() => setStageName(s.stage)}>
            {s.stage} <span className={AVAIL_CLASS[s.availability] ?? "chip"}>{s.availability}</span>
          </button>
        ))}
      </div>
      {stageData && (
        <>
          <p className="muted provenance">
            observation_class={stageData.observation_class} · exit={stageData.exit_code} ·{" "}
            {stageData.duration_ms}ms · raw <code>{stageData.raw_artifact_sha256?.slice(0, 16)}…</code> ·{" "}
            stderr <code>{stageData.stderr_artifact_sha256?.slice(0, 16)}…</code>
            {stageData.truncated && <span className="chip partial"> truncated</span>}
            {stageData.invocation?.tool_versions?.clang && (
              <> · clang <code>{String(stageData.invocation.tool_versions.clang).split(" ").slice(-1)[0]}</code></>)}
            {stageData.invocation?.tool_versions?.cpython && (
              <> · CPython <code>{String(stageData.invocation.tool_versions.cpython)}</code></>)}
            {" · worker: "}{String(stageData.invocation?.worker ?? "?")}
          </p>
          {stageData.limitations.length > 0 && (
            <ul className="limits">{stageData.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>
          )}
          {renderItems()}
          {stageData.raw_artifact_sha256 && (
            <RawToggle key={`${analysisId}:${stageData.stage}`}
                       analysisId={analysisId} stage={stageData.stage} />
          )}
        </>
      )}
      {error && <p className="err">{error}</p>}
      <p className="muted">{job.note}</p>
    </div>
  );
}

function RawToggle({ analysisId, stage }: { analysisId: string; stage: string }) {
  const [raw, setRaw] = useState<string | null>(null);
  const [show, setShow] = useState(false);
  // Remounted per (analysis, stage) via key; refetches on mount so raw text can
  // never be shown under another stage's name (CV-04).
  useEffect(() => {
    let alive = true;
    setRaw(null);
    setShow(false);
    api.stageRaw(analysisId, stage).then((r) => {
      if (alive) setRaw(r.excerpt);
    }).catch(() => { /* excerpt stays null */ });
    return () => { alive = false; };
  }, [analysisId, stage]);
  if (!show) {
    return <button className="primary" onClick={() => setShow(true)}>Show raw tool output</button>;
  }
  return (
    <div>
      <button className="primary" onClick={() => setShow(false)}>Hide raw</button>
      <pre className="excerpt">{raw ?? "loading…"}</pre>
    </div>
  );
}
