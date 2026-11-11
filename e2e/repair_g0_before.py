"""Before-state screenshots of the PY-02 Watch view and the PY-02/C AST view.
Real stack, real demos. Viewports: 1920x1080, 1366x768, 390x844.
Run: backend/.venv/bin/python e2e/repair_g0_before.py   (repo root, stack running)
"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "e2e" / "screenshots" / "repair_watch_ast" / "before"
BASE = "http://127.0.0.1:5173"
CONSOLE_ERRORS: list[str] = []


def shot(page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / name), full_page=False)
    print(f"  screenshot: e2e/screenshots/repair_watch_ast/before/{name}")


def open_demo(page, demo_id: str) -> None:
    page.goto(BASE + "/demos")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1200)
    page.evaluate(
        """(id) => {
          const card = [...document.querySelectorAll('.democard')]
            .find((c) => c.textContent.includes(id));
          if (!card) throw new Error('card missing ' + id);
          card.click();
        }""", demo_id)
    page.wait_for_timeout(400)


def watch(page, demo_id: str) -> None:
    open_demo(page, demo_id)
    page.evaluate("""() => {
      [...document.querySelectorAll('button')]
        .find((b) => b.textContent.includes('Watch This Program Work')).click();
    }""")
    page.wait_for_url("**/workspace?*walkthrough=1", timeout=120_000)
    page.wait_for_selector(".walkthrough", timeout=30_000)
    page.wait_for_timeout(3500)


def explore(page, demo_id: str) -> None:
    open_demo(page, demo_id)
    page.evaluate("""() => {
      [...document.querySelectorAll('button')]
        .find((b) => b.textContent.includes('Explore this program →')).click();
    }""")
    page.wait_for_selector(".obs-app", timeout=90_000)
    page.wait_for_timeout(2500)


def ast(page, demo_id: str) -> None:
    explore(page, demo_id)
    page.evaluate(
        """(name) => {
          [...document.querySelectorAll('button.jstage')]
            .find((b) => b.textContent.includes(name))?.click();
        }""", "Syntax Tree")
    page.wait_for_selector(".graphwrap", timeout=30_000)
    page.wait_for_timeout(2600)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # 1920x1080 - Watch
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.on("console", lambda m: CONSOLE_ERRORS.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: CONSOLE_ERRORS.append(str(e)))
        watch(page, "PY-02")
        shot(page, "watch_py02_1920x1080.png")
        # geometry audit of the walkthrough panels
        audit = page.evaluate("""() => {
          const sel = ['.wt-src','.wt-flow','.wt-stack','.wt-vars','.wt-out','.theater-controls'];
          const out = {};
          for (const s of sel) {
            const el = document.querySelector(s);
            out[s] = el ? el.getBoundingClientRect().toJSON() : null;
          }
          const center = document.querySelector('.obs-center');
          out['.obs-center'] = center ? center.getBoundingClientRect().toJSON() : null;
          out.centerScrollable = center ? { sh: center.scrollHeight, ch: center.clientHeight } : null;
          const srcBody = document.querySelector('.wt-src-body');
          out.srcBody = srcBody ? { sh: srcBody.scrollHeight, ch: srcBody.clientHeight,
                                    lines: srcBody.querySelectorAll('.wt-srcline').length } : null;
          return out;
        }""")
        print("  geometry:", json.dumps(audit))
        # AST at 1920
        ast(page, "PY-02")
        shot(page, "ast_py02_1920x1080.png")
        page.close()
        # 1366x768
        page = browser.new_page(viewport={"width": 1366, "height": 768})
        page.on("console", lambda m: CONSOLE_ERRORS.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: CONSOLE_ERRORS.append(str(e)))
        watch(page, "PY-02")
        shot(page, "watch_py02_1366x768.png")
        ast(page, "PY-02")
        shot(page, "ast_py02_1366x768.png")
        page.close()
        # 390x844 mobile
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.on("console", lambda m: CONSOLE_ERRORS.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: CONSOLE_ERRORS.append(str(e)))
        watch(page, "PY-02")
        shot(page, "watch_py02_390x844.png")
        ast(page, "PY-02")
        shot(page, "ast_py02_390x844.png")
        page.close()
        browser.close()
    print(f"console errors: {len(CONSOLE_ERRORS)}")
    for e in CONSOLE_ERRORS[:8]:
        print("  ", e[:160])


if __name__ == "__main__":
    main()
