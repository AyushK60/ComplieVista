import { useEffect, useMemo, useRef } from "react";

const KEYWORDS: Record<string, string[]> = {
  python: ["def", "return", "if", "elif", "else", "for", "while", "in", "import",
    "from", "class", "try", "except", "finally", "with", "as", "pass", "yield",
    "raise", "lambda", "not", "and", "or", "is", "None", "True", "False", "async", "await"],
  c: ["int", "char", "void", "return", "if", "else", "for", "while", "do", "switch",
    "case", "default", "break", "continue", "static", "const", "struct", "sizeof",
    "unsigned", "signed", "long", "short", "float", "double", "include", "define"],
};

/**
 * M3-B read-only source view: line numbers, keyword/string/comment coloring,
 * highlight + scroll-to-line for graph→source navigation (M3-C two-way),
 * and browser-native search. Monaco was attempted in M3 and deferred to M8
 * (Vite worker incompatibility documented in docs/TEST_EVIDENCE/M3.md);
 * this is the equivalent read-only mode for immutable analyzed snapshots.
 */
export default function CodeView({ text, path, language, highlightLine }: {
  text: string;
  path: string;
  language?: string;
  highlightLine?: number | null;
}) {
  const lines = useMemo(() => text.split("\n"), [text]);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const kw = KEYWORDS[language ?? ""] ?? [];

  const colorize = (line: string, lang: string | undefined) => {
    const parts: Array<{ t: string; c: string }> = [];
    const re = /(#.*$|\/\/.*$|\/\*.*?\*\/)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|([A-Za-z_][\w]*)|(\d+)/g;
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(line)) !== null) {
      if (m.index > last) parts.push({ t: line.slice(last, m.index), c: "" });
      if (m[1]) parts.push({ t: m[1], c: "tok-comment" });
      else if (m[2]) parts.push({ t: m[2], c: "tok-string" });
      else if (m[3] && lang && kw.includes(m[3])) parts.push({ t: m[3], c: "tok-keyword" });
      else if (m[4]) parts.push({ t: m[4], c: "tok-number" });
      else parts.push({ t: m[0], c: "" });
      last = m.index + m[0].length;
    }
    if (last < line.length) parts.push({ t: line.slice(last), c: "" });
    return parts;
  };

  useEffect(() => {
    if (highlightLine == null || !bodyRef.current) return;
    const el = bodyRef.current.querySelector(`[data-line="${highlightLine}"]`);
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [highlightLine]);

  return (
    <div className="codeview" aria-label={`source of ${path}`}>
      <div className="codeview-title">
        <code>{path}</code>
        <span className="muted" style={{ marginLeft: "auto" }}>
          read-only · immutable analyzed snapshot
        </span>
      </div>
      <div className="codeview-body" ref={bodyRef}>
        <ol className="gutter" start={1}>
          {lines.map((_, i) => (
            <li key={i} className={highlightLine === i + 1 ? "hl" : undefined}
                onClick={() => undefined}>{i + 1}</li>
          ))}
        </ol>
        <pre className="code">
          {lines.map((l, i) => (
            <div className={`codeline ${highlightLine === i + 1 ? "hl" : ""}`}
                 data-line={i + 1} key={i}>
              {colorize(l, language).map((p, j) => (
                p.c ? <span key={j} className={p.c}>{p.t}</span> : <span key={j}>{p.t}</span>
              ))}
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}
