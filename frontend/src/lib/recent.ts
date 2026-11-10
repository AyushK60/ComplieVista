/** Recent sessions, kept only in this browser (localStorage) — never sent anywhere. */
export interface RecentSession {
  key: string; title: string; language: string; ts: number;
  project: string; snapshot: string; analysis?: string; execution?: string; target?: string;
}
const KEY = "cv.recent.v1";
const MAX = 12;

export function loadRecent(): RecentSession[] {
  try {
    const raw = localStorage.getItem(KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr.filter((r) => r && r.snapshot && r.project) : [];
  } catch { return []; }
}

export function recordRecent(s: Omit<RecentSession, "key" | "ts">): void {
  try {
    const key = s.snapshot;
    const prev = loadRecent().find((r) => r.key === key);
    const entry: RecentSession = { ...prev, ...s, key, ts: Date.now() };
    const rest = loadRecent().filter((r) => r.key !== key);
    localStorage.setItem(KEY, JSON.stringify([entry, ...rest].slice(0, MAX)));
  } catch { /* private mode / blocked storage: history is a convenience only */ }
}

export function clearRecent(): void {
  try { localStorage.removeItem(KEY); } catch { /* ignore */ }
}

export function recentUrl(r: RecentSession): string {
  const p = new URLSearchParams({ project: r.project, snapshot: r.snapshot });
  if (r.target) p.set("target", r.target);
  if (r.analysis) p.set("analysis", r.analysis);
  if (r.execution) p.set("execution", r.execution);
  return `/workspace?${p.toString()}`;
}
