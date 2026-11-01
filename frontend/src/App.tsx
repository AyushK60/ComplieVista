import { BrowserRouter, Route, Routes } from "react-router-dom";
import Home from "./pages/Home";
import Workspace from "./pages/Workspace";
import Compare from "./pages/Compare";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/workspace" element={<Workspace />} />
        <Route path="/compare" element={<Compare />} />
      </Routes>
    </BrowserRouter>
  );
}
