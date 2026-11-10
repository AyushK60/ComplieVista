import { useCallback, useEffect, useState } from "react";

/** Light/dark theme. "system" follows the OS until the user picks one; the choice is
 * stored in this browser only. Applied on <html data-theme> (see also index.html, which
 * sets it before first paint so there is no flash). */
export type Theme = "light" | "dark";
const KEY = "cv.theme";

function systemTheme(): Theme {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function stored(): Theme | null {
  try {
    const v = localStorage.getItem(KEY);
    return v === "dark" || v === "light" ? v : null;
  } catch { return null; }
}

export function applyTheme(t: Theme) {
  document.documentElement.dataset.theme = t;
}

export function useTheme(): [Theme, (t: Theme) => void, () => void] {
  const [theme, setThemeState] = useState<Theme>(() => stored() ?? systemTheme());
  useEffect(() => { applyTheme(theme); }, [theme]);
  // follow the OS only while the user has not chosen
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!mq) return;
    const on = () => { if (!stored()) setThemeState(mq.matches ? "dark" : "light"); };
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  const setTheme = useCallback((t: Theme) => {
    try { localStorage.setItem(KEY, t); } catch { /* private mode: still apply for this tab */ }
    setThemeState(t);
  }, []);
  const toggle = useCallback(() => setTheme(theme === "dark" ? "light" : "dark"), [theme, setTheme]);
  return [theme, setTheme, toggle];
}
