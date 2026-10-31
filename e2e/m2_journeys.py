"""M2-F browser E2E journeys (Windows Playwright → Vite/WSL → FastAPI/WSL).

Run from Windows:  python e2e/m2_journeys.py
Exercises the real Analyze flow: pasted C with genuine AST+IR, pasted Python with
genuine AST+bytecode, a syntax-error case with real diagnostics, source-line
highlighting, and no-runtime-execution states. Real backend artifacts only.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "docs" / "TEST_EVIDENCE" / "m2"
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
    print(f"  screenshot: docs/TEST_EVIDENCE/m2/{name}")


def step(name: str) -> None:
    print(f"[journey] {name}")


def ok(page: Page, what: str) -> None:
    print(f"  ok: {what}")


def fail(page: Page, what: str, e: Exception) -> None:
    FAILED.append(f"{what}: {e}")
    print(f"  FAIL: {what}: {e}")
    shot(page, f"failure_{what.replace(' ', '_')}.png")


def paste_and_analyze(page: Page, language: str, filename: str, content: str):
    page.goto(BASE + "/workspace")
    page.get_by_role("tab", name="Paste").click()
    page.get_by_label("Language").select_option(language)
    page.get_by_label("Filename").fill(filename)
    page.get_by_label("paste source code").fill(content)
    page.get_by_role("button", name="Create snapshot").click()
    expect(page.get_by_text("Snapshot created")).to_be_visible(timeout=20000)
    page.get_by_role("button", name="Analyze with real").click()


def journey_c(page: Page) -> None:
    step("C: paste → Analyze → genuine AST, IR blocks, object evidence")
    paste_and_analyze(page, "c", "demo.c", C_SRC)
    stage = page.get_by_role("tab", name="ast AVAILABLE")
    expect(stage).to_be_visible(timeout=120000)
    stage.click()
    page.get_by_role("tab", name="Table").click()  # M3 defaults to graph; Table preserved
    expect(page.locator(".tree")).to_be_visible()
    expect(page.locator(".tree").get_by_text("FunctionDecl", exact=False).first).to_be_visible()
    ok(page, "Clang AST tree renders real FunctionDecl nodes")
    page.get_by_role("tab", name="ir_o0 AVAILABLE").click()
    page.get_by_role("tab", name="Table").click()  # M3 view toggle
    expect(page.locator(".irfunc").first).to_be_visible()
    expect(page.get_by_text("define @adjust", exact=False).first).to_be_visible()
    expect(page.locator(".blocks li").first).to_be_visible()
    ok(page, "LLVM IR functions with real blocks (terminator-derived edges)")
    page.get_by_role("tab", name="object AVAILABLE").click()
    expect(page.get_by_text("object sha256").first).to_be_visible()
    ok(page, "object artifact with recorded sha256")
    # CV-04: raw toggle must not leak text across stages
    page.get_by_role("tab", name="preprocess AVAILABLE").click()
    page.get_by_role("button", name="Show raw tool output").click()
    expect(page.locator(".excerpt").first).to_contain_text("demo.c", timeout=15000)
    page.get_by_role("tab", name="tokens AVAILABLE").click()
    expect(page.get_by_role("button", name="Show raw tool output")).to_be_visible()
    assert page.locator(".excerpt").count() == 0, "stale raw text across stages (CV-04)"
    ok(page, "raw output never shown under another stage's name")
    # source highlighting via AST node click (M2 tree view, preserved as fallback)
    page.get_by_role("tab", name="ast AVAILABLE").click()
    page.get_by_role("tab", name="Table").click()  # M3 defaults graph; M2 tree in Table
    page.locator(".astnode", has_text="FunctionDecl").first.locator(".tw").click()
    node = page.locator(".astnode", has_text="CompoundStmt").first
    expect(node).to_be_visible()
    node.click()
    hl = page.locator(".codeline.hl")
    expect(hl).to_have_count(1)
    ok(page, "clicking AST node highlights its source line")
    shot(page, "c_analysis_ast_ir_object.png")


def journey_python(page: Page) -> None:
    step("Python: paste → Analyze → genuine tokens/AST/bytecode")
    paste_and_analyze(page, "python", "fib.py", PY_SRC)
    expect(page.get_by_role("tab", name="bytecode AVAILABLE")).to_be_visible(timeout=120000)
    # CV-05: python tokens carry line info and highlight source on click
    page.get_by_role("tab", name="tokens AVAILABLE").click()
    tok = page.locator(".token.clickable", has_text="fib").first
    tok.click()
    expect(page.locator(".codeline.hl")).to_have_count(1)
    ok(page, "python token click highlights its source line")
    # CV-06: real code-object metadata explorer
    page.get_by_role("tab", name="code_object AVAILABLE").click()
    expect(page.locator("table.grid").get_by_text("qualname", exact=True)).to_be_visible()
    expect(page.locator("table.grid").get_by_text("fib", exact=True).first).to_be_visible()
    expect(page.locator("table.grid").get_by_text("argcount", exact=True)).to_be_visible()
    ok(page, "code-object inspector shows real fields (id/qualname/argcount)")
    page.get_by_role("tab", name="bytecode AVAILABLE").click()
    page.get_by_role("tab", name="Table").click()  # M3 view toggle
    expect(page.locator("table.grid").first).to_be_visible()
    expect(page.locator("table.grid").get_by_text("BINARY_OP", exact=False).first).to_be_visible()
    instr = page.locator("table.grid tr.clickable").nth(3)
    instr.click()
    expect(page.locator(".codeline.hl")).to_have_count(1)
    ok(page, "bytecode instruction click highlights its source line")
    page.get_by_role("tab", name="code_object AVAILABLE").click()
    expect(page.get_by_text("fib", exact=False).first).to_be_visible()
    shot(page, "python_analysis_bytecode.png")


def journey_error(page: Page) -> None:
    step("Python syntax error: real CPython diagnostics, honest stage availability")
    paste_and_analyze(page, "python", "broken.py", PY_BROKEN)
    diag_tab = page.get_by_role("tab", name="diagnostics AVAILABLE")
    expect(diag_tab).to_be_visible(timeout=120000)
    diag_tab.click()
    expect(page.get_by_text("invalid syntax").first).to_be_visible()
    expect(page.get_by_text("line 1:", exact=False).first).to_be_visible()
    # bytecode stage must NOT be available for unparseable source
    assert page.get_by_role("tab", name="bytecode AVAILABLE").count() == 0
    ok(page, "SyntaxError diagnostic with exact location; bytecode honestly unavailable")
    shot(page, "python_syntax_error_diags.png")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        for journey in (journey_c, journey_python, journey_error):
            try:
                journey(page)
            except Exception as e:  # noqa: BLE001
                fail(page, journey.__name__, e)
        browser.close()
    print()
    if FAILED:
        print(f"E2E RESULT: FAIL ({len(FAILED)} failures)")
        return 1
    print("E2E RESULT: PASS (3 M2 journeys)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
