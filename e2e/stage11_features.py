#!/usr/bin/env python3
"""Stage 11 browser E2E: design-rework features (run from repo root with the stack up).

Journeys: live hero -> Try it, command palette, theme toggle persistence, keyboard shortcuts,
guided tour (started on demand), About page facts. Real UI, real backend, nothing mocked.
"""
from __future__ import annotations

import re
import sys

from playwright.sync_api import Page, expect, sync_playwright

BASE = "http://127.0.0.1:5173"
FAIL: list[str] = []


def ok(cond: bool, msg: str) -> None:
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAIL.append(msg)


def journey_hero(page: Page) -> None:
    print("[journey] title sequence hero and recorded-data figures")
    page.goto(BASE + "/")
    expect(page.get_by_role("heading", name=re.compile("Your program"), level=1)).to_be_visible(timeout=15000)
    fig = page.locator(".ts")
    expect(fig).to_be_visible(timeout=15000)
    steps = fig.get_by_role("group", name="Show a step").get_by_role("button")
    ok(steps.count() == 3, "the title sequence offers three steps (source, tokens, syntax tree)")
    steps.nth(1).click()
    ok(fig.get_attribute("data-step") == "1", "pressing Tokens holds the token step")
    expect(fig.locator(".ts-kind").first).to_be_visible(timeout=5000)
    ok(fig.locator(".ts-kind").count() >= 4, "tokens show their recorded kinds")
    steps.nth(2).click()
    ok(fig.get_attribute("data-step") == "2", "pressing Syntax tree holds the tree step")
    ok("sha256" in fig.locator("figcaption").inner_text(), "the figure carries its source sha256")

    # the four stage figures are drawn from recorded data and carry provenance
    page.locator("#stage-01").scroll_into_view_if_needed()
    ok(page.locator("#stage-01 .fg-tokrows li").count() >= 3, "tokens figure lists source lines")
    page.locator("#stage-01").get_by_role("tab", name=re.compile("C . clang")).click()
    ok(page.locator("#stage-01 .fg-toks .tk").count() > 0, "the C tab shows clang's tokens")
    page.locator("#stage-02").scroll_into_view_if_needed()
    ok(page.locator("#stage-02 .fg-tree .node").count() >= 15, "syntax tree figure draws Clang's nodes")
    ok(page.locator("#stage-02 .fg-tree .node.implicit").count() >= 1, "implicit nodes are drawn dashed")
    page.locator("#stage-03").scroll_into_view_if_needed()
    for tab, needle in (("C . x86-64", "retq"), ("Python . bytecode", "LOAD_FAST")):
        page.locator("#stage-03").get_by_role("tab", name=re.compile(tab)).click()
        ok(needle in page.locator("#stage-03 .fg-list").inner_text(), f"the {tab} tab lists real instructions ({needle})")
    page.locator("#stage-04").scroll_into_view_if_needed()
    slider = page.locator("#stage-04 input[type=range]")
    slider.fill("20")
    ok("area=10" in page.locator("#stage-04 .fg-out").inner_text(), "the recorded run ends with its real output")
    for fig_id in ("#stage-01", "#stage-02", "#stage-03", "#stage-04"):
        ok("Recorded output" in page.locator(f"{fig_id} figcaption").first.inner_text(), f"{fig_id} labels itself as recorded output")

    # the reels show every stage, and the frame names stay readable when lit
    ok(page.locator(".strip").nth(0).locator(".frames li").count() == 8, "the C reel shows all eight stages")
    ok(page.locator(".strip").nth(1).locator(".frames li").count() == 6, "the Python reel shows all six stages")


