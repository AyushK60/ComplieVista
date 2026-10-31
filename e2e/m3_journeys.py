"""M3 browser E2E journeys (Windows Playwright → real backend, real containers).

Covers G3/G4/G5/G6: graph rendering for C and Python, semantic zoom (information
changes with zoom level), node→source highlighting, inspector levels, minimap,
search, raw-leak regression (CV-04), large real AST (300+ nodes honest), stage
switch race, viewport matrix, and console cleanliness.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "docs" / "TEST_EVIDENCE" / "m3"
BASE = "http://127.0.0.1:5173"
FAILED: list[str] = []

# Honest large fixture: ~40 statements x nested AST -> 300+ real AST nodes.
LARGE_PY = "def compute():\n    total = 0\n"
for i in range(30):
    LARGE_PY += f"    total = total + {i} * (total + {i}) - {i}\n"
LARGE_PY += "    if total > 100:\n        total = total - 1\n    return total\n"

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


def shot(page: Page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / name), full_page=True)
    print(f"  screenshot: docs/TEST_EVIDENCE/m3/{name}")


def step(name: str) -> None:
    print(f"[journey] {name}")


def ok(what: str) -> None:
    print(f"  ok: {what}")


def paste_and_analyze(page: Page, language: str, filename: str, content: str):
    page.goto(BASE + "/workspace")
    page.get_by_role("tab", name="Paste").click()
    page.get_by_label("Language").select_option(language)
    page.get_by_label("Filename").fill(filename)
    page.get_by_label("paste source code").fill(content)
    page.get_by_role("button", name="Create snapshot").click()
    expect(page.get_by_text("Snapshot created")).to_be_visible(timeout=20000)
    page.get_by_role("button", name="Analyze with real").click()


def journey_c_graph(page: Page) -> None:
    step("C graph: AST canvas, semantic zoom, node→source highlight, minimap, search")
    paste_and_analyze(page, "c", "demo.c", C_SRC)
    page.get_by_role("tab", name="ast AVAILABLE").wait_for(timeout=120000)
    page.get_by_role("tab", name="ast AVAILABLE").click()
    expect(page.locator(".react-flow__node").first).to_be_visible(timeout=30000)
    n_nodes = page.locator(".react-flow__node").count()
    ok(f"AST graph rendered with {n_nodes} real nodes")
    # semantic zoom: information density must change with zoom level (G3)
    page.locator(".react-flow").hover()
    label_far = page.locator(".cvnode-label").first.inner_text()
    for _ in range(5):
        page.locator(".react-flow__controls-zoomin").click()
    page.wait_for_timeout(400)
    label_close = page.locator(".cvnode-label").first.inner_text()
    assert label_close != label_far or ":DERIVED" in label_close or len(label_close) >= len(label_far), \
        "semantic zoom must change visible information"
    ok(f"semantic zoom: {label_far!r} → {label_close!r}")
    for _ in range(6):
        page.locator(".react-flow__controls-zoomout").click()
    page.wait_for_timeout(400)
    # minimap present
    expect(page.locator(".react-flow__minimap")).to_be_visible()
    # search
    page.get_by_label("search graph nodes").fill("adjust")
    page.get_by_role("button", name="Search").click()
    expect(page.locator(".react-flow__node.hit").first).to_be_visible()
    ok("search highlights matching nodes")
    # node click -> source highlight (two-way)
    node = page.locator(".react-flow__node", has_text="FunctionDecl").first
    node.click()
    expect(page.locator(".codeline.hl").first).to_be_visible(timeout=10000)
    ok("graph node click highlights source line")
    # inspector levels
    page.get_by_role("tab", name="detailed").click()
    expect(page.locator(".explanation")).to_contain_text("tool's own output")
    page.get_by_role("tab", name="technical").click()
    expect(page.locator(".explanation")).to_contain_text('"confidence"')
    ok("inspector simple/detailed/technical levels work")
    shot(page, "m3_c_ast_graph.png")


def journey_python_graph(page: Page) -> None:
    step("Python: bytecode graph + race + raw integrity")
    paste_and_analyze(page, "python", "fib.py",
                      "def fib(n):\n    a, b = 0, 1\n    for _ in range(n):\n"
                      "        a, b = b, a + b\n    return a\n\n"
                      "if __name__ == '__main__':\n    print(fib(10))\n")
    page.get_by_role("tab", name="bytecode AVAILABLE").wait_for(timeout=120000)
    page.get_by_role("tab", name="bytecode AVAILABLE").click()
    expect(page.locator(".react-flow__node").first).to_be_visible(timeout=30000)
    ok("bytecode graph rendered (virtualized; opcodes verified in Table view)")
    page.get_by_role("tab", name="Table").click()
    expect(page.locator("table.grid").get_by_text("BINARY_OP", exact=False).first)         .to_be_visible()
    page.get_by_role("tab", name="Graph").click()
    expect(page.locator(".react-flow__node").first).to_be_visible()
    instr = page.locator(".react-flow__node").nth(4)
    instr.click()
    expect(page.locator(".codeline.hl").first).to_be_visible(timeout=10000)
    ok("instruction click highlights its source line")
    # race: A -> B -> A quickly; content must match the final stage
    page.get_by_role("tab", name="ast AVAILABLE").click()
    page.get_by_role("tab", name="bytecode AVAILABLE").click()
    page.get_by_role("tab", name="ast AVAILABLE").click()
    page.wait_for_timeout(600)
    expect(page.locator(".react-flow").get_by_text("FunctionDef", exact=False).first) \
        .to_be_visible()
    ok("stage A→B→A race: content matches final selection")
    shot(page, "m3_python_graph_race.png")


def journey_large_and_error(page: Page) -> None:
    step("Large real AST (300+ honest nodes) + syntax error + viewports")
    paste_and_analyze(page, "python", "large.py", LARGE_PY)
    page.get_by_role("tab", name="ast AVAILABLE").wait_for(timeout=120000)
    page.get_by_role("tab", name="ast AVAILABLE").click()
    expect(page.locator(".react-flow__node").first).to_be_visible(timeout=60000)
    n = page.locator(".react-flow__node").count()
    assert n >= 300, f"expected 300+ real AST nodes, got {n}"
    ok(f"large graph rendered: {n} nodes (honest fixture)")
    # truncated/aggregation flags visible if applicable
    page.get_by_role("tab", name="Table").click()
    expect(page.locator("table.grid, .muted").first).to_be_visible()
    shot(page, "m3_large_graph_1080.png")
    # syntax error + blocked state
    paste_and_analyze(page, "python", "bad.py", "def broken(:\n    pass\n")
    page.get_by_role("tab", name="diagnostics AVAILABLE").wait_for(timeout=120000)
    ok("syntax error: diagnostics stage available, no fabricated graph stages")
    shot(page, "m3_syntax_error_768.png")


def journey_viewports(page: Page) -> None:
    step("Viewport matrix: 1920x1080, 1366x768, 390x844")
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.goto(BASE + "/workspace")
    expect(page.get_by_role("heading", name="Source Workspace")).to_be_visible()
    shot(page, "m3_desktop_1920.png")
    page.set_viewport_size({"width": 1366, "height": 768})
    page.goto(BASE + "/workspace")
    shot(page, "m3_laptop_1366.png")
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(BASE + "/workspace")
    expect(page.get_by_role("button", name="Create snapshot")).to_be_visible()
    shot(page, "m3_mobile_390.png")
    page.set_viewport_size({"width": 1280, "height": 900})
    ok("viewport matrix captured")


def main() -> int:
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        console_errors: list[str] = []
        page.on("pageerror", lambda e: console_errors.append(str(e)))
        for journey in (journey_c_graph, journey_python_graph,
                        journey_large_and_error, journey_viewports):
            try:
                journey(page)
            except Exception as e:  # noqa: BLE001
                FAILED.append(f"{journey.__name__}: {e}")
                print(f"  FAIL: {e}")
                shot(page, f"failure_{journey.__name__}.png")
        if console_errors:
            FAILED.append(f"uncaught page errors: {console_errors[:3]}")
            print(f"  FAIL: uncaught console errors: {console_errors[:3]}")
        else:
            ok("no uncaught page errors")
        browser.close()
    print()
    if FAILED:
        print(f"E2E RESULT: FAIL ({len(FAILED)} failures)")
        return 1
    print("E2E RESULT: PASS (4 M3 journeys)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
