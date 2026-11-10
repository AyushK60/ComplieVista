import { useEffect } from "react";
import { NavLink, Link, useLocation } from "react-router-dom";
import { useMode } from "../state/mode";

const TITLES: Array<[string, string]> = [
  ["/demos", "Demo Library"],
  ["/workspace", "Source Workspace"],
  ["/compare", "Compare C and Python"],
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useMode();
  const { pathname } = useLocation();
  useEffect(() => {
    const hit = TITLES.find(([p]) => pathname === p || pathname.startsWith(p + "/"));
    document.title = hit ? `${hit[1]} — CompileVista` : "CompileVista — see how code becomes execution";
  }, [pathname]);
  return (
    <>
      <nav className="topnav">
        <Link to="/" className="brand"><span className="brand-mark" aria-hidden />CompileVista</Link>
        {[
          ["/", "Home"],
          ["/demos", "Demo Library"],
          ["/workspace", "Source Workspace"],
          ["/compare", "Compare"],
        ].map(([to, label]) => (
          <NavLink key={to} to={to} end={to === "/"}
                   className={({ isActive }) => isActive ? "navlink active" : "navlink"}>
            {label}
          </NavLink>
        ))}
        <div className="spacer" style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 14 }}>
          <div className="modeswitch" role="group" aria-label="experience mode">
            <button aria-pressed={mode === "explore"} onClick={() => setMode("explore")}>Explore</button>
            <button aria-pressed={mode === "technical"} onClick={() => setMode("technical")}>Technical</button>
          </div>
        </div>
      </nav>
      {children}
    </>
  );
}
