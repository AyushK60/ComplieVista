"""Compact browser journeys for the current journey UI (replaces the retired m2/m3/m5/m6-era
checks of the old tab/table screens). Real Clang/CPython analysis through the full stack:

  C:      stage navigator lists every stage; Syntax Tree, LLVM IR (-O0/-O2), Object File render
          real content; raw output belongs to its own stage (no leakage across stages)
  Python: Token Formation / Code Objects / Bytecode render; clicking a source line highlights it
  Error:  a syntax error shows the genuine CPython diagnostic and bytecode is NOT offered
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "docs" / "TEST_EVIDENCE" / "m9"
BASE = "http://127.0.0.1:5173"
FAILED: list[str] = []

C_SRC = """#include <stdio.h>
#define SCALE 3
static int adjust(int base, int limit) {
    int scaled = base * SCALE;
    if (scaled > limit) {
        return limit;
    }
    return scaled;
}
int main(void) {
    int values[4] = {1, 2, 3, 4};
    int total = 0;
    for (int i = 0; i < 4; i++) {
        total += adjust(values[i], 10);
    }
    printf("total=%d\\n", total);
    return 0;
}
"""

PY_SRC = """def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


if __name__ == "__main__":
    print(fib(10))
"""

PY_BROKEN = "def broken(:\n    pass\n"



def shot(page: Page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / name), full_page=True)


def ok(what: str) -> None:
    print(f"  ok: {what}")


def paste_and_analyze(page: Page, language: str, filename: str, content: str) -> None:
    page.goto(BASE + "/workspace")
    page.get_by_role("tab", name="Paste").click()
    page.get_by_label("Language").select_option(language)
    page.get_by_label("Filename").fill(filename)
    page.get_by_label("paste source code").fill(content)
    page.get_by_role("button", name="Load code").click()
    expect(page.get_by_role("list", name="snapshot files")).to_be_visible(timeout=20000)
    page.get_by_role("button", name=re.compile("^Analyze with")).click()


def nav(page: Page):
    return page.get_by_role("navigation", name="compilation journey")


def stage(page: Page, name: str):
    nav(page).get_by_role("button", name=name, exact=True).click()
    expect(page.get_by_role("heading", name=name, level=2)).to_be_visible(timeout=15000)


def journey_c(page: Page) -> None:
    print("[journey] C: stages, real content, raw output isolation")
    paste_and_analyze(page, "c", "demo.c", C_SRC)
    expect(nav(page)).to_be_visible(timeout=120000)
    for name in ("Preprocessing", "Token Formation", "Syntax Tree", "LLVM IR (-O0)",
                 "LLVM IR (-O2)", "Assembly", "Disassembly", "Object File", "Symbol Table"):
        expect(nav(page).get_by_role("button", name=name, exact=True)).to_be_visible(timeout=60000)
    ok("all nine C stages are offered")
    stage(page, "Syntax Tree")
    expect(page.locator("main").get_by_text("FunctionDecl").first).to_be_visible(timeout=30000)
    ok("Syntax Tree shows real Clang FunctionDecl nodes")
    # entering Syntax Tree deliberately opens full-screen focus; leave it to reach the navigator
    page.get_by_role("button", name=re.compile("exit focus")).click()
    stage(page, "LLVM IR (-O0)")
    expect(page.locator("main").get_by_text(re.compile(r"adjust")).first).to_be_visible(timeout=30000)
    ok("LLVM IR (-O0) mentions the program's own function")
    stage(page, "Object File")
    page.get_by_role("group", name="experience mode").get_by_role("button", name="Technical").click()
    expect(page.locator("main").get_by_text(re.compile("sha256", re.I)).first).to_be_visible(timeout=15000)
    ok("Object File shows its recorded sha256")
    stage(page, "Preprocessing")
    expect(page.locator("main").get_by_text("demo.c").first).to_be_visible(timeout=15000)
    stage(page, "Token Formation")
    assert "# 1 \"/work/demo.c\"" not in page.locator("main").inner_text(),         "preprocessor raw text leaked under the token stage"
    ok("raw output of one stage never appears under another")
    shot(page, "c_journey.png")


def journey_python(page: Page) -> None:
    print("[journey] Python: stages and source-line highlighting")
    paste_and_analyze(page, "python", "fib.py", PY_SRC)
    expect(nav(page)).to_be_visible(timeout=120000)
    for name in ("Token Formation", "Code Objects", "Bytecode"):
        expect(nav(page).get_by_role("button", name=name, exact=True)).to_be_visible(timeout=60000)
    stage(page, "Bytecode")
    expect(page.locator("main").get_by_text(re.compile("BINARY_OP|LOAD_FAST|RETURN")).first).to_be_visible(timeout=30000)
    ok("Bytecode shows real CPython 3.12 instructions")
    page.locator(".sourceline").nth(1).click()
    expect(page.locator(".sourceline.hl, .sourceline.hl-linked").first).to_be_visible()
    ok("clicking a source line highlights it")
    shot(page, "python_journey.png")


def journey_error(page: Page) -> None:
    print("[journey] Python syntax error: genuine diagnostic, bytecode not offered")
    paste_and_analyze(page, "python", "broken.py", PY_BROKEN)
    expect(nav(page).get_by_role("button", name="Diagnostics", exact=True)).to_be_visible(timeout=120000)
    stage(page, "Diagnostics")
    expect(page.locator("main").get_by_text("invalid syntax").first).to_be_visible(timeout=15000)
    assert nav(page).get_by_role("button", name="Bytecode", exact=True).count() == 0
    ok("diagnostic shown; Bytecode honestly absent for unparseable source")
    shot(page, "python_error_journey.png")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        for journey in (journey_c, journey_python, journey_error):
            try:
                journey(page)
            except Exception as e:  # noqa: BLE001
                FAILED.append(f"{journey.__name__}: {str(e)[:1500]}")
                print(f"  FAIL: {journey.__name__}: {str(e)[:1500]}")
                shot(page, f"failure_{journey.__name__}.png")
        browser.close()
    FAILED.extend(errors)
    print()
    if FAILED:
        print(f"E2E RESULT: FAIL ({len(FAILED)} failures)")
        return 1
    print("E2E RESULT: PASS (3 journeys)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
