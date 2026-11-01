import { useEffect, useMemo, useState } from "react";
import { confBadge, Selection, TokenItem } from "./types";

/**
 * Token Formation — the signature lexical canvas (porcelain revision).
 * Every chip is a token the real tool reported (clang -dump-tokens /
 * CPython tokenize), laid out on its exact source line with faithful
 * inter-token spacing. `col` is 1-based for C, 0-based for Python — both are
 * converted to a 0-based character offset here and the source text fills the
 * gaps, so whitespace is never invented.
 *
 * Educational behavior:
 * - a meaningful short statement is auto-selected on load; the default view
 *   focuses its tokens (a 40-line docstring can never monopolize the screen);
 * - clicking/hovering a token highlights its exact source span in the dock;
 *   selecting source in the dock focuses this canvas on that line;
 * - categories are filterable, tokens searchable, and the full stream is one
 *   click away;
 * - tokens that do not correspond to visible source text (e.g. CPython's
 *   ENCODING token) render as virtual metadata chips, never as fake source;
 * - guided mode walks concept → expression → segmentation → categories →
 *   parsing, with each step driving the canvas itself.
 */

export interface SourceSpan { line: number; col0: number; col1: number }

const FOCUS_OPS = new Set(["=", "+", "-", "*", "/", "==", "+=", "-=", "*=", "(", ")", "->", "%"]);

/** Pick an educationally meaningful default line: a short assignment or call,
 * never a bare docstring, comment or import banner. */
function pickFocusLine(rows: Array<{ ln: number; toks: TokenItem[] }>, sourceLines: string[]): number | null {
  let fallback: number | null = null;
  for (const { ln, toks } of rows) {
    const real = toks.filter((t) => !isInvis(t.kind));
    if (real.length < 3 || real.length > 10) continue;
    if (real.some((t) => t.kind.toLowerCase().includes("comment"))) continue;
    const text = sourceLines[ln - 1] ?? "";
    if (text.trim().length < 4) continue;
    if (fallback === null) fallback = ln;
    const hasOp = real.some((t) => FOCUS_OPS.has(String(t.text)));
    const hasCall = real.some((t, i) => String(t.text) === "(" && i > 0 && real[i - 1].kind.toLowerCase().includes("name"));
    const multilineOnly = real.every((t) => isStr(t.kind) && String(t.text).includes("\n"));
    if ((hasOp || hasCall) && !multilineOnly) return ln;
  }
  return fallback;
}

function isInvis(kind: string): boolean {
  const k = kind.toLowerCase();
  return k === "newline" || k === "indent" || k === "dedent" || k === "endmarker";
}
function isStr(kind: string): boolean {
  const k = kind.toLowerCase();
  return k.includes("string") || k.includes("fstring");
}

