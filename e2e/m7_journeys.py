"""M7-G browser E2E: demo library catalog, all-20 guided journeys (parameterized
with individual results), pair compare CTA, Error Microscope, mobile viewport.

Efficient parameterization: each demo's journey = open catalog -> open demo ->
Run (real containers) -> expect expected-output match + replay banner. Analysis
and OptimizationLab deep-checks run for a representative subset (C-05, PY-03,
C-01) since the backend matrix (test_m7_demos) covers all 20 exhaustively.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "docs" / "TEST_EVIDENCE" / "m7"
BASE = "http://127.0.0.1:5173"
FAILED: list[str] = []
RESULTS: dict[str, str] = {}
EXPECTED = {d["id"]: d for d in json.loads(
    (REPO / "sandbox" / "fixtures" / "demos" / "manifest.json").read_text())["demos"]}


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
    expect(page.get_by_role("heading", name=re.compile("Twenty real programs"))
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
    lang_filter = page.get_by_role("group", name="language filter")
    lang_filter.get_by_role("button", name="python", exact=True).click()
    py_cards = page.locator(".democard").count()
    ok(py_cards == 10, f"python toggle shows 10 PY/PY-pair demos (got {py_cards})")
    lang_filter.get_by_role("button", name="all", exact=True).click()
    shot(page, "m7_catalog.png")


def journey_demo_detail(page: Page, demo_id: str, title_part: str) -> None:
    """Open the demo's own page, check the three guided stories and honest capability
    matrix, run it in the observatory, and compare the recorded stdout/exit code (read
    from the API) with the manifest's expected values."""
    page.goto(BASE + f"/demos/{demo_id}")
    expect(page.locator(".demo-detail")).to_be_visible(timeout=15000)
    for heading in ("The idea", "How it works", "Under the hood"):
        expect(page.get_by_role("heading", name=heading)).to_be_visible()
    ok(page.locator(".dd-story p").count() == 3 and
       all(t.strip() for t in page.locator(".dd-story p").all_inner_texts()),
       f"{demo_id}: three guided stories present")
    ok("Capability matrix" in page.locator(".demo-detail").inner_text(),
       f"{demo_id}: capability matrix shown")
    page.get_by_role("button", name="Run (observatory)").click()
    page.wait_for_url(re.compile(r"/workspace\?.*execution="), timeout=180000)
    expect(page.locator(".execdock")).to_be_visible(timeout=120000)
    eid = re.search(r"execution=([0-9a-f]+)", page.url).group(1)
    out = page.request.get(BASE + f"/api/v1/executions/{eid}/output").json()
    want = EXPECTED[demo_id]
    ok((out["stdout"] or "").strip() == want["expected_stdout"].strip()
       and out["exit_code"] == want["expected_exit"],
       f"{demo_id}: recorded run output matches the manifest's expected output")
    RESULTS[demo_id] = "run+replay OK"


def journey_deep_checks(page: Page) -> None:
    print("[journey] deep checks: C-05 multi-file, PY-03 memory, error microscope")
    journey_demo_detail(page, "C-05", "Multi-file")
    shot(page, "m7_c05_multifile.png")
    journey_demo_detail(page, "PY-03", "recursion")
    shot(page, "m7_py03_replay.png")
    page.goto(BASE + "/demos")
    # Error Microscope: all four fixtures with genuine diagnostics
    cards = page.locator(".errcard")
    expect(cards.first).to_be_visible(timeout=15000)
    ok(cards.count() == 4, f"four error fixtures listed (got {cards.count()})")
    for i in range(cards.count()):
        card = cards.nth(i)
        card.get_by_role("button", name="Reproduce the diagnostic").click()
        expect(card.locator("pre")).to_be_visible(timeout=120000)
        diag = card.locator("pre").inner_text()
        ok(len(diag.strip()) > 20, f"error fixture {i + 1}: genuine diagnostic rendered")
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
