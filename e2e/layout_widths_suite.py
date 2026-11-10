"""Responsive layout guard: the workspace must not overlap itself at any width.

Regression: between the desktop frame and the mobile stack (around 1024px) the
side docks kept `top: 66px` and painted over the stage tabs. The older suites only
checked 1920 / 1366 / 390, so the gap went unnoticed.

Run: backend/.venv/bin/python e2e/layout_widths_suite.py   (repo root, stack running)
For every width it loads a pasted program into the real workspace, analyzes it, and
asserts (1) no page-level horizontal scroll, (2) no two workspace columns/blocks
intersect, (3) the stage pipeline bar is not covered by another element.
"""
from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "docs" / "TEST_EVIDENCE" / "layout_widths"
BASE = "http://127.0.0.1:5173"
WIDTHS = [(390, 844), (768, 1024), (1024, 768), (1180, 800), (1181, 800), (1440, 900), (1920, 1080)]
FAILED: list[str] = []
CONSOLE_ERRORS: list[str] = []

SOURCE = "def area(base, height):\n    return base * height / 2\n\nprint(area(3, 4))\n"

JS_CHECK = """
() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 1 && r.height > 1; };
  const grid = document.querySelector('.obs-grid');
  const blocks = grid ? [...grid.children].filter(vis) : [];
  const rects = blocks.map((e) => { const r = e.getBoundingClientRect();
    return { c: e.className.toString().slice(0, 24), l: r.left, t: r.top, r: r.right, b: r.bottom }; });
  const overlaps = [];
  for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) {
    const a = rects[i], b = rects[j];
    const w = Math.min(a.r, b.r) - Math.max(a.l, b.l), h = Math.min(a.b, b.b) - Math.max(a.t, b.t);
    if (w > 2 && h > 2) overlaps.push(`${a.c} x ${b.c} (${Math.round(w)}x${Math.round(h)}px)`);
  }
  // the first stage tab must be what the user actually hits at its centre point
  const tab = document.querySelector('.obs-center [class*=journey] button, .obs-center [role=tab]');
  let covered = null;
  if (tab) {
    tab.scrollIntoView({ block: 'center' });
    const r = tab.getBoundingClientRect();
    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    covered = !(hit && (hit === tab || tab.contains(hit) || hit.contains(tab)));
  }
  return { overlaps, covered, hasTab: !!tab, overflowX: document.documentElement.scrollWidth - innerWidth };
}
"""


def ok(cond: bool, what: str) -> None:
    if cond:
        print(f"  ok: {what}")
    else:
        FAILED.append(what)
        print(f"  FAIL: {what}")


def check_width(page, w: int, h: int) -> None:
    print(f"[width {w}x{h}]")
    page.set_viewport_size({"width": w, "height": h})
    page.goto(BASE + "/workspace")
    page.get_by_label("paste source code").fill(SOURCE)
    page.get_by_role("button", name="Load code").click()
    expect(page.get_by_role("list", name="snapshot files")).to_be_visible(timeout=15000)
    page.get_by_role("button", name="Analyze with CPython 3.12").click()
    expect(page.get_by_text("Token Formation").first).to_be_visible(timeout=60000)
    page.wait_for_timeout(600)  # let layout settle
    res = page.evaluate(JS_CHECK)
    ok(res["overflowX"] <= 1, f"{w}px: no horizontal page scroll (overflow {res['overflowX']}px)")
    ok(not res["overlaps"], f"{w}px: workspace blocks do not overlap {res['overlaps'] or ''}")
    ok(res["hasTab"] and res["covered"] is False, f"{w}px: stage tab is reachable (not covered)")
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / f"workspace_{w}.png"), full_page=False)


def main() -> None:
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", lambda m: CONSOLE_ERRORS.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: CONSOLE_ERRORS.append(str(e)))
        for w, h in WIDTHS:
            check_width(page, w, h)
        ok(not CONSOLE_ERRORS, f"zero console errors {CONSOLE_ERRORS[:3] or ''}")
        browser.close()
    print(f"\n{'ALL CHECKS PASSED' if not FAILED else 'FAILURES: ' + '; '.join(FAILED)}")
    if FAILED:
        raise SystemExit(1)
    print(f"elapsed: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
