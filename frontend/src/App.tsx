import { lazy, Suspense } from "react";
import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";
import AppShell from "./components/AppShell";
import Home from "./pages/Home";
import { Skeleton } from "./ui";

const Workspace = lazy(() => import("./pages/Workspace"));
const Compare = lazy(() => import("./pages/Compare"));
const DemoLibrary = lazy(() => import("./pages/DemoLibrary"));
const About = lazy(() => import("./pages/About"));

function NotFound() {
  return (
    <main className="obs obs-empty">
      <div className="obs-ingest panel">
        <h1>That page doesn’t exist</h1>
        <p className="muted">Try the <Link to="/demos">Demo Library</Link>, paste your own code in the{" "}
          <Link to="/workspace">Source Workspace</Link>, or go back <Link to="/">home</Link>.</p>
      </div>
    </main>
  );
}

/** Loading placeholder shaped like the page that is about to appear. */
function RouteFallback() {
  const { pathname } = useLocation();
  const kind = pathname.startsWith("/workspace") ? "ws" : pathname.startsWith("/demos") ? "lib" : "page";
  return (
    <main className={"obs obs-empty skel-route skel-" + kind} aria-busy="true" aria-label="Loading page">
      {kind === "lib" ? (
        <div className="skel-lib">
          <i className="skel-title" />
          {Array.from({ length: 6 }, (_, i) => <i key={i} className="skel-card" />)}
        </div>
      ) : kind === "ws" ? (
        <div className="skel-ws"><i /><i /><i /></div>
      ) : (
        <div style={{ width: "min(560px, 90vw)" }}><Skeleton rows={5} label="Loading page" /></div>
      )}
    </main>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/workspace" element={<Workspace />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/about" element={<About />} />
          <Route path="/demos" element={<DemoLibrary />} />
          <Route path="/demos/:demoId" element={<DemoLibrary />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
        </Suspense>
      </AppShell>
    </BrowserRouter>
  );
}
