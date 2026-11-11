import type { ReactNode } from "react";
import type { DemoEntry } from "../api";

/**
 * Demo specimen: a small, honest diagram of what a program is about (control flow, a call tree,
 * memory, loops, scopes, threads, instructions, optimisation levels). It is an illustration keyed
 * by the demo's concepts, not data from the run, and it is labelled "specimen" on the card.
 * Colours come from CSS classes (see redesign.css) so both themes use the same tokens.
 */
type Kind = "branch" | "loop" | "recursion" | "memory" | "opt" | "scope" | "threads" | "bytecode";

const LABEL: Record<Kind, string> = {
  branch: "control flow", loop: "loops and data", recursion: "call tree", memory: "memory",
  opt: "optimization levels", scope: "scopes", threads: "threads", bytecode: "instructions",
};

/** Anything with an id and concept words can have a specimen (a demo, or a C/Python pair). */
export type SpecimenSource = Pick<DemoEntry, "id" | "concepts">;

function kindOf(d: SpecimenSource): Kind {
  const c = d.concepts.join(" ").toLowerCase();
  if (/recursion|call stack/.test(c)) return "recursion";
  if (/pointer|memory|heap/.test(c)) return "memory";
  if (/optimi|benchmark/.test(c)) return "opt";
  if (/sort|loop|array|collection|accumulator|list/.test(c)) return "loop";
  if (/closure|generator|suspension|scope|exception/.test(c)) return "scope";
  if (/thread|concurren|class|import/.test(c)) return "threads";
  if (/bytecode|token/.test(c)) return "bytecode";
  return "branch";
}

const Node = ({ x, y, w, h, label, tone = "", dashed }: { x: number; y: number; w: number; h: number; label: ReactNode; tone?: string; dashed?: boolean }) => (
  <g>
    <rect x={x} y={y} width={w} height={h} rx={2} className={`sp-node ${tone}`} strokeDasharray={dashed ? "4 3" : undefined} />
    <text x={x + w / 2} y={y + h / 2 + 4} textAnchor="middle" className="sp-t">{label}</text>
  </g>
);
const Edge = ({ d, hot, arrow }: { d: string; hot?: boolean; arrow?: boolean }) => (
  <path d={d} className={"sp-edge" + (hot ? " hot" : "")} markerEnd={arrow ? "url(#sp-arrow)" : undefined} />
);
const T = ({ x, y, children, anchor = "start", dim }: { x: number; y: number; children: ReactNode; anchor?: "start" | "middle" | "end"; dim?: boolean }) => (
  <text x={x} y={y} textAnchor={anchor} className={dim ? "sp-t sp-d" : "sp-t"}>{children}</text>
);

