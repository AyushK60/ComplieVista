import { useCallback, useEffect, useRef, useState } from "react";
import sample from "../../data/heroSample.json";

/**
 * The opening title card. One real line of C, as Clang 18 recorded it, is cut into its tokens and
 * the tokens re-form as the syntax tree Clang built for that line.
 *
 *   step 0  source   the line as written; a blade sweeps across it
 *   step 1  tokens   Clang's own token list for the line, each with its recorded kind; the macro
 *                    M0_SCALE is still a name
 *   step 2  tree     the AST subtree: tokens move to the nodes they became; the macro resolves to
 *                    the literal 3; nodes with no token of their own (DeclStmt, ImplicitCastExpr)
 *                    are drawn dashed
 *
 * Data is recorded output (src/data/heroSample.json, with tool, version and SHA-256). It loops on
 * its own (source, tokens, tree, a rest, again) until you press a step; the step buttons then hold
 * that step. Reduced motion rests on the tree.
 */

type Spot = { x: number; y: number };
type Block = {
  id: string;
  tone: "ink" | "cream" | "saffron" | "cobalt";
  token?: { text: string; kind: string; at: Spot; order: number };
  node: { label: string; sub?: string; at: Spot; implied?: boolean; resolves?: string };
  from?: string;
};

const ROW = 46;
const BLOCKS: Block[] = [
  { id: "d", tone: "ink", node: { label: "DeclStmt", at: { x: 50, y: 9 }, implied: true } },
  { id: "v", tone: "cobalt", token: { text: "scaled", kind: "identifier", at: { x: 33, y: ROW }, order: 1 }, node: { label: "VarDecl", sub: "scaled", at: { x: 50, y: 28 } }, from: "d" },
  { id: "b", tone: "saffron", token: { text: "*", kind: "star", at: { x: 69, y: ROW }, order: 4 }, node: { label: "BinaryOperator", sub: "*", at: { x: 50, y: 47 } }, from: "v" },
  { id: "c", tone: "ink", node: { label: "ImplicitCastExpr", sub: "LValueToRValue", at: { x: 27, y: 66 }, implied: true }, from: "b" },
  { id: "l", tone: "cream", token: { text: "M0_SCALE", kind: "macro, line 5", at: { x: 86, y: ROW }, order: 5 }, node: { label: "IntegerLiteral", sub: "3", at: { x: 75, y: 66 }, resolves: "3" }, from: "b" },
  { id: "r", tone: "cream", token: { text: "base", kind: "identifier", at: { x: 55, y: ROW }, order: 3 }, node: { label: "DeclRefExpr", sub: "base", at: { x: 27, y: 85 } }, from: "c" },
];
// tokens that belong to a node's range but have no block of their own: they fold into VarDecl
const FOLD: Array<{ text: string; kind: string; at: Spot; into: string; order: number }> = [
  { text: "int", kind: "int", at: { x: 8, y: ROW }, into: "v", order: 0 },
  { text: "=", kind: "equal", at: { x: 45, y: ROW }, into: "v", order: 2 },
];

const STEPS = [
  { n: "Source", note: "The line, as written in demos/m0/c_fixture.c" },
  { n: "Tokens", note: "Clang’s token list for the line. The macro M0_SCALE is still a name." },
  { n: "Syntax tree", note: "Clang’s AST for the line. The macro is now the literal 3." },
];
// loop timeline in ms: tokens cut, tree forms, tree rests, start over
const AT = [0, 1700, 3900, 9800];

const byId = new Map(BLOCKS.map((b) => [b.id, b]));

export default function TitleSequence() {
  const reduce = typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const [step, setStep] = useState(reduce ? 2 : 0);
  const [loop, setLoop] = useState(!reduce);
  const timers = useRef<number[]>([]);
  const clear = () => { timers.current.forEach((t) => window.clearTimeout(t)); timers.current = []; };

  useEffect(() => {
    if (!loop) return;
    const run = () => {
      setStep(0);
      timers.current = [
        window.setTimeout(() => setStep(1), AT[1]),
        window.setTimeout(() => setStep(2), AT[2]),
        window.setTimeout(run, AT[3]),
      ];
    };
    run();
    return clear;
  }, [loop]);

  const go = useCallback((n: number) => { clear(); setLoop(false); setStep(n); }, []);
  const line = sample.line;

  return (
    <figure className="ts" data-step={step} data-loop={loop ? "" : undefined} aria-label="One line of C, cut into tokens and rebuilt as its syntax tree">
      <div className="ts-stage" role="img" aria-label={`${STEPS[step].n}: ${STEPS[step].note}`}>
        <svg className="ts-wires" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
          {BLOCKS.filter((b) => b.from).map((b, i) => {
            const p = byId.get(b.from!)!;
            return <line key={b.id} pathLength={1} style={{ ["--w" as string]: `${i * 120}ms` }} x1={p.node.at.x} y1={p.node.at.y} x2={b.node.at.x} y2={b.node.at.y} vectorEffect="non-scaling-stroke" />;
          })}
        </svg>

        <p className="ts-line" aria-hidden>
          <span>{line}</span>
          <i className="ts-blade" key={`${step === 0}-${loop}`} />
        </p>

        {FOLD.map((f) => {
          const into = byId.get(f.into)!.node.at;
          const at = step === 2 ? into : f.at;
          return (
            <span key={f.text} className="ts-b ts-fold" data-tone="ink" aria-hidden
                  style={{ left: `${at.x}%`, top: `${at.y}%`, ["--t" as string]: f.order }}>
              <span className="ts-tk">{f.text}</span>
              {step === 1 && <em className="ts-kind">{f.kind}</em>}
            </span>
          );
        })}

        {BLOCKS.map((b, i) => {
          const at = step === 2 || !b.token ? b.node.at : b.token.at;
          return (
            <span key={b.id} className="ts-b" data-tone={b.tone} data-implied={b.node.implied ? "" : undefined}
                  data-has-token={b.token ? "" : undefined} aria-hidden
                  style={{ left: `${at.x}%`, top: `${at.y}%`, ["--t" as string]: b.token?.order ?? 0, ["--n" as string]: i }}>
              {b.token && <span className="ts-tk">{b.token.text}</span>}
              <span className="ts-nd"><b>{b.node.label}</b>{b.node.sub && <i>{b.node.sub}</i>}</span>
              {b.token && step === 1 && <em className="ts-kind">{b.token.kind}</em>}
            </span>
          );
        })}
      </div>

      <figcaption className="ts-cap">
        <div className="ts-steps" role="group" aria-label="Show a step">
          {STEPS.map((s, i) => (
            <button key={s.n} type="button" aria-pressed={step === i} onClick={() => go(i)}>{s.n}</button>
          ))}
        </div>
        {!loop && !reduce && <button type="button" className="ts-replay" onClick={() => setLoop(true)}>Play the loop</button>}
        <p>
          Recorded output · {sample.provenance.tool} · source sha256 <code>{sample.provenance.source_sha256.slice(0, 10)}…</code>
        </p>
      </figcaption>
    </figure>
  );
}
