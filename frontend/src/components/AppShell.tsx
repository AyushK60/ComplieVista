import { NavLink, Link } from "react-router-dom";
import { useMode } from "../state/mode";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useMode();
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
