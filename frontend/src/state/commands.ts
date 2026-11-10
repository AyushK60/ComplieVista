import { useEffect, useSyncExternalStore } from "react";

/** A tiny command registry. Pages register the commands that make sense right now
 * (for example, the jump-to-stage list in the workspace); the palette reads them. */
export type Command = {
  id: string;
  title: string;
  group: string;
  keywords?: string;
  hint?: string;
  run: () => void;
};

const registered = new Map<string, Command[]>();
const listeners = new Set<() => void>();
let snapshot: Command[] = [];

function rebuild() {
  snapshot = [...registered.values()].flat();
  listeners.forEach((l) => l());
}

export function registerCommands(owner: string, cmds: Command[]): () => void {
  registered.set(owner, cmds);
  rebuild();
  return () => { registered.delete(owner); rebuild(); };
}

export function useRegisteredCommands(): Command[] {
  return useSyncExternalStore(
    (cb) => { listeners.add(cb); return () => listeners.delete(cb); },
    () => snapshot,
  );
}

/** Register commands for the lifetime of a component. `cmds` should be memoized. */
export function useCommands(owner: string, cmds: Command[]) {
  useEffect(() => registerCommands(owner, cmds), [owner, cmds]);
}

/** Subsequence match with a simple score; empty query matches everything. */
export function score(query: string, text: string): number {
  if (!query) return 1;
  const q = query.toLowerCase();
  const t = text.toLowerCase();
  const at = t.indexOf(q);
  if (at >= 0) return 100 - at;          // contiguous hit, earlier is better
  let i = 0, run = 0, best = 0;
  for (const ch of t) {
    if (ch === q[i]) { i++; run++; best = Math.max(best, run); } else run = 0;
    if (i === q.length) return 10 + best;
  }
  return 0;
}

export function isTypingTarget(el: EventTarget | null): boolean {
  const n = el as HTMLElement | null;
  if (!n || !n.tagName) return false;
  const tag = n.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || n.isContentEditable
    || !!n.closest?.(".cm-editor");
}
