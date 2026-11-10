import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { demos, DemoEntry } from "../api";
import { Command, score, useRegisteredCommands } from "../state/commands";
import { Icon } from "../ui";

export const SHORTCUTS: Array<[string, string]> = [
  ["Ctrl/⌘ + K", "Open the command palette"],
  ["?", "Show this list"],
  ["[  and  ]", "Previous / next stage in the compilation journey"],
  ["1 – 4", "Switch between the workspace views"],
  ["I", "Show or hide the inspector"],
  ["F", "Focus the canvas (full screen); Esc leaves it"],
  ["Space", "Play or pause the replay (Execution observatory)"],
  ["← →", "Step the replay one event back or forward"],
];

/** Ctrl/⌘+K palette: jump anywhere, load a demo, switch a stage, toggle mode or theme. */
export default function CommandPalette({ open, onClose, base }: {
  open: boolean; onClose: () => void; base: Command[];
}) {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const [catalog, setCatalog] = useState<DemoEntry[] | null>(null);
  const navigate = useNavigate();
  const dynamic = useRegisteredCommands();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLUListElement | null>(null);

  useEffect(() => {
    if (!open) { setQ(""); setSel(0); return; }
    setQ(""); setSel(0);
    setTimeout(() => inputRef.current?.focus(), 0);
    if (!catalog) demos.list().then((r) => setCatalog(r.demos)).catch(() => setCatalog([]));
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const all = useMemo<Command[]>(() => {
    const demoCmds: Command[] = (catalog ?? []).map((d) => ({
      id: "demo:" + d.id, group: "Open a demo", title: `${d.id} — ${d.title}`,
      keywords: d.concepts.join(" "), run: () => navigate(`/demos/${encodeURIComponent(d.id)}`),
    }));
    return [...dynamic, ...base, ...demoCmds];
  }, [dynamic, base, catalog, navigate]);

  const results = useMemo(() => {
    const scored = all
      .map((c) => ({ c, s: Math.max(score(q, c.title), score(q, `${c.group} ${c.keywords ?? ""}`) * 0.5) }))
      .filter((x) => x.s > 0);
    if (q) scored.sort((a, b) => b.s - a.s);
    return scored.map((x) => x.c).slice(0, 40);
  }, [all, q]);

  useEffect(() => { setSel(0); }, [q]);
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
  }, [sel]);

  if (!open) return null;
  const run = (c: Command | undefined) => { if (!c) return; onClose(); setTimeout(c.run, 0); };

  let lastGroup = "";
  return (
    <div className="cmdk-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="cmdk" role="dialog" aria-modal="true" aria-label="Command palette"
           onKeyDown={(e) => {
             if (e.key === "Escape") { e.preventDefault(); onClose(); }
             else if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(results.length - 1, s + 1)); }
             else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
             else if (e.key === "Enter") { e.preventDefault(); run(results[sel]); }
           }}>
        <div className="cmdk-input">
          <Icon name="search" size={16} />
          <input ref={inputRef} autoFocus value={q} onChange={(e) => setQ(e.target.value)}
                 placeholder="Type a command, stage or demo…" aria-label="Search commands"
                 role="combobox" aria-expanded="true" aria-controls="cmdk-list"
                 aria-activedescendant={results[sel] ? `cmdk-${results[sel].id}` : undefined} />
          <kbd>Esc</kbd>
        </div>
        <ul id="cmdk-list" className="cmdk-list" role="listbox" aria-label="Commands" ref={listRef}>
          {results.length === 0 && <li className="cmdk-empty" role="presentation">No matching command.</li>}
          {results.map((c, i) => {
            const head = c.group !== lastGroup ? c.group : null;
            lastGroup = c.group;
            return (
              <li key={c.id} role="presentation">
                {head && <div className="cmdk-group" role="presentation">{head}</div>}
                <div id={`cmdk-${c.id}`} role="option" aria-selected={i === sel}
                     className={"cmdk-item" + (i === sel ? " on" : "")}
                     onMouseMove={() => setSel(i)} onClick={() => run(c)}>
                  <span>{c.title}</span>
                  {c.hint && <kbd>{c.hint}</kbd>}
                </div>
              </li>
            );
          })}
        </ul>
        <div className="cmdk-foot"><span><kbd>↑</kbd><kbd>↓</kbd> move</span><span><kbd>Enter</kbd> run</span><span><kbd>?</kbd> shortcuts</span></div>
      </div>
    </div>
  );
}

export function ShortcutsHelp({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => { if (open) ref.current?.focus(); }, [open]);
  if (!open) return null;
  return (
    <div className="cmdk-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="cmdk shortcuts" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts" tabIndex={-1} ref={ref}
           onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}>
        <div className="cmdk-input"><Icon name="keyboard" size={16} /><strong>Keyboard shortcuts</strong>
          <span className="spacer" /><button className="iconbtn" aria-label="Close shortcuts" onClick={onClose}><Icon name="close" size={14} /></button></div>
        <dl className="shortcut-list">
          {SHORTCUTS.map(([k, d]) => (<div key={k}><dt><kbd>{k}</kbd></dt><dd>{d}</dd></div>))}
        </dl>
      </div>
    </div>
  );
}
