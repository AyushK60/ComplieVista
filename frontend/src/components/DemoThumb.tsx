import thumbs from "../data/demoThumbs.json";

/**
 * One film frame per demo, drawn from that program's REAL analysis (src/data/demoThumbs.json, built
 * by scripts/media/build_demo_thumbs.py from the live tokens and AST stages): the first function's
 * source, the real tokens of its signature line, and the real top of its syntax tree.
 */
type Thumb = {
  lang: string;
  excerpt: string[];
  excerpt_from: number;
  tokens: Array<{ kind: string; text: string }>;
  tree: Array<{ kind: string; name: string | null; depth: number }>;
  counts: { tokens: number | null; ast_nodes: number | null };
};
const data = (thumbs as unknown as { demos: Record<string, Thumb> }).demos;

const PY_KW = new Set(["def", "return", "if", "else", "elif", "for", "while", "in", "import", "from", "class", "and", "or", "not", "True", "False", "None", "lambda", "yield", "with", "as", "try", "except", "raise", "pass", "break", "continue", "global", "nonlocal", "async", "await"]);
function tone(kind: string, text: string): string {
  const k = kind.toLowerCase();
  if (k === "name") return PY_KW.has(text) ? "kw" : "id";
  if (k === "identifier") return "id";
  if (k === "number" || k.includes("numeric")) return "num";
  if (k.includes("string")) return "str";
  if (k === "op" || /paren|brace|square|comma|semi|colon|equal|star|plus|minus|slash|less|greater|amp|pipe|arrow|period|percent|exclaim/.test(k)) return "op";
  return "kw";
}

export function hasThumb(id: string) { return !!data[id]; }

export default function DemoThumb({ id }: { id: string }) {
  const t = data[id];
  if (!t) return null;
  const root = t.tree[0];
  const kids = t.tree.slice(1);
  return (
    <div className="dth" aria-hidden>
      <ol className="dth-code">
        {t.excerpt.map((l, i) => (
          <li key={i}><span className="n">{t.excerpt_from + i}</span><code>{l || " "}</code></li>
        ))}
      </ol>
      {t.tokens.length > 0 && (
        <div className="dth-tok">
          {t.tokens.map((k, i) => <span key={i} data-t={tone(k.kind, k.text)} title={k.kind}>{k.text}</span>)}
        </div>
      )}
      {root && (
        <div className="dth-tree">
          <span className="dth-root">{root.kind}{root.name ? <i>{root.name}</i> : null}</span>
          {kids.length > 0 && (
            <div className="dth-kids">
              {kids.map((c, i) => <span key={i}>{c.kind}{c.name ? <i>{c.name}</i> : null}</span>)}
            </div>
          )}
        </div>
      )}
      <p className="dth-n">{[t.counts.tokens != null && `${t.counts.tokens} tokens`, t.counts.ast_nodes != null && `${t.counts.ast_nodes} syntax nodes`].filter(Boolean).join(" · ")}</p>
    </div>
  );
}
