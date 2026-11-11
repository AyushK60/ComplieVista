"""Keyboard and tab-order audit over the real screens (stack running on :5173).

For each page it presses Tab through the document and checks, for every focus stop:
  * a VISIBLE focus indicator (outline width > 0 with a non-transparent colour, or a box-shadow
    that differs from the unfocused state);
  * no keyboard trap (focus leaves the page's own controls within a bounded number of presses);
  * the stop is on-screen after focus (the browser scrolls it into view);
  * the order is not wildly out of reading order: a stop may not jump UP the page by more than
    one viewport height unless it wraps back to the start.
Then it drives the new learning panel and the Memory/process view with the keyboard only.
Usage:  python e2e/keyboard_suite.py
"""
from __future__ import annotations

import sys

from playwright.sync_api import Page, sync_playwright

BASE = "http://127.0.0.1:5173"
FAIL: list[str] = []

PROBE = """() => {
  const e = document.activeElement;
  if (!e || e === document.body) return null;
  const host = e.closest('.cm-editor') || e;   // CodeMirror draws its ring on the editor wrapper
  const cs = getComputedStyle(host), r = e.getBoundingClientRect();
  return {tag: e.tagName, name: (e.getAttribute('aria-label') || e.innerText || e.getAttribute('href') || e.className || '').toString().trim().slice(0, 40),
          ow: parseFloat(cs.outlineWidth) || 0, os: cs.outlineStyle, oc: cs.outlineColor, bs: cs.boxShadow,
          top: r.top + scrollY, h: r.height, w: r.width, vis: r.width > 0 && r.height > 0,
          inview: r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth};
}"""


def ok(cond: bool, what: str) -> None:
    print(("  ok: " if cond else "  FAIL: ") + what)
    if not cond:
        FAIL.append(what)