function art(kind: Kind, seed: number): ReactNode {
  switch (kind) {
    case "branch": {
      const i = seed % 5;
      const cond = ["x <= 0", "n % 2 == 0", "ptr == NULL", "i < len", "err != 0"][i];
      const left = ["return 0", "skip", "free(p)", "break", "return -1"][i];
      const right = ["b * h // 2", "count += 1", "use(p)", "sum += a[i]", "retry()"][i];
      const after = ["print(area)", "next item", "return", "emit(sum)", "log(err)"][i];
      const leftHot = seed % 2 === 1;
      return (<>
        <Node x={110} y={22} w={100} h={26} label={cond} tone="sky" />
        <Edge d="M160 48 V62 H76 V86" hot={leftHot} arrow /><Edge d="M160 48 V62 H244 V86" hot={!leftHot} arrow />
        <T x={112} y={58} anchor="end" dim>true</T><T x={208} y={58} dim>else</T>
        <Node x={26} y={86} w={100} h={26} label={left} tone={leftHot ? "mint hot" : "mint"} />
        <Node x={194} y={86} w={100} h={26} label={right} tone={leftHot ? "apricot" : "apricot hot"} />
        <Edge d="M76 112 V132 H160 V148" hot={leftHot} arrow /><Edge d="M244 112 V132 H160" hot={!leftHot} />
        <Node x={110} y={148} w={100} h={26} label={after} tone="violet" />
      </>);
    }
    case "loop": {
      const v = (i: number) => ((seed * (i + 3)) % 38) + 2;
      const hot = 3 + (seed % 3);
      return (<>
        {Array.from({ length: 8 }, (_, i) => (
          <g key={i}>
            <rect x={24 + i * 34} y={66} width={30} height={32} rx={2} className={"sp-node " + (i === hot ? "hot" : i < hot ? "sky" : "")} />
            <T x={39 + i * 34} y={87} anchor="middle">{v(i)}</T>
            <T x={39 + i * 34} y={114} anchor="middle" dim>{i}</T>
          </g>
        ))}
        <path d={`M${39 + hot * 34} 52 l-6 -10 h12 z`} className="sp-fill hot" />
        <T x={39 + hot * 34} y={34} anchor="middle">i</T>
        <rect x={24} y={138} width={272} height={28} rx={2} className="sp-node" />
        <rect x={24} y={138} width={Math.round(272 * (hot + 1) / 8)} height={28} rx={2} className="sp-bar mint" />
        <T x={34} y={157}>total += x</T><T x={286} y={157} anchor="end" dim>{Array.from({ length: hot + 1 }, (_, i) => v(i)).reduce((a, b) => a + b, 0)}</T>
      </>);
    }
    case "recursion": {
      const n = 4 + (seed % 2);
      const nodes: Array<[number, number, string, boolean?]> = [
        [160, 24, `f(${n})`, true], [96, 76, `f(${n - 1})`], [224, 76, `f(${n - 2})`],
        [64, 128, `f(${n - 2})`], [128, 128, `f(${n - 3})`], [192, 128, `f(${n - 3})`], [256, 128, `f(${n - 4})`],
      ];
      const links: Array<[number, number]> = [[0, 1], [0, 2], [1, 3], [1, 4], [2, 5], [2, 6]];
      return (<>
        {links.map(([a, b], i) => (
          <Edge key={i} d={`M${nodes[a][0]} ${nodes[a][1] + 11} C ${nodes[a][0]} ${nodes[a][1] + 34}, ${nodes[b][0]} ${nodes[b][1] - 24}, ${nodes[b][0]} ${nodes[b][1] - 11}`} hot={b === 1 || b === 3} />
        ))}
        {nodes.map(([x, y, l, hot], i) => <Node key={i} x={x - 24} y={y - 11} w={48} h={22} label={l} tone={hot ? "hot" : i < 3 ? "apricot" : ""} />)}
        <T x={24} y={178} dim>depth {n}</T><T x={296} y={178} anchor="end" dim>{nodes.length} calls shown</T>
      </>);
    }
    case "memory":
      return (<>
        <T x={20} y={30} dim>stack</T><T x={196} y={30} dim>heap</T>
        <rect x={20} y={40} width={112} height={112} rx={2} className="sp-node" />
        <T x={30} y={58}>main()</T>
        <Node x={30} y={68} w={92} h={24} label="p = 0x7f3a" tone="violet" />
        <Node x={30} y={100} w={92} h={24} label="n = 4" tone="sky" />
        <Edge d="M122 80 H190" hot arrow />
        <Node x={192} y={40} w={108} h={46} label="malloc(16)" tone="mint hot" />
        <Node x={192} y={104} w={108} h={46} label="freed" dashed />
        <T x={20} y={178} dim>pointer to a live block</T>
      </>);
    case "opt": {
      const rows: Array<[string, number, string, number]> = [["-O0", 236, "apricot", 42], ["-O1", 170, "sky", 31], ["-O2", 100, "mint", 18]];
      return (<>
        {rows.map(([l, w, tone, c], i) => (
          <g key={l}>
            <T x={20} y={64 + i * 44} dim>{l}</T>
            <rect x={60} y={46 + i * 44} width={w} height={26} rx={2} className={`sp-bar ${tone}`} />
            <T x={60 + w - 8} y={64 + i * 44} anchor="end">{c}</T>
          </g>
        ))}
        <T x={60} y={178} dim>instructions per level</T>
      </>);
    }
    case "scope":
      return (<>
        <rect x={24} y={24} width={272} height={152} rx={2} className="sp-node" />
        <T x={34} y={42}>outer()</T><T x={286} y={42} anchor="end" dim>count = 0</T>
        <rect x={52} y={56} width={216} height={102} rx={2} className="sp-node sky" />
        <T x={62} y={74}>inner()</T>
        <rect x={80} y={88} width={160} height={52} rx={2} className="sp-node apricot hot" />
        <T x={90} y={108}>count += 1</T><T x={90} y={126} dim>reads the cell above</T>
        <Edge d="M240 100 H262 V52" arrow />
      </>);
    case "threads":
      return (<>
        <T x={20} y={64} dim>T1</T><T x={20} y={110} dim>T2</T>
        <Node x={50} y={48} w={70} h={24} label="work" tone="sky" />
        <Node x={168} y={48} w={80} h={24} label="work" tone="sky" />
        <Node x={90} y={94} w={70} h={24} label="wait" dashed />
        <Node x={200} y={94} w={80} h={24} label="work" tone="violet" />
        <Edge d="M120 60 H168" /><Edge d="M160 106 H200" />
        {[0, 1, 2, 3].map((i) => <Node key={i} x={50 + i * 62} y={142} w={54} h={26} label={i < 2 ? `r${i}` : "-"} tone={i < 2 ? "mint" : ""} dashed={i >= 2} />)}
        <T x={20} y={158} dim>slots</T>
      </>);
    case "bytecode": {
      const rows: Array<[string, string, string, string, boolean?]> = [
        ["0", "RESUME", "", "violet"], ["2", "LOAD_FAST", "base", "sky"], ["4", "LOAD_CONST", "0", "apricot"],
        ["6", "COMPARE_OP", "<=", "violet", true], ["10", "POP_JUMP_IF_FALSE", "→ 18", "violet"], ["12", "RETURN_CONST", "0", "mint"],
      ];
      return (<>
        {rows.map(([o, op, arg, tone, hot], i) => (
          <g key={o}>
            {hot && <rect x={16} y={26 + i * 24} width={288} height={22} className="sp-row hot" />}
            <T x={30} y={41 + i * 24} dim>{o.padStart(3, "0")}</T>
            <text x={70} y={41 + i * 24} className={`sp-t sp-op ${tone}`}>{op}</text>
            <T x={206} y={41 + i * 24} dim>{arg}</T>
          </g>
        ))}
      </>);
    }
  }
}

export default function Specimen({ d }: { d: SpecimenSource }) {
  const kind = kindOf(d);
  const seed = [...d.id].reduce((a, c) => a + c.charCodeAt(0), 0);
  const id = d.id.replace(/[^A-Z0-9-]/gi, "");
  return (
    <div className="dc-screen screen on-ink" aria-hidden>
      <svg viewBox="0 -10 320 224" className="dcs-svg" preserveAspectRatio="xMidYMid meet">
        <defs>
          <marker id="sp-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M0 0 L10 5 L0 10 z" className="sp-fill" />
          </marker>
        </defs>
        {art(kind, seed)}
      </svg>
      <span className="dcs-caption">{id} · {LABEL[kind]} · specimen</span>
    </div>
  );
}
