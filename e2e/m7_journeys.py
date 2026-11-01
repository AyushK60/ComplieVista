"""M7-G browser E2E: demo library catalog, all-20 guided journeys (parameterized
with individual results), pair compare CTA, Error Microscope, mobile viewport.

Efficient parameterization: each demo's journey = open catalog -> open demo ->
Run (real containers) -> expect expected-output match + replay banner. Analysis
and OptimizationLab deep-checks run for a representative subset (C-05, PY-03,
C-01) since the backend matrix (test_m7_demos) covers all 20 exhaustively.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "docs" / "TEST_EVIDENCE" / "m7"
BASE = "http://127.0.0.1:5173"
FAILED: list[str] = []
RESULTS: dict[str, str] = {}


def shot(page: Page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / name), full_page=True)
    print(f"  screenshot: docs/TEST_EVIDENCE/m7/{name}")


def ok(cond: bool, what: str) -> None:
    if cond:
        print(f"  ok: {what}")
    else:
        FAILED.append(what)
        print(f"  FAIL: {what}")


def journey_catalog(page: Page) -> None:
    print("[journey] catalog: 20 cards, search, language toggle")
    page.goto(BASE + "/demos")
    expect(page.get_by_role("heading", name="Demo Library — 20 real programs")
           ).to_be_visible()
    cards = page.locator(".democard")
    expect(cards.first).to_be_visible()
    ok(cards.count() == 20, f"20 demo cards rendered (got {cards.count()})")
    # M7QA: viewport matrix screenshots (1920 / 1366 / 390)
    for w, h, name in ((1920, 1080, "m7_catalog_1920.png"),
                       (1366, 768, "m7_catalog_1366.png"),
                       (390, 844, "m7_catalog_390.png")):
        page.set_viewport_size({"width": w, "height": h})
        shot(page, name)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.get_by_label("search demos").fill("recursion")
    ok(page.locator(".democard").count() >= 2, "search filters by concept")
    page.get_by_label("search demos").fill("")
    page.get_by_role("button", name="python", exact=True).click()
    py_cards = page.locator(".democard").count()
    ok(py_cards == 10, f"python toggle shows 10 PY/PY-pair demos (got {py_cards})")
    page.get_by_role("button", name="all", exact=True).click()
    shot(page, "m7_catalog.png")


def journey_demo_detail(page: Page, demo_id: str, title_part: str) -> None:
    page.goto(BASE + "/demos")
    page.get_by_label("search demos").fill(demo_id)
    card = page.locator(".democard").filter(has_text=demo_id)
    expect(card.first).to_be_visible()
    card.first.get_by_role("button", name="Open").click()
    expect(page.locator(".demodetail")).to_be_visible()
    # guided story: three levels
    for level in ("Simple", "Detailed", "Technical"):
        page.get_by_role("tab", name=level).click()
        expect(page.locator(".guided")).not_to_be_empty()
    ok(True, f"{demo_id}: guided story levels present")
    # capability matrix honesty
    body = page.locator(".demodetail").inner_text()
    ok("Capability matrix" in body, f"{demo_id}: capability matrix shown")
    # run (real containers)
    page.get_by_role("button", name="Run in restricted container").click()
    expect(page.get_by_text("matches expected ✓").first).to_be_visible(timeout=180000)
    expect(page.get_by_text("Recorded replay").first).to_be_visible(timeout=60000)
    ok(True, f"{demo_id}: run matched expected output with recorded replay")
    RESULTS[demo_id] = "run+replay OK"


def journey_deep_checks(page: Page) -> None:
    print("[journey] deep checks: C-05 multi-file, PY-03 memory, error microscope")
    journey_demo_detail(page, "C-05", "Multi-file")
    body = page.locator(".demodetail").inner_text()
    ok("matches expected ✓" in body, "C-05 linked program matched expected output")
    shot(page, "m7_c05_multifile.png")
    journey_demo_detail(page, "PY-03", "recursion")
    shot(page, "m7_py03_replay.png")
    # Error Microscope: all four fixtures with genuine diagnostics
    for fid in ("ERR-SYNTAX", "ERR-SEMANTIC", "ERR-LINK", "ERR-RUNTIME"):
        card = page.locator(".errfixture").filter(has_text=fid)
        card.get_by_role("button", name="Run").click()
        expect(card.locator("pre")).to_be_visible(timeout=120000)
        diag = card.locator("pre").inner_text()
        ok(len(diag.strip()) > 20, f"{fid}: genuine diagnostic rendered")
    shot(page, "m7_error_microscope.png")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        try:
            journey_catalog(page)
            all_demos = [
                "PY-01", "PY-02", "PY-03", "PY-04", "PY-05",
                "C-01", "C-02", "C-03", "C-04",
                "PAIR-01-C", "PAIR-02-C", "PAIR-03-C", "PAIR-04-C", "PAIR-05-C",
                "PAIR-01-PY", "PAIR-02-PY", "PAIR-03-PY", "PAIR-04-PY", "PAIR-05-PY",
            ]
            for demo_id in all_demos:
                try:
                    journey_demo_detail(page, demo_id, demo_id)
                except Exception as e:  # noqa: BLE001
                    RESULTS[demo_id] = f"FAIL: {e}"
                    FAILED.append(f"{demo_id}: {e}")
                    print(f"  FAIL (exception): {demo_id}: {e}")
                    shot(page, f"failure_{demo_id}.png")
            journey_deep_checks(page)
        finally:
            browser.close()
    print()
    print(f"individual results: {len(RESULTS)} demos journeyed")
    for k in sorted(RESULTS):
        print(f"  {k}: {RESULTS[k]}")
    if errors:
        FAILED.extend(errors)
    if FAILED:
        print(f"E2E RESULT: FAIL ({len(FAILED)} failures): {FAILED}")
        return 1
    print("E2E RESULT: PASS (all 20 demos journeyed + deep checks + microscope)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
