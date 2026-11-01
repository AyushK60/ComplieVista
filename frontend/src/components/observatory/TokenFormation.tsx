import { useEffect, useMemo, useState } from "react";
import { confBadge, Selection, TokenItem } from "./types";

/**
 * Token Formation — the signature lexical canvas. Every chip is a token the
 * real tool reported (clang -dump-tokens / CPython tokenize), laid out on its
 * exact source line with faithful inter-token spacing. `col` is 1-based for C,
 * 0-based for Python — both are converted to a 0-based character offset here
 * and the source text fills the gaps, so whitespace is never invented.
 */
export default function TokenFormation({ tokens, sourceText, language, truncated, onSelect, onSelectLine, activeLine }: {
  tokens: TokenItem[];
  sourceText: string;
  language: string;
  truncated?: boolean;
  onSelect: (sel: Selection) => void;
  onSelectLine: (line: number) => void;
  activeLine?: number | null;
}) {
  const [revealed, setRevealed] = useState(false);
  useEffect(() => {
    setRevealed(false);
    const t = setTimeout(() => setRevealed(true), 60);
    return () => clearTimeout(t);
  }, [tokens]);

  const sourceLines = useMemo(() => sourceText.split("\n"), [sourceText]);

  const rows = useMemo(() => {
    const byLine = new Map<number, TokenItem[]>();
    for (const t of tokens) {
      const ln = Number(t.line);
      if (!byLine.has(ln)) byLine.set(ln, []);
      byLine.get(ln)!.push(t);
    }
    return [...byLine.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([ln, toks]) => {
        // 0-based character offset of each token start
        const offs = toks.map((t) => language === "c" ? Number(t.col) - 1 : Number(t.col));
        const gaps: number[] = [];
        for (let i = 0; i < toks.length; i++) {
          const end = offs[i] + String(toks[i].text ?? "").length;
          const next = i + 1 < toks.length ? offs[i + 1] : null;
          const lineText = sourceLines[ln - 1] ?? "";
          gaps.push(next != null
            ? Math.max(0, next - end)
            : Math.max(0, lineText.length - end));
        }
        const lead = Math.max(0, offs[0] ?? 0);
        return { ln, toks, gaps, lead };
      });
  }, [tokens, sourceLines, language]);

  const kindCounts = useMemo(() => {
    const m = new Map<string, number>();
    for (const t of tokens) m.set(t.kind, (m.get(t.kind) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [tokens]);

  if (!tokens.length) {
    return <div className="unavailable"><span className="glyph">◍</span>
      This stage reported no tokens (see the stage limitations below the canvas).</div>;
  }

  return (
    <div className="tokenformation">
      <div className="tf-toolbar">
        <span className="muted">{tokens.length} tokens{truncated ? " (truncated)" : ""} ·
          positions {language === "c" ? "clang 1-based columns" : "CPython 0-based columns"}</span>
        <span className="spacer" />
        <button className="btn ghost" onClick={() => setRevealed((r) => !r)}>
          {revealed ? "Merge back to text" : "Dissolve into tokens"}
        </button>
      </div>

      <div className={"tf-code" + (revealed ? " revealed" : "")} role="list"
           aria-label="token stream laid out on source lines">
        {rows.map(({ ln, toks, gaps, lead }) => (
          <div key={ln}
               className={"tf-row" + (activeLine === ln ? " active" : "")}
               role="listitem">
            <span className="tf-lineno">{ln}</span>
            <span className="tf-chips">
              {lead > 0 && <span className="tf-gap" style={{ width: `${lead}ch` }} />}
              {toks.map((t, i) => (
                <span key={i} style={{ display: "inline-flex", alignItems: "baseline" }}>
                  {i > 0 && gaps[i - 1] > 0 &&
                    <span className="tf-gap" style={{ width: `${gaps[i - 1]}ch` }} />}
                  <button
                    className={`tf-token k-${tokClass(t.kind, t.text)}`}
                    style={{ transitionDelay: revealed ? `${Math.min((ln * 8 + i) * 14, 1400)}ms` : "0ms" }}
                    title={`${t.kind} · line ${t.line} col ${t.col} · ${t.mapping_confidence ?? ""}`}
                    onClick={() => {
                      onSelect({
                        id: `tok:${ln}:${i}`,
                        title: `${t.kind} “${t.text}”`,
                        subtitle: `token · ${t.mapping_confidence ?? ""}`,
                        stage: "tokens",
                        language,
                        what: TOKEN_WHAT(t.kind, t.text),
                        fields: [
                          ["kind", String(t.kind)],
                          ["text", String(t.text)],
                          ["line", String(t.line)],
                          ["col (tool-reported)", String(t.col)],
                          ["mapping", String(t.mapping_confidence ?? "—")],
                        ],
                        sourceLine: ln,
                        confidence: t.mapping_confidence,
                      });
                      onSelectLine(ln);
                    }}>
                    {String(t.text ?? "")}
                  </button>
                </span>
              ))}
            </span>
          </div>
        ))}
      </div>

      <div className="tf-legend">
        {kindCounts.slice(0, 8).map(([k, n]) => (
          <span key={k} className="chip"><i className={`tf-dot k-${tokClass(k, "")}`} />{k} ×{n}</span>
        ))}
        {truncated && <span className="chip blocked">truncated</span>}
      </div>
      <p className="muted tf-note">
        The lexer never sees whitespace — the grey gaps show where it was, and why it
        exists only for humans. Hover a token to locate it; click to inspect.
      </p>
      {confBadge("EXACT") && <span className="tech-only prov">mapping_confidence: EXACT (tool-reported positions)</span>}
    </div>
  );
}

function tokClass(kind: string, text: string): string {
  const k = kind.toLowerCase();
  if (k.includes("comment")) return "comment";
  if (k.includes("string") || k.includes("fstring") || k === "string") return "str";
  if (k.includes("number") || k.includes("int") || k.includes("float") || k.includes("literal")) return "num";
  if (k.includes("keyword") || k === "name" && ["if", "else", "for", "while", "def", "return", "import", "from", "in", "not", "and", "or", "is", "None", "True", "False", "int", "char", "void", "include", "struct", "const"].includes(text))
    return k.includes("keyword") ? "kw" : "name";
  if (k.includes("keyword")) return "kw";
  if (k.includes("op") || k.includes("punct") || k.includes("delimiter") || k === "dellipsis") return "op";
  if (k === "name" || k.includes("identifier")) return "name";
  if (k === "newline" || k === "indent" || k === "dedent" || k === "endmarker") return "invis";
  return "other";
}

function TOKEN_WHAT(kind: string, text: string): string {
  const k = kind.toLowerCase();
  if (k.includes("keyword")) return `A reserved word of the language. The lexer recognizes it before any parsing happens — “${text}” can never be used as a name.`;
  if (k.includes("string")) return "A string literal: the exact bytes your program will see at runtime, captured verbatim by the lexer.";
  if (k.includes("number") || k.includes("int") || k.includes("float")) return "A numeric literal. The lexer records its text; the parser later decides its type and value.";
  if (k.includes("op") || k.includes("punct") || k.includes("delimiter")) return "A punctuation or operator token — the glue of the grammar. Brackets delimit scope, operators describe computation.";
  if (k === "newline" || k === "indent" || k === "dedent") return "A layout token: for Python, indentation IS syntax, so the tokenizer emits INDENT/DEDENT/NEWLINE tokens that the parser consumes.";
  if (k.includes("identifier") || k === "name") return `An identifier — a name your program uses. After lexing it is just text (“${text}”); the parser and semantic phases decide what it refers to.`;
  return "A token reported by the toolchain's lexer, with its exact source position.";
}