def journey_palette(page: Page) -> None:
    print("[journey] command palette + shortcuts help")
    page.goto(BASE + "/demos")
    expect(page.locator(".democard").first).to_be_visible(timeout=15000)
    page.keyboard.press("Control+k")
    dlg = page.get_by_role("dialog", name="Command palette")
    expect(dlg).to_be_visible(timeout=5000)
    expect(page.get_by_label("Search commands")).to_be_focused(timeout=5000)
    page.keyboard.type("compare")
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(r"/compare$"), timeout=10000)
    ok(True, "palette navigates (Go to Compare)")
    page.keyboard.press("Control+k")
    expect(page.get_by_label("Search commands")).to_be_focused(timeout=5000)
    page.keyboard.type("PY-03")
    page.keyboard.press("Enter")
    expect(page).to_have_url(re.compile(r"/demos/PY-03$"), timeout=10000)
    ok(True, "palette opens a demo by id")
    page.keyboard.press("?")
    expect(page.get_by_role("dialog", name="Keyboard shortcuts")).to_be_visible(timeout=5000)
    page.keyboard.press("Escape")
    ok(page.get_by_role("dialog", name="Keyboard shortcuts").count() == 0, "? opens and Esc closes the shortcuts list")


def journey_theme(page: Page) -> None:
    print("[journey] theme toggle persists")
    page.goto(BASE + "/demos")
    before = page.evaluate("document.documentElement.dataset.theme")
    page.get_by_role("button", name=re.compile("Switch to (dark|light) theme")).click()
    after = page.evaluate("document.documentElement.dataset.theme")
    ok(before != after, f"theme toggles ({before} -> {after})")
    page.reload()
    ok(page.evaluate("document.documentElement.dataset.theme") == after, "theme survives a reload (no flash)")
    page.evaluate("localStorage.removeItem('cv.theme')")


def journey_workspace_keys(page: Page) -> None:
    print("[journey] workspace shortcuts, tour, status popover")
    page.goto(BASE + "/demos/PY-03")
    page.get_by_role("button", name="Run (observatory)").click()
    expect(page.locator(".execdock")).to_be_visible(timeout=120000)
    badge = page.locator(".statusbadge", has_text="Trusted trace")
    expect(badge).to_be_visible(timeout=20000)
    badge.get_by_role("button").click()
    expect(page.get_by_role("tooltip")).to_contain_text("curated program")
    ok(True, "status badge explains itself in plain language")
    page.keyboard.press("Escape")
    page.keyboard.press("2")
    views = page.get_by_role("tablist", name="workspace views")
    ok(views.get_by_role("tab", name="Execution observatory").get_attribute("aria-selected") == "true", "key 2 selects the second view")
    page.evaluate("window.dispatchEvent(new Event('cv:tour'))")
    tour = page.get_by_role("dialog", name="Guided tour")
    expect(tour).to_be_visible(timeout=5000)
    tour.get_by_role("button", name="Next").click()
    expect(tour).to_contain_text("Stages and views")
    tour.get_by_role("button", name="Close tour").click()
    ok(page.get_by_role("dialog", name="Guided tour").count() == 0, "tour opens on demand and closes")


def journey_about(page: Page) -> None:
    print("[journey] About / Method")
    page.goto(BASE + "/about")
    expect(page.get_by_role("heading", name=re.compile("Real artifacts"), level=1)).to_be_visible(timeout=10000)
    txt = page.locator("main").inner_text()
    # headings are set in capitals by CSS, and inner_text follows text-transform, so compare case-insensitively
    ok("76 / 76" in txt and "what it does not do" in txt.lower(), "About states the fidelity result and the limitations")


def main() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch()
        for fn in (journey_hero, journey_palette, journey_theme, journey_workspace_keys, journey_about):
            page = b.new_page(viewport={"width": 1440, "height": 900})
            try:
                fn(page)
            except Exception as e:  # noqa: BLE001
                FAIL.append(f"{fn.__name__}: {str(e)[:300]}")
                print(f"  FAIL {fn.__name__}: {str(e)[:300]}")
            page.close()
        b.close()
    print()
    if FAIL:
        print(f"E2E RESULT: FAIL ({len(FAIL)}): {FAIL}")
        return 1
    print("E2E RESULT: PASS (5 journeys)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
