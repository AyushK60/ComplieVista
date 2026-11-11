#!/usr/bin/env python3
"""M11 browser E2E: design-rework features (run from repo root with the stack up).

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
    print("[journey] hero journey window -> workspace")
    page.goto(BASE + "/")
    expect(page.get_by_role("heading", name=re.compile("Your program"), level=1)).to_be_visible(timeout=15000)
    rail = page.locator(".jw-rail button")
    expect(rail.first).to_be_visible(timeout=60000)
    ok(rail.count() == 5, "the journey has five phases")
    rail.nth(1).click()
    expect(page.locator("[data-pane=tokens] .pl-token").first).to_be_visible(timeout=10000)
    lines = page.locator(".jw-src .pl-line")
    n = lines.count()
    ok(n >= 3, f"the window lists the source lines ({n})")
    lines.nth(0).click()
    first = page.locator("[data-pane=tokens] .pl-token").all_text_contents()
    lines.nth(n - 1).click()
    last = page.locator("[data-pane=tokens] .pl-token").all_text_contents()
    ok(first != last and len(first) > 0 and len(last) > 0, "selecting a different line changes its tokens")
    rail.nth(2).click()
    ok(page.locator("[data-pane=ast] .pl-nodes li").count() > 0, "the same line shows syntax nodes")
    rail.nth(3).click()
    ok(page.locator("[data-pane=bytecode] .pl-ins").count() > 0, "and its bytecode")
    rail.nth(4).click()
    expect(page.locator("[data-pane=run] .pl-steps li").first).to_be_visible(timeout=60000)
    ok("area=" in page.locator("[data-pane=run] .pl-stdout").inner_text(), "the execution phase shows a real recorded run and its output")
    rail.nth(3).click()
    page.get_by_role("link", name=re.compile("Open this stage in the workspace")).click()
    expect(page.get_by_role("navigation", name="compilation journey")).to_be_visible(timeout=60000)
    ok("stage=bytecode" in page.url, "the link opens the stage shown")
    expect(page.get_by_role("heading", name="Bytecode", level=2)).to_be_visible(timeout=20000)
    ok(True, "workspace is on the Bytecode stage")


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
    ok("76 / 76" in txt and "What it does not do" in txt, "About states the fidelity result and the limitations")


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
