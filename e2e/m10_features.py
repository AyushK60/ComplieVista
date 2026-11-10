"""Browser journeys for the Stage B/C features on the current UI:
  - CodeMirror editor accepts pasted code (same accessible name as before)
  - recent sessions list appears after a snapshot was opened
  - Optimization lab: source <-> IR <-> asm links, -O0 vs -O2 table (dead local has no code at -O2)
  - replay file download is a self-contained HTML file whose embedded data matches the program
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "docs" / "TEST_EVIDENCE" / "m10"
BASE = "http://127.0.0.1:5173"
FAILED: list[str] = []
C_SRC = (REPO / "backend" / "tests" / "fixtures" / "linemap" / "demo.c").read_text()
DEAD_LINE = 16  # `int unused = 42;` in demo.c


def shot(page: Page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / name), full_page=True)


def ok(what: str) -> None:
    print(f"  ok: {what}")


def load_c(page: Page) -> None:
    page.goto(BASE + "/workspace")
    page.get_by_role("tab", name="Paste").click()
    page.get_by_label("Language").select_option("c")
    page.get_by_label("Filename").fill("demo.c")
    editor = page.get_by_label("paste source code")
    expect(editor).to_be_visible(timeout=20000)
    editor.click()
    page.keyboard.press("Control+A")
    page.keyboard.insert_text(C_SRC)
    page.get_by_role("button", name="Load code").click()
    expect(page.get_by_role("list", name="snapshot files")).to_be_visible(timeout=20000)


def journey_editor_and_recent(page: Page) -> None:
    print("[journey] editor accepts code; recent sessions list")
    load_c(page)
    expect(page.locator(".sourceline").first).to_be_visible(timeout=20000)
    assert "sum_squares" in page.locator("main").inner_text()
    ok("pasted code through the CodeMirror editor reached the snapshot")
    page.goto(BASE + "/workspace")
    recent = page.get_by_role("region", name="recent sessions")
    expect(recent).to_be_visible(timeout=15000)
    ok("recent sessions list appears after a snapshot was opened")
    recent.get_by_role("link").first.click()
    expect(page.get_by_role("list", name="snapshot files")).to_be_visible(timeout=20000)
    ok("a recent session reopens its snapshot")


def journey_linking(page: Page) -> None:
    print("[journey] Optimization lab: source <-> IR <-> asm links and -O0/-O2 table")
    load_c(page)
    page.get_by_role("button", name=re.compile("^Analyze with")).click()
    page.get_by_role("tab", name="Optimization lab").click(timeout=120000)
    page.get_by_role("button", name=re.compile(r"Build -O0.*-O2")).click()
    link = page.locator(".slv")
    expect(link).to_be_visible(timeout=240000)
    expect(link.get_by_label("source").locator(".slv-row").first).to_be_visible(timeout=60000)
    # click source line 4 (`return x * x;`) -> IR and asm rows highlighted
    link.get_by_label("level for line links").select_option("O0")
    link.get_by_label("source").locator(".slv-row").nth(3).click()
    expect(link.get_by_label("LLVM IR").locator(".slv-row.hit").first).to_be_visible(timeout=15000)
    expect(link.get_by_label("assembly").locator(".slv-row.hit").first).to_be_visible(timeout=15000)
    ok("clicking a source line highlights its IR and assembly instructions")
    # dead local: has code at -O0, none at -O2, and the table says so
    row = link.get_by_label("per-line comparison").locator("tr", has=page.locator(f"td:text-is('{DEAD_LINE}')"))
    expect(row).to_contain_text("no code at -O2", timeout=15000)
    ok("the table reports the dead local as having no code at -O2")
    link.get_by_label("level for line links").select_option("O2")
    link.get_by_label("source").locator(".slv-row").nth(DEAD_LINE - 1).click()
    expect(link).to_contain_text(f"Source line {DEAD_LINE} has no code at O2")
    ok("selecting that line at -O2 says nothing was emitted for it")
    shot(page, "source_links.png")


def journey_replay_download(page: Page) -> None:
    print("[journey] replay file download")
    load_c(page)
    page.get_by_role("button", name="Run in restricted container").click()
    expect(page.locator(".execdock")).to_be_visible(timeout=120000)
    with page.expect_download(timeout=60000) as dl:
        page.get_by_role("link", name=re.compile("Replay file")).click()
    path = dl.value.path()
    html = Path(path).read_text(encoding="utf-8")
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    assert m, "no embedded data"
    data = json.loads(m.group(1))
    assert data["source"] == C_SRC
    assert data["output"]["stdout"].strip() == "285"      # 0+1+4+...+81
    assert not re.search(r'(src|href)\s*=\s*["\']https?:', html)
    ok("downloaded replay is self-contained and matches the program and its output")
    shot(page, "replay_button.png")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        for journey in (journey_editor_and_recent, journey_linking, journey_replay_download):
            try:
                journey(page)
            except Exception as e:  # noqa: BLE001
                FAILED.append(f"{journey.__name__}: {str(e)[:900]}")
                print(f"  FAIL: {journey.__name__}: {str(e)[:900]}")
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
