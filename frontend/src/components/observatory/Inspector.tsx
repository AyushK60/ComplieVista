import { useState } from "react";
import { Selection } from "./types";
import StatusBadge from "../../ui/status";

/**
 * Contextual Inspector — explains whatever the user selected in any canvas:
 * what it is, why it exists, which source produced it, and its exact recorded
 * fields. Explanations are educational copy; fields are verbatim API data.
 */
export default function Inspector({ selection, onClose, onShowSource }: {
  selection: Selection | null;
  onClose: () => void;
  onShowSource: (line: number) => void;
}) {
  const [level, setLevel] = useState<"what" | "fields" | "raw">("what");

  if (!selection) {
    return (
      <div className="inspector panel">
        <div className="panel-h">Contextual Inspector</div>
        <div className="insp-empty">
          <p className="muted">
            Select anything — a token, an AST node, an instruction, a frame — and its
            story appears here: what it is, which source line produced it, and the
            exact recorded evidence.
          </p>
          <p className="muted insp-hint">Cross-stage links are shown only where the
            backend provides them; nothing is invented.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="inspector panel" aria-label="inspector">
      <div className="panel-h">
        <span className="insp-kind">{selection.subtitle ?? selection.stage}</span>
        <span className="spacer" />
        {selection.confidence && <StatusBadge code={String(selection.confidence)} />}
        <button className="btn ghost" onClick={onClose} aria-label="close inspector">✕</button>
      </div>
      <div className="insp-title">
        <h3>{selection.title}</h3>
        {selection.sourceLine != null && (
          <button className="btn ghost src-link"
                  onClick={() => onShowSource(selection.sourceLine!)}>
            ↦ source line {selection.sourceLine}
          </button>
        )}
      </div>

      <div className="insp-levels" role="tablist">
        <button role="tab" aria-selected={level === "what"} className={level === "what" ? "active" : ""}
                onClick={() => setLevel("what")}>What &amp; why</button>
        <button role="tab" aria-selected={level === "fields"} className={level === "fields" ? "active" : ""}
                onClick={() => setLevel("fields")}>Recorded fields</button>
        <button role="tab" aria-selected={level === "raw"} className={`${level === "raw" ? "active" : ""} tech-only`}
                onClick={() => setLevel("raw")}>Raw record</button>
      </div>

      {level === "what" && (
        <div className="insp-what">
          <p>{selection.what}</p>
          {selection.relations?.map((r) => r.items.length > 0 && (
            <div key={r.label} className="insp-rel">
              <h4>{r.label}</h4>
              <ul>{r.items.slice(0, 10).map((it, i) => <li key={i}><code>{it}</code></li>)}</ul>
            </div>
          ))}
          {selection.excerpt && <pre className="excerpt" tabIndex={0}>{selection.excerpt}</pre>}
        </div>
      )}
      {level === "fields" && (
        <table className="insp-fields">
          <tbody>
            {selection.fields.map(([k, v]) => (
              <tr key={k}><td>{k}</td><td><code>{v}</code></td></tr>
            ))}
          </tbody>
        </table>
      )}
      {level === "raw" && (
        <pre className="excerpt" tabIndex={0}>{JSON.stringify(selection.raw ?? {}, null, 2).slice(0, 3000)}</pre>
      )}
    </div>
  );
}
