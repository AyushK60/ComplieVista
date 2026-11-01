import { BrowserRouter, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import Home from "./pages/Home";
import Workspace from "./pages/Workspace";
import Compare from "./pages/Compare";
import DemoLibrary from "./pages/DemoLibrary";

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/workspace" element={<Workspace />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/demos" element={<DemoLibrary />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}
