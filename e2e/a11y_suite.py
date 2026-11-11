"""Accessibility scan with axe-core (WCAG 2.0/2.1 A + AA rules) over the real screens.

Usage (repo root, inside WSL, stack running):
    backend/.venv/bin/python e2e/a11y_suite.py          # fails on serious/critical violations
    A11Y_ALL=1 backend/.venv/bin/python e2e/a11y_suite.py   # also fails on moderate/minor

Each screen is reached through the real UI (no mocks). Violations are printed with the rule,
impact, the number of affected elements and the first selectors, so they can be fixed
at the source. axe covers what a machine can check (contrast, names, roles, landmarks,
labels); it does not replace a manual keyboard / screen-reader pass.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:5173"
AXE = (REPO / "frontend" / "node_modules" / "axe-core" / "axe.min.js").read_text(encoding="utf-8")
RANK = {"minor": 1, "moderate": 2, "serious": 3, "critical": 4}
THRESHOLD = 1 if os.environ.get("A11Y_ALL") else 3
C_SRC = (REPO / "backend" / "tests" / "fixtures" / "linemap" / "demo.c").read_text()
FAIL: list[str] = []


def scan(page: Page, name: str) -> None:
    page.evaluate(AXE)
    res = page.evaluate("""async () => await axe.run(document, {
        runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } })""")
    vs = res["violations"]
    bad = [v for v in vs if RANK.get(v["impact"], 0) >= THRESHOLD]
    print(f"[{name}] {len(res['passes'])} rules passed, {len(vs)} violation(s), {len(bad)} at/above threshold")
    for v in vs:
        mark = "FAIL" if v in bad else "note"
        sel = "; ".join(" ".join(n["target"][0:1]) for n in v["nodes"][:3])
        print(f"   {mark} {v['id']} ({v['impact']}) x{len(v['nodes'])}: {v['help']} :: {sel[:200]}")
        if v["id"] == "color-contrast":
            for n in v["nodes"][:4]:
                msg = (n["any"] or [{}])[0].get("message", "")
                print(f"        {' '.join(n['target'][:1])[:70]} -> {msg[:150]}")
        if v in bad:
            FAIL.append(f"{name}: {v['id']} ({v['impact']}) x{len(v['nodes'])}")


def paste_load(page: Page, language: str, filename: str, text: str) -> None:
    page.goto(BASE + "/workspace")
    page.get_by_role("tab", name="Paste").click()
    page.get_by_label("Language").select_option(language)
    page.get_by_label("Filename").fill(filename)
    editor = page.get_by_label("paste source code")
    expect(editor).to_be_visible(timeout=20000)
    editor.click()
    page.keyboard.press("Control+A")
    page.keyboard.insert_text(text)
    page.get_by_role("button", name="Load code").click()
    expect(page.get_by_role("list", name="snapshot files")).to_be_visible(timeout=20000)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        steps = []

        def go(name, fn):
            try:
                fn()
                page.wait_for_timeout(600)
                scan(page, name)
            except Exception as e:  # noqa: BLE001
                FAIL.append(f"{name}: could not reach screen: {str(e)[:200]}")
                print(f"[{name}] COULD NOT REACH: {str(e)[:200]}")

        go("home", lambda: (page.goto(BASE + "/"), expect(page.locator(".jw-rail")).to_be_visible(timeout=60000), page.wait_for_timeout(800)))
        go("about", lambda: (page.goto(BASE + "/about"), expect(page.get_by_role("heading", level=1)).to_be_visible(timeout=15000)))
        def palette():
            page.goto(BASE + "/demos")
            expect(page.locator(".democard").first).to_be_visible(timeout=15000)
            page.keyboard.press("Control+k")
            expect(page.get_by_role("dialog", name="Command palette")).to_be_visible(timeout=5000)
        go("command-palette", palette)
        def dark_home():
            page.keyboard.press("Escape")
            page.goto(BASE + "/demos")
            page.evaluate("localStorage.setItem('cv.theme','dark')")
            page.reload()
            expect(page.locator(".democard").first).to_be_visible(timeout=15000)
        go("demo-library-dark", dark_home)
        go("reset-theme", lambda: (page.evaluate("localStorage.removeItem('cv.theme')"), page.goto(BASE + "/demos/PY-03"), expect(page.locator(".demo-detail")).to_be_visible(timeout=15000)))
        go("demo-library", lambda: (page.goto(BASE + "/demos"), expect(page.locator(".democard").first).to_be_visible(timeout=15000)))
        go("demo-detail", lambda: (page.goto(BASE + "/demos/PY-03"), expect(page.locator(".demo-detail")).to_be_visible(timeout=15000)))
        go("compare", lambda: (page.goto(BASE + "/compare"), expect(page.get_by_role("heading", level=1)).to_be_visible(timeout=15000)))
        go("workspace-empty", lambda: (page.goto(BASE + "/workspace"), expect(page.get_by_label("paste source code")).to_be_visible(timeout=20000)))
        go("workspace-loaded-c", lambda: paste_load(page, "c", "demo.c", C_SRC))

        def analyzed():
            page.get_by_role("button", name=re.compile("^Analyze with")).click()
            expect(page.get_by_role("navigation", name="compilation journey")).to_be_visible(timeout=120000)
        go("journey-c", analyzed)

        def ir_stage():
            page.get_by_role("navigation", name="compilation journey").get_by_role("button", name="LLVM IR (-O0)", exact=True).click()
            expect(page.get_by_role("heading", name="LLVM IR (-O0)", level=2)).to_be_visible(timeout=20000)
        go("stage-ir", ir_stage)

        def ast_stage():
            page.get_by_role("navigation", name="compilation journey").get_by_role("button", name="Syntax Tree", exact=True).click()
            expect(page.get_by_role("heading", name="Syntax Tree", level=2)).to_be_visible(timeout=20000)
        go("stage-ast-focus", ast_stage)

        def opt_lab():
            page.get_by_role("button", name=re.compile("exit focus")).click()
            page.get_by_role("tab", name="Optimization lab").click()
            page.get_by_role("button", name=re.compile(r"Build -O0.*-O2")).click()
            expect(page.locator(".slv")).to_be_visible(timeout=240000)
        go("optimization-lab", opt_lab)

        def execution():
            page.goto(BASE + "/demos/PY-03")
            page.get_by_role("button", name="Run (observatory)").click()
            expect(page.locator(".execdock")).to_be_visible(timeout=120000)
        go("execution", execution)

        def walkthrough():
            page.get_by_role("tab", name="Watch it work").click()
            page.wait_for_timeout(1500)
        go("watch-it-work", walkthrough)

        browser.close()
    print()
    if FAIL:
        print(f"A11Y RESULT: FAIL ({len(FAIL)}): {json.dumps(FAIL, indent=1)}")
        return 1
    print("A11Y RESULT: PASS (no violations at or above the threshold)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
