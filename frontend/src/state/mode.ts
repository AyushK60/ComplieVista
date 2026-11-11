import { useEffect, useState } from "react";

/** Explore vs Technical presentation mode. Presentation-only: never resets
 * program/stage/selection state. Persisted; applied on <html data-mode>. */
export type Mode = "explore" | "technical";
const KEY = "cv.mode";

export function useMode(): [Mode, (m: Mode) => void] {
  const [mode, setMode] = useState<Mode>(() => {
    const saved = typeof localStorage !== "undefined" ? localStorage.getItem(KEY) : null;
    return saved === "technical" ? "technical" : "explore";
  });
  useEffect(() => {
    document.documentElement.dataset.mode = mode;
    localStorage.setItem(KEY, mode);
  }, [mode]);
  return [mode, setMode];
}

/** Teacher mode: large type, technical panels hidden. Presentation-only; persisted;
 * applied on <html data-teacher>. */
export function useTeacher(): [boolean, () => void] {
  const [on, setOn] = useState(() => {
    try { return localStorage.getItem("cv.teacher") === "on"; } catch { return false; }
  });
  useEffect(() => {
    document.documentElement.dataset.teacher = on ? "on" : "off";
    try { localStorage.setItem("cv.teacher", on ? "on" : "off"); } catch { /* ignore */ }
  }, [on]);
  return [on, () => setOn((v) => !v)];
}
