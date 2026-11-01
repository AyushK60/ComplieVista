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
