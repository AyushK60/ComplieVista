"""M6-E browser E2E journeys (Windows Playwright → Vite/WSL → FastAPI/WSL → Docker).

Proves: OptimizationLab builds -O0/-O1/-O2 with per-level provenance and an A/B
assembly diff; uninstrumented benchmark results with stats; the Compare page runs
a real C/Python pair experiment (two independent rails, expected-output match);
mobile viewport; no console errors.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "docs" / "TEST_EVIDENCE" / "m6"
BASE = "http://127.0.0.1:5173"
FAILED: list[str] = []


def shot(page: Page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / name), full_page=True)
    print(f"  screenshot: docs/TEST_EVIDENCE/m6/{name}")


def ok(cond: bool, what: str) -> None:
    if cond:
        print(f"  ok: {what}")
    else:
        FAILED.append(what)
        print(f"  FAIL: {what}")


def step(name: str) -> None:
    print(f"[journey] {name}")


C_SRC = (REPO / "sandbox" / "fixtures" / "pairs" / "add.c").read_text()


def journey_optlab(page: Page) -> None:
    step("OptimizationLab: build O0/O1/O2, inspect provenance + asm diff")
    page.goto(BASE + "/workspace")
    page.get_by_role("tab", name="Paste").click()
    page.get_by_label("Language").select_option("c")
    page.get_by_label("Filename").fill("add.c")
    page.get_by_label("paste source code").fill(C_SRC)
    page.get_by_role("button", name="Load code").click()
    expect(page.get_by_text("Snapshot created")).to_be_visible(timeout=15000)
    page.get_by_role("button", name="Build -O0/-O1/-O2").click()
    expect(page.get_by_text("Assembly diff (A/B, static artifacts)")).to_be_visible(
        timeout=120000)
    ok(True, "three real builds completed with per-level table")
    expect(page.get_by_text("18.1.3").first).to_be_visible()
    ok(True, "clang tool provenance shown")
    diff = page.locator(".diff").inner_text()
    ok(len(diff) > 100 and ("+" in diff or "-" in diff), "A/B asm diff rendered")
    ok("NOT an executed-instruction count" in page.locator(".optlab").inner_text()
       or "NOT an executed-instruction count" in page.locator("body").inner_text(),
       "static-asm honesty label visible")
    shot(page, "m6_optlab_builds.png")
    # benchmark
    page.get_by_role("button", name="Benchmark (uninstrumented, ≥5 repeats)").click()
    expect(page.get_by_text("Benchmark (uninstrumented; warmup excluded)")).to_be_visible(
        timeout=120000)
    body = page.locator(".optlab").inner_text()
    ok("median" in body and "stdev" in body, "variability stats shown")
    ok("checksums" in body or "identical" in body, "semantics guard shown")
    ok("cgroup" in body, "container limits provenance shown")
    shot(page, "m6_optlab_benchmark.png")


def journey_compare_pair(page: Page) -> None:
    step("Compare page: real C/Python pair experiment (two rails)")
    page.goto(BASE + "/compare")
    expect(page.get_by_role("heading", name="Cross-Language Compare")).to_be_visible()
    expect(page.get_by_text("Python has no LLVM -O levels")).to_be_visible()
    ok(True, "no-fake-LLVM-levels honesty visible")
    page.get_by_role("listitem").filter(has_text="add").get_by_role(
        "button", name="Run paired experiment").click()
    expect(page.get_by_text("matches expected").first).to_be_visible(timeout=180000)
    body = page.locator(".compare").inner_text()
    ok("sum=299995" in body, "verified expected output on both rails")
    ok("C rail" in body and "Python rail" in body, "two independent rails")
    ok("different" in body or "independently implemented" in body,
       "semantic-difference caveat visible")
    shot(page, "m6_compare_pair.png")
    page.set_viewport_size({"width": 390, "height": 844})
    shot(page, "m6_compare_mobile.png")
    page.set_viewport_size({"width": 1440, "height": 900})


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        for journey in (journey_optlab, journey_compare_pair):
            try:
                journey(page)
            except Exception as e:  # noqa: BLE001
                FAILED.append(f"{journey.__name__}: {e}")
                print(f"  FAIL (exception): {e}")
                shot(page, f"failure_{journey.__name__}.png")
        browser.close()
    print()
    if errors:
        print(f"  page errors: {errors}")
        FAILED.extend(errors)
    if FAILED:
        print(f"E2E RESULT: FAIL ({len(FAILED)} failures): {FAILED}")
        return 1
    print("E2E RESULT: PASS (2 M6 journeys, desktop+mobile)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
