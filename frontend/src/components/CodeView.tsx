import { useMemo } from "react";

/** Read-only source view with line numbers (M1). Full Monaco integration is M3 scope. */
export default function CodeView({ text, path }: { text: string; path: string }) {
  const lines = useMemo(() => text.split("\n"), [text]);
  const gutterWidth = String(lines.length).length;
  return (
    <div className="codeview" aria-label={`source of ${path}`}>
      <div className="codeview-title">
        <code>{path}</code>
      </div>
      <div className="codeview-body">
        <ol className="gutter" start={1}>
          {lines.map((_, i) => (
            <li key={i}>{i + 1}</li>
          ))}
        </ol>
        <pre className="code">
          {lines.map((l, i) => (
            <div className="codeline" key={i}>
              {l || " "}
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}
