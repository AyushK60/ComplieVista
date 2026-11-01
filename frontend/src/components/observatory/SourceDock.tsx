import { useEffect, useMemo, useRef } from "react";
import { TokenItem } from "./types";

const KEYWORDS: Record<string, string[]> = {
  python: ["def", "return", "if", "elif", "else", "for", "while", "in", "import",
    "from", "class", "try", "except", "finally", "with", "as", "pass", "yield",
    "raise", "lambda", "not", "and", "or", "is", "None", "True", "False", "async", "await"],
  c: ["int", "char", "void", "return", "if", "else", "for", "while", "do", "switch",
    "case", "default", "break", "continue", "static", "const", "struct", "sizeof",
    "unsigned", "signed", "long", "short", "float", "double", "include", "define"],
};

/**
 * Source Dock — read-only, line-numbered source of the immutable snapshot.
 * `activeLine` is driven by every other dock (tokens, AST, bytecode, trace).
 * Reader colorization is presentational only; the token stage shows the
 * tool-reported tokens.
 */
export default function SourceDock({ text, path, language, activeLine, onSelectLine, linked }: {
  text: string;
  path: string;
  language?: string;
  activeLine?: number | null;
  /** when true, the active line is a real artifact↔source link (mint) vs a manual click (dim) */
  linked?: boolean;
  onSelectLine?: (line: number) => void;
}) {
  const lines = useMemo(() => text.split("\n"), [text]);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const kw = KEYWORDS[language ?? ""] ?? [];

  const colorize = (line: string) => {
    const parts: Array<{ t: string; c: string }> = [];
    const re = /(#.*$|\/\/.*$|\/\*.*?\*\/)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|([A-Za-z_][\w]*)|(\d+)/g;
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(line)) !== null) {
      if (m.index > last) parts.push({ t: line.slice(last, m.index), c: "" });
      if (m[1]) parts.push({ t: m[1], c: "tok-comment" });
      else if (m[2]) parts.push({ t: m[2], c: "tok-str" });
      else if (m[3] && kw.includes(m[3])) parts.push({ t: m[3], c: "tok-kw" });
      else if (m[4]) parts.push({ t: m[4], c: "tok-num" });
      else if (m[3]) parts.push({ t: m[3], c: "tok-name" });
      else parts.push({ t: m[0], c: "" });
      last = m.index + m[0].length;
    }
    if (last < line.length) parts.push({ t: line.slice(last), c: "" });
    return parts;
  };

  useEffect(() => {
    if (activeLine == null || !bodyRef.current) return;
    const el = bodyRef.current.querySelector(`[data-line="${activeLine}"]`);
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [activeLine]);

  return (
    <div className="sourcedock panel" aria-label={`source of ${path}`}>
      <div className="panel-h">
        <span className="sd-path"><code>{path}</code></span>
        <span className="spacer" />
        <span className="muted" style={{ fontSize: 11 }}>{lines.length} lines · read-only snapshot</span>
      </div>
      <div className="sourcedock-body" ref={bodyRef}>
        {lines.map((l, i) => {
          const n = i + 1;
          const isActive = activeLine === n;
          return (
            <div key={n}
                 className={"sourceline" + (isActive ? (linked ? " hl-linked" : " hl") : "")}
                 data-line={n}
                 onClick={() => onSelectLine?.(n)}>
              <span className="sl-no">{n}</span>
              <span className="sl-text">
                {l.length ? colorize(l).map((p, j) =>
                  p.c ? <span key={j} className={p.c}>{p.t}</span> : <span key={j}>{p.t}</span>
                ) : "\u200b"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
