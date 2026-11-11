/**
 * Preload the code for a page when the pointer or keyboard focus reaches a link to it, so the
 * click opens it without the loading placeholder. These are the same dynamic imports App.tsx
 * uses, so the bundler shares the chunks; calling one twice is harmless.
 */
const loaders: Record<string, () => Promise<unknown>> = {
  workspace: () => import("../pages/Workspace"),
  compare: () => import("../pages/Compare"),
  demos: () => import("../pages/DemoLibrary"),
  about: () => import("../pages/About"),
};

const done = new Set<string>();

export function prefetch(path: string): void {
  const key = path.split("/")[1] ?? "";
  const load = loaders[key];
  if (!load || done.has(key)) return;
  done.add(key);
  load().catch(() => done.delete(key));
}
