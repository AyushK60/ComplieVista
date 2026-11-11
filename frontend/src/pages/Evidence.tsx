import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

/** Honest-evidence panel: every recorded artifact with tool, command, exit code, SHA-256,
 * counts and limitations, read straight from the backend's stage views (ADR-0002). */
interface Row {
  analysis: string; stage: string; availability: string; cls: string; tool: string;
  argv: string; exit: number | null; sha: string | null; bytes: number | null;
  counts: Record<string, number>; limits: string[];
}

async function j<T>(u: string): Promise<T> { const r = await fetch(u); if (!r.ok) throw new Error(`${u}: ${r.status}`); return r.json(); }

export default function Evidence() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  useEffect(() => {
    let alive = true;
    (async () => {
      const list = await j<Array<{ id: string; stages: string[] }>>("/api/v1/analyses");
      const out: Row[] = [];
      for (const a of list) {
        const m = await j<{ tools: Record<string, string> }>(`/api/v1/analyses/${a.id}`);
        const tools = Object.entries(m.tools).filter(([k]) => k !== "host").map(([, v]) => v);
        const views = await Promise.all(a.stages.map((s) =>
          j<Record<string, any>>(`/api/v1/analyses/${a.id}/stages/${s}`).catch(() => null)));
        views.forEach((v, i) => {
          if (!v) return;
          const inv = v.invocation ?? {};
          out.push({
            analysis: a.id, stage: a.stages[i], availability: v.availability, cls: v.observation_class ?? "",
            tool: inv.tool ?? inv.version ?? tools[0] ?? "", argv: (inv.argv ?? []).join(" "),
            exit: inv.exit_code ?? null, sha: v.artifact?.sha256 ?? null, bytes: v.artifact?.bytes ?? null,
            counts: v.counts ?? {}, limits: v.limitations ?? [],
          });
        });
      }
      if (alive) setRows(out);
    })().catch((e) => alive && setErr(String(e)));
    return () => { alive = false; };
  }, []);

  const shown = (rows ?? []).filter((r) => !q || JSON.stringify(r).toLowerCase().includes(q.toLowerCase()));
  return (
    <main className="obs evidence">
      <h1>Evidence</h1>
      <p className="muted">Every artifact the tool shows, with how it was produced. Nothing here is estimated: a field that was
        not recorded is shown as “not recorded”. Method and limits: <Link to="/about">About</Link>.</p>
      <label>Filter <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="stage, tool, sha…" /></label>
      {err && <p className="err">{err}</p>}
      {!rows && !err && <p className="muted"><span className="spinner" /> reading recorded evidence…</p>}
      {rows && (
        <div className="ev-scroll" role="region" tabIndex={0} aria-label="evidence table">
          <table className="ev-table">
            <caption className="sr-only">Recorded artifacts, {shown.length} rows</caption>
            <thead><tr><th>Analysis</th><th>Stage</th><th>Status</th><th>Command</th><th>Exit</th><th>SHA-256</th><th>Counts</th><th>Limitations</th></tr></thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.analysis + r.stage}>
                  <td>{r.analysis}</td>
                  <td>{r.stage}<br /><span className="muted">{r.cls}</span></td>
                  <td>{r.availability}</td>
                  <td><code>{r.argv ? r.argv.replace(/\/mnt\/e\/ComplieVista\//g, "") : "not recorded"}</code><br /><span className="muted">{r.tool}</span></td>
                  <td>{r.exit ?? "—"}</td>
                  <td><code title={r.sha ?? ""}>{r.sha ? r.sha.slice(0, 16) + "…" : "not recorded"}</code>{r.bytes != null && <><br /><span className="muted">{r.bytes} B</span></>}</td>
                  <td>{Object.entries(r.counts).map(([k, v]) => `${k}: ${v}`).join(", ") || "—"}</td>
                  <td>{r.limits.join(" ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
