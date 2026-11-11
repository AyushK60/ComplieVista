import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Link, useLocation, useNavigate, useNavigationType } from "react-router-dom";
import { useMode } from "../state/mode";
import { useTheme } from "../state/theme";
import { Command, isTypingTarget } from "../state/commands";
import CommandPalette, { ShortcutsHelp } from "./CommandPalette";
import { Icon } from "../ui";
import { prefetch } from "../lib/prefetch";

const TITLES: Array<[string, string]> = [
  ["/demos", "Demo Library"],
  ["/workspace", "Source Workspace"],
  ["/compare", "Compare C and Python"],
  ["/about", "About and Method"],
];

const LINKS: Array<[string, string]> = [
  ["/", "Home"],
  ["/demos", "Demo Library"],
  ["/workspace", "Workspace"],
  ["/compare", "Compare"],
  ["/about", "About"],
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useMode();
  const [theme, , toggleTheme] = useTheme();
  const { pathname, key } = useLocation();
  const navType = useNavigationType();
  const navigate = useNavigate();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  // on the home page the header floats over the hero and turns solid once the page scrolls
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 24);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, [pathname]);

  // Scroll: a new page opens at the top; Back and Forward return to where you were.
  const saved = useRef(new Map<string, number>());
  const keyRef = useRef(key);
  const first = useRef(true);
  useEffect(() => {
    const on = () => saved.current.set(keyRef.current, window.scrollY);
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  useEffect(() => {
    keyRef.current = key;
    if (first.current) { first.current = false; return; }
    let timer: ReturnType<typeof setTimeout> | undefined;
    if (navType === "POP") {
      const y = saved.current.get(key) ?? 0;
      let tries = 0;
      const tick = () => { // the page may still be loading its content: retry briefly
        window.scrollTo({ top: y, behavior: "instant" });
        if (Math.abs(window.scrollY - y) > 2 && tries++ < 20) timer = setTimeout(tick, 60);
      };
      tick();
    } else {
      window.scrollTo({ top: 0, behavior: "instant" });
    }
    return () => { if (timer) clearTimeout(timer); };
  }, [key, navType]);

  useEffect(() => {
    const hit = TITLES.find(([p]) => pathname === p || pathname.startsWith(p + "/"));
    document.title = hit ? `${hit[1]} — CompileVista` : "CompileVista — see how code becomes execution";
  }, [pathname]);

  // global keys: Ctrl/⌘+K palette, ? shortcuts (never while typing in a field)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setHelpOpen(false);
        setPaletteOpen((o) => !o);
        return;
      }
      if (e.key === "?" && !isTypingTarget(e.target) && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        setPaletteOpen(false);
        setHelpOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const base = useMemo<Command[]>(() => [
    ...LINKS.map(([to, label]): Command => ({
      id: "go:" + to, group: "Go to", title: label, run: () => navigate(to),
    })),
    { id: "mode", group: "Preferences", title: mode === "explore" ? "Switch to Technical mode (show provenance and digests)" : "Switch to Explore mode",
      keywords: "technical explore provenance", run: () => setMode(mode === "explore" ? "technical" : "explore") },
    { id: "theme", group: "Preferences", title: theme === "dark" ? "Switch to light theme" : "Switch to dark theme",
      keywords: "dark light theme appearance", run: toggleTheme },
    { id: "shortcuts", group: "Help", title: "Show keyboard shortcuts", hint: "?", run: () => setHelpOpen(true) },
    { id: "tour", group: "Help", title: "Take the guided tour", keywords: "tutorial intro walkthrough",
      run: () => { navigate("/workspace"); setTimeout(() => window.dispatchEvent(new Event("cv:tour")), 400); } },
  ], [navigate, mode, setMode, theme, toggleTheme]);

  return (
    <>
      <a href="#main" className="skip-link" onClick={(e) => {
        e.preventDefault();
        const m = document.querySelector<HTMLElement>("main");
        if (m) { m.setAttribute("tabindex", "-1"); m.focus(); }
      }}>Skip to main content</a>
      <nav className={"topnav" + (pathname === "/" ? " is-home" : "") + (scrolled ? " scrolled" : "")} aria-label="primary">
        <Link to="/" className="brand"><span className="brand-mark" aria-hidden />CompileVista</Link>
        {LINKS.map(([to, label]) => (
          <NavLink key={to} to={to} end={to === "/"}
                   onMouseEnter={() => prefetch(to)} onFocus={() => prefetch(to)}
                   className={({ isActive }) => isActive ? "navlink active" : "navlink"}>
            {label}
          </NavLink>
        ))}
        <div className="navtools">
          <button className="kbdhint" title="Open the command palette" onClick={() => setPaletteOpen(true)}>
            <Icon name="search" size={13} /><span className="kbdtext">Search</span>{" "}<span>Ctrl K</span>
          </button>
          <button className="iconbtn" onClick={toggleTheme}
                  aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
                  title={theme === "dark" ? "Light theme" : "Dark theme"}>
            <Icon name={theme === "dark" ? "sun" : "moon"} size={15} />
          </button>
          <div className="modeswitch" role="group" aria-label="experience mode">
            <button aria-pressed={mode === "explore"} onClick={() => setMode("explore")}>Explore</button>
            <button aria-pressed={mode === "technical"} onClick={() => setMode("technical")}>Technical</button>
          </div>
        </div>
      </nav>
      <div key={pathname.split("/")[1] || "home"} className="route-fade">{children}</div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} base={base} />
      <ShortcutsHelp open={helpOpen} onClose={() => setHelpOpen(false)} />
    </>
  );
}