export default function TokenFormation({ tokens, sourceText, language, truncated, onSelect, onSelectLine, activeLine, onHoverSpan, guided, onNavigateStage }: {
  tokens: TokenItem[];
  sourceText: string;
  language: string;
  truncated?: boolean;
  onSelect: (sel: Selection) => void;
  onSelectLine: (line: number) => void;
  activeLine?: number | null;
  onHoverSpan?: (span: SourceSpan | null) => void;
  guided?: boolean;
  onNavigateStage?: (stage: string) => void;
}) {
  const [revealed, setRevealed] = useState(false);
  const [scope, setScope] = useState<"expression" | "full">("expression");
  const [focusLine, setFocusLine] = useState<number | null>(null);
  const [hiddenKinds, setHiddenKinds] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [step, setStep] = useState(0);

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
        // a token is "virtual" when the source at its reported offset does not
        // actually contain its text (CPython ENCODING et al.) — never fake it
        const virtual = toks.map((t, i) => {
          if (isInvis(t.kind)) return false;
          const lineText = sourceLines[ln - 1] ?? "";
          return lineText.slice(offs[i], offs[i] + String(t.text ?? "").length) !== String(t.text ?? "");
        });
        return { ln, toks, gaps, lead, offs, virtual };
      });
  }, [tokens, sourceLines, language]);

  // default focus: pick once per token set (re-picks when the source text
  // arrives — deep-linked snapshots load the file asynchronously)
  useEffect(() => {
    const ln = pickFocusLine(rows, sourceLines);
    setFocusLine(ln);
    setScope("expression");
    setStep(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tokens, sourceText]);

  // external source-line selection focuses this canvas
  useEffect(() => {
    if (activeLine != null) { setFocusLine(activeLine); setScope("expression"); }
  }, [activeLine]);

  const kindCounts = useMemo(() => {
    const m = new Map<string, number>();
    for (const t of tokens) m.set(t.kind, (m.get(t.kind) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [tokens]);

  const q = query.trim().toLowerCase();
  const kindHidden = (t: TokenItem) => hiddenKinds.has(tokClass(t.kind, String(t.text)));
  const matches = (t: TokenItem) => !q || String(t.text ?? "").toLowerCase().includes(q);

  // which rows to draw in expression scope: the focus line with one line of
  // context on each side (skipping invisible-only rows)
  const visibleRows = useMemo(() => {
    if (scope === "full" || focusLine == null) return rows;
    const idx = rows.findIndex((r) => r.ln === focusLine);
    if (idx < 0) return rows;
    const lo = Math.max(0, idx - 1), hi = Math.min(rows.length - 1, idx + 1);
    return rows.slice(lo, hi + 1);
  }, [rows, scope, focusLine]);

  const hiddenRowCount = rows.length - visibleRows.length;

  // ——— guided script: each step drives the canvas itself ———
  useEffect(() => {
    if (!guided) return;
    if (step === 0) { setRevealed(false); setScope("full"); }
    if (step === 1) { setRevealed(false); if (focusLine == null) setScope("full"); else setScope("expression"); }
    if (step === 2) { setRevealed(true); setScope("expression"); setHiddenKinds(new Set()); setQuery(""); }
    if (step === 3) { setRevealed(true); setScope("full"); }
    if (step === 4) { setRevealed(true); setScope("full"); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, guided]);

  if (!tokens.length) {
    return <div className="unavailable"><span className="glyph">◍</span>
      This stage reported no tokens (see the stage limitations below the canvas).</div>;
  }

  const focusText = focusLine != null ? (sourceLines[focusLine - 1] ?? "").trim() : null;

  const GUIDED_STEPS: Array<{ cap: string; body: React.ReactNode }> = [
    { cap: "step 1 · the concept", body: <>This is your program exactly as the toolchain received it. To a compiler, it is not code yet — just characters. The <b>lexer</b> is about to read every one of them.</> },
    { cap: "step 2 · one expression", body: focusText
      ? <>Let’s start small. This statement — <code>{focusText.slice(0, 60)}</code> — is one complete thought. Keep it in mind; we’ll watch what the lexer does to it.</>
      : <>Let’s start with one short statement and watch what the lexer does to it.</> },
    { cap: "step 3 · segmentation", body: <>The lexer split it into <b>tokens</b>: the smallest units that still mean something. Whitespace is gone — it only separated tokens; the grey gaps mark where it was. Click any token to see its exact source position.</> },
    { cap: "step 4 · categories", body: <>Every token belongs to a category — <b>keywords</b>, <b>names</b>, <b>literals</b>, <b>operators</b> — shown in the legend. Click a legend chip to filter; this is the vocabulary the parser is about to consume.</> },
    { cap: "step 5 · into the parser", body: <>The lexer emits this flat stream — nothing nested yet. The <b>parser</b> turns it into a tree. Continue to the Syntax Tree stage to watch it happen.</> },
  ];

  return (
    <div className="tokenformation">
      <div className="tf-toolbar">
        <span className="muted">{tokens.length} tokens{truncated ? " (truncated)" : ""} ·
          positions {language === "c" ? "clang 1-based columns" : "CPython 0-based columns"}</span>
        <span className="spacer" />
        <input className="input" placeholder="find a token…" aria-label="search tokens"
               value={query} onChange={(e) => setQuery(e.target.value)} />
        <button className="btn ghost" onClick={() => setRevealed((r) => !r)}>
          {revealed ? "Merge back to text" : "Dissolve into tokens"}
        </button>
        <button className="btn ghost" aria-pressed={scope === "full"}
                onClick={() => setScope((s) => s === "full" ? "expression" : "full")}>
          {scope === "full" ? "Focus expression" : "Show full file"}
        </button>
      </div>

      {guided && (
        <div className="tf-guided" role="note" aria-live="polite">
          <div className="tf-guided-h">
            <span>{GUIDED_STEPS[step].cap}</span>
          </div>
          <p className="tf-guided-step">{GUIDED_STEPS[step].body}</p>
          <div className="tf-guided-actions">
            <button className="btn ghost" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0}>← back</button>
            {step < GUIDED_STEPS.length - 1
              ? <button className="btn primary" onClick={() => setStep((s) => s + 1)}>continue →</button>
              : <button className="btn primary" onClick={() => onNavigateStage?.(language === "c" ? "ast" : "ast")}>
                  continue to the Syntax Tree →</button>}
            <div className="tf-guided-dots" aria-hidden>
              {GUIDED_STEPS.map((_, i) => <span key={i} className={i === step ? "on" : ""} />)}
            </div>
          </div>
        </div>
      )}

      {focusLine != null && scope === "expression" && !guided && (
        <div className="tf-focusnote">
          <span className="muted">focused</span>
          <code>{focusText?.slice(0, 70) || `line ${focusLine}`}</code>
          <span className="spacer" style={{ flex: 1 }} />
          <span className="muted">select any line in the source dock to refocus</span>
        </div>
      )}

      <div className={"tf-code on-ink" + (revealed ? " revealed" : "")} role="list"
           aria-label="token stream laid out on source lines">
        {visibleRows.map(({ ln, toks, gaps, lead, virtual }) => {
          const rowMatch = toks.some((t) => matches(t) && !kindHidden(t));
          return (
            <div key={ln}
                 className={"tf-row" + (activeLine === ln ? " active" : "") + (rowMatch ? "" : " dimmed")}
                 role="listitem">
              <span className="tf-lineno">{ln}</span>
              <span className="tf-chips">
                {lead > 0 && <span className="tf-gap" style={{ width: `${lead}ch` }} />}
                {toks.map((t, i) => {
                  const cls = tokClass(t.kind, String(t.text));
                  const isVirtual = virtual[i];
                  const multiline = isStr(t.kind) && String(t.text ?? "").includes("\n");
                  const compact = multiline ? `${String(t.text).split("\n")[0].slice(0, 24)}… ⌄${String(t.text).split("\n").length} lines` : String(t.text ?? "");
                  return (
                    <span key={i} style={{ display: "inline-flex", alignItems: "baseline" }}>
                      {i > 0 && gaps[i - 1] > 0 &&
                        <span className="tf-gap" style={{ width: `${gaps[i - 1]}ch` }} />}
                      {isVirtual ? (
                        <span className="tf-virtual" title={`${t.kind} · reported at line ${t.line} col ${t.col} but not present in the visible source text`}>
                          {t.kind.toLowerCase()} <b>{String(t.text)}</b>
                        </span>
                      ) : (
                        <button
                          className={`tf-token k-${cls}` + (kindHidden(t) ? " filtered" : "") + (matches(t) && q ? " focused" : "")}
                          style={{ transitionDelay: revealed ? `${Math.min((ln * 8 + i) * 14, 1400)}ms` : "0ms" }}
                          title={`${t.kind} · line ${t.line} col ${t.col} · ${t.mapping_confidence ?? ""}`}
                          onMouseEnter={() => onHoverSpan?.({
                            line: ln,
                            col0: language === "c" ? Number(t.col) - 1 : Number(t.col),
                            col1: (language === "c" ? Number(t.col) - 1 : Number(t.col)) + String(t.text ?? "").length,
                          })}
                          onMouseLeave={() => onHoverSpan?.(null)}
                          onFocus={() => onHoverSpan?.({
                            line: ln,
                            col0: language === "c" ? Number(t.col) - 1 : Number(t.col),
                            col1: (language === "c" ? Number(t.col) - 1 : Number(t.col)) + String(t.text ?? "").length,
                          })}
                          onBlur={() => onHoverSpan?.(null)}
                          onClick={() => {
                            onSelectLine(ln);
                            onSelect({
                              id: `tok:${ln}:${i}`,
                              title: `${t.kind} “${compact}”`,
                              subtitle: `token · ${t.mapping_confidence ?? ""}`,
                              stage: "tokens",
                              language,
                              what: TOKEN_WHAT(t.kind, String(t.text)),
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
                          }}>
                          {compact}
                        </button>
                      )}
                    </span>
                  );
                })}
              </span>
            </div>
          );
        })}
        {hiddenRowCount > 0 && (
          <button className="btn ghost" style={{ margin: "8px 0 0 36px" }}
                  onClick={() => setScope("full")}>
            … {hiddenRowCount} more source line{hiddenRowCount === 1 ? "" : "s"} in this file — show the full token stream
          </button>
        )}
      </div>

      <div className="tf-legend">
        <span className="lab muted" style={{ fontSize: 11, fontFamily: "var(--font-mono)" }}>categories:</span>
        {kindCounts.slice(0, 9).map(([k, n]) => {
          const cls = tokClass(k, "");
          const off = hiddenKinds.has(cls);
          return (
            <button key={k} className={"chip" + (off ? " off" : "")}
                    aria-pressed={!off}
                    title={off ? `show ${k}` : `hide ${k}`}
                    onClick={() => setHiddenKinds((prev) => {
                      const next = new Set(prev);
                      if (next.has(cls)) next.delete(cls); else next.add(cls);
                      return next;
                    })}>
              <i className={`tf-dot k-${cls}`} />{k} ×{n}
            </button>
          );
        })}
        {truncated && <span className="chip blocked">truncated</span>}
      </div>
      <p className="muted tf-note">
        The lexer never sees whitespace — the grey gaps show where it was, and why it
        exists only for humans. Hover a token to locate it in the source; click to inspect.
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
