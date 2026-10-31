import { useMemo } from "react";

/** Read-only source view with line numbers (M1) + selected-line highlight (M2). */
export default function CodeView({ text, path, highlightLine }: {
  text: string; path: string; highlightLine?: number | null;
}) {
  const lines = useMemo(() => text.split("\n"), [text]);
  return (
    <div className="codeview" aria-label={`source of ${path}`}>
      <div className="codeview-title">
        <code>{path}</code>
      </div>
      <div className="codeview-body">
        <ol className="gutter" start={1}>
          {lines.map((_, i) => (
            <li key={i} className={highlightLine === i + 1 ? "hl" : undefined}>{i + 1}</li>
          ))}
        </ol>
        <pre className="code">
          {lines.map((l, i) => (
            <div className={`codeline ${highlightLine === i + 1 ? "hl" : ""}`} key={i}>
              {l || " "}
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}
