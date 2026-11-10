#!/usr/bin/env python3
"""Render the 1200x630 social preview (frontend/public/og.png) from an inline HTML card.

    backend/.venv/bin/python scripts/media/make_og.py

No network and no data: a static brand card (name, tagline, the pipeline stages).
"""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "og.png"

HTML = """
<html><body style="margin:0;width:1200px;height:630px;background:#0b1115;color:#e7efed;
  font-family:Inter,system-ui,'Segoe UI',sans-serif;position:relative;overflow:hidden">
<div style="position:absolute;inset:0;background:
  radial-gradient(900px 420px at 85% 10%,rgba(111,195,184,.22),transparent 60%),
  radial-gradient(700px 380px at 10% 100%,rgba(230,168,126,.16),transparent 60%)"></div>
<div style="position:absolute;left:72px;top:64px;display:flex;align-items:center;gap:16px">
  <div style="width:44px;height:44px;border-radius:11px;background:#1d292f;border:1px solid rgba(216,230,230,.3);position:relative">
    <div style="position:absolute;left:11px;top:12px;width:20px;height:19px;border-left:4px solid #e6a87e;border-bottom:4px solid #6fc3b8;border-radius:2px"></div></div>
  <div style="font-size:30px;font-weight:700;letter-spacing:-.01em">CompileVista</div>
</div>
<div style="position:absolute;left:72px;top:170px;width:1060px">
  <div style="font-family:Georgia,'Times New Roman',serif;font-size:76px;line-height:1.06;font-weight:600;letter-spacing:-.015em">
    See how code becomes <span style="color:#6fc3b8;font-style:italic">execution.</span></div>
  <div style="margin-top:24px;font-size:27px;line-height:1.4;color:#b9c8c8;width:900px">
    Real tokens, syntax trees, LLVM IR, bytecode and recorded runs from Clang and CPython.</div>
</div>
<div style="position:absolute;left:72px;bottom:64px;display:flex;gap:12px;font:500 20px 'JetBrains Mono',ui-monospace,Consolas,monospace">
  <span style="padding:8px 16px;border:1px solid rgba(111,195,184,.5);border-radius:999px;color:#6fc3b8">tokens</span>
  <span style="padding:8px 16px;border:1px solid rgba(185,168,216,.5);border-radius:999px;color:#b9a8d8">syntax tree</span>
  <span style="padding:8px 16px;border:1px solid rgba(230,168,126,.5);border-radius:999px;color:#e6a87e">LLVM IR</span>
  <span style="padding:8px 16px;border:1px solid rgba(150,198,139,.5);border-radius:999px;color:#96c68b">bytecode</span>
  <span style="padding:8px 16px;border:1px solid rgba(216,230,230,.4);border-radius:999px;color:#b9c8c8">execution</span>
</div>
</body></html>
"""


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1200, "height": 630})
        page.set_content(HTML)
        page.screenshot(path=str(OUT), type="png")
        b.close()
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