def audit(page: Page, label: str, limit: int = 120) -> None:
    print(f"[{label}]")
    page.evaluate("() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0); }")
    stops, no_ring, off, jumps, seen = 0, [], [], [], {}
    prev_top = -1.0
    for _ in range(limit):
        page.keyboard.press("Tab")
        page.wait_for_timeout(60)                  # let widgets such as CodeMirror apply their focus class
        info = page.evaluate(PROBE)
        if info is None:
            break
        if info["vis"] and not info["inview"]:      # smooth scrolling may still be in flight
            page.wait_for_timeout(450)
            info = page.evaluate(PROBE) or info
        key = (info["tag"], info["name"], round(info["top"]))
        if key in seen:           # focus wrapped around to an element already visited
            break
        seen[key] = 1
        stops += 1
        ring = (info["os"] != "none" and info["ow"] > 0 and "0, 0, 0, 0" not in info["oc"]) or \
               (info["bs"] not in ("none", ""))
        if info["vis"] and not ring:
            no_ring.append(f'{info["tag"]} "{info["name"]}"')
        if info["vis"] and not info["inview"]:
            off.append(f'{info["tag"]} "{info["name"]}"')
        if prev_top >= 0 and info["top"] < prev_top - 900:
            jumps.append(f'{info["tag"]} "{info["name"]}"')
        prev_top = info["top"]
    ok(stops >= 3, f"{label}: {stops} focus stops reached by Tab")
    ok(stops < limit, f"{label}: Tab does not trap focus (left the page controls within {limit} presses)")
    ok(not no_ring, f"{label}: every focus stop has a visible indicator" + (f" - missing on {no_ring[:4]}" if no_ring else ""))
    ok(not off, f"{label}: focused control is scrolled into view" + (f" - off-screen: {off[:3]}" if off else ""))
    ok(not jumps, f"{label}: tab order does not jump back up the page" + (f" - jumps: {jumps[:3]}" if jumps else ""))


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        for theme in ("light", "dark"):
            page.goto(BASE + "/")
            page.evaluate(f"() => {{ document.documentElement.dataset.theme = '{theme}'; }}")
            page.wait_for_timeout(600)
            audit(page, f"home-{theme}")
        page.goto(BASE + "/demos"); page.wait_for_timeout(1200); audit(page, "demo-library")
        page.goto(BASE + "/evidence"); page.wait_for_timeout(2000); audit(page, "evidence")
        page.goto(BASE + "/about"); page.wait_for_timeout(600); audit(page, "about")
        page.goto(BASE + "/workspace"); page.wait_for_timeout(1200); audit(page, "workspace-empty")

        # skip link: first Tab on a fresh page lands on it and it becomes visible
        page.goto(BASE + "/about"); page.wait_for_timeout(500)
        page.keyboard.press("Tab")
        first = page.evaluate("() => { const e = document.activeElement; return e ? [e.className, e.getBoundingClientRect().top] : null; }")
        ok(bool(first) and "skip" in str(first[0]) and first[1] >= 0, "first Tab stop is the skip link and it is visible")

        # --- Memory and process view and the learning panel, keyboard only ---
        import json, urllib.request
        def post(path):
            return json.load(urllib.request.urlopen(urllib.request.Request(BASE + path, method="POST"), timeout=120))
        run = post("/api/v1/demos/PY-03/run")
        url = (f"{BASE}/workspace?demo=PY-03&project=demo-library&execution={run['execution_id']}"
               f"&snapshot={run['snapshot_id']}&target={run['target_id']}&memory=1")
        page.goto(url); page.wait_for_selector(".mpv-ctl", timeout=30000); page.wait_for_timeout(800)
        audit(page, "memory-and-process", limit=200)
        page.focus(".mpv-ctl input[type=range]")
        before = page.inner_text(".mpv-ctl .muted")
        for _ in range(5):
            page.keyboard.press("ArrowRight")
        after = page.inner_text(".mpv-ctl .muted")
        ok(before != after, "slider moves with the arrow keys and updates the event counter")
        page.focus(".mpv-ctl .btn.primary"); page.keyboard.press("Enter"); page.wait_for_timeout(700)
        ok(page.get_attribute(".mpv-ctl .btn.primary", "aria-pressed") == "true", "Play toggles with Enter")
        page.keyboard.press("Enter")

        opt = post("/api/v1/demos/C-02/optimize")["experiment_id"]
        for _ in range(60):
            st = json.load(urllib.request.urlopen(f"{BASE}/api/v1/experiments/{opt}"))["status"]
            if st in ("COMPLETED", "FAILED"):
                break
            page.wait_for_timeout(2000)
        crun = post("/api/v1/demos/C-02/run")
        page.goto(f"{BASE}/workspace?demo=C-02&project=demo-library&execution={crun['execution_id']}"
                  f"&snapshot={crun['snapshot_id']}&target={crun['target_id']}&view=lesson")
        page.wait_for_selector(".ol-tabs", timeout=60000); page.wait_for_timeout(1500)
        page.focus(".ol-nav .btn.primary")
        say0 = page.inner_text(".ol-say")
        page.keyboard.press("Enter"); page.keyboard.press("Enter"); page.keyboard.press("Enter")
        ok(page.inner_text(".ol-say") != say0, "lesson advances with the keyboard (Next via Enter)")
        page.focus(".ol-tabs .btn:nth-child(2)"); page.keyboard.press("Enter"); page.wait_for_selector(".ol-row")
        page.focus(".ol-row"); page.keyboard.press("Enter"); page.wait_for_timeout(500)
        ok(page.get_attribute(".ol-row", "aria-pressed") == "true", "diff row is selectable with the keyboard")
        page.focus(".ol-tabs .btn:nth-child(4)"); page.keyboard.press("Enter"); page.wait_for_selector(".ol-opts")
        page.focus(".ol-opts .btn"); page.keyboard.press("Enter"); page.wait_for_timeout(500)
        ok(page.locator("[aria-live=polite] p").count() > 0, "quiz can be answered with the keyboard and reveals the result")

        ok(not errors, "zero console errors" + (f": {errors[:2]}" if errors else ""))
        browser.close()
    print("\nFAILURES: " + "; ".join(FAIL) if FAIL else "\nALL CHECKS PASSED")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
