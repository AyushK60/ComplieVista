"""Stage 8-G0 browser E2E: F-M7-01 trace trust badges + F-M7-05 Demo Library error
recovery with Retry. Real API throughout; the ONLY interception is the
temporary network-level failure injected for the recovery test, which is then
removed so Retry exercises the live API (no static fake replacement)."""
from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "e2e" / "screenshots" / "m8g0"
BASE = "http://127.0.0.1:5173"
FAILED: list[str] = []


def shot(page: Page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / name), full_page=True)
    print(f"  screenshot: e2e/screenshots/m8g0/{name}")


def ok(cond: bool, what: str) -> None:
    if cond:
        print(f"  ok: {what}")
    else:
        FAILED.append(what)
        print(f"  FAIL: {what}")


def journey_catalog_recovery(page: Page) -> None:
    """F-M7-05: a failing demos API must NOT replace the page with an error;
    navigation stays, Retry appears, and Retry against the restored live API
    recovers the real catalog."""
    print("[journey] Demo Library API failure -> Retry -> live recovery")
    aborted = {"on": True}

    def fail_demos(route):
        if aborted["on"]:
            route.abort()
        else:
            route.continue_()

    page.route("**/api/v1/demos**", fail_demos)
    page.goto(BASE + "/demos")
    expect(page.get_by_role("heading", name=re.compile("Twenty real programs"))
           ).to_be_visible()
    banner = page.get_by_role("alert").filter(has_text="demo catalog could not be loaded")
    expect(banner.first).to_be_visible(timeout=15000)
    ok(True, "error state shown instead of the catalog")
    # The page chrome survives: nav, heading, search box and error fixtures zone.
    ok(page.get_by_label("search demos").count() == 1, "navigation/search still present")
    ok(page.get_by_role("heading", name="Error Microscope").count() == 1,
       "Error Microscope section still present")
    retry_btn = page.get_by_role("button", name="Retry loading the demo catalog")
    ok(retry_btn.count() == 1, "accessible Retry control present")
    shot(page, "m8g0_demos_api_failure.png")

    aborted["on"] = False  # restore the live API
    retry_btn.click()
    expect(page.locator(".democard").first).to_be_visible(timeout=20000)
    n = page.locator(".democard").count()
    ok(n == 20, f"Retry recovers the live catalog with 20 real demos (got {n})")
    ok(page.get_by_role("alert").filter(has_text="demo catalog could not be loaded")
       .count() == 0, "error banner cleared after recovery")
    shot(page, "m8g0_demos_recovered.png")
    page.unroute("**/api/v1/demos**")


def journey_trace_trust_badges(page: Page) -> None:
    """F-M7-01: pasted (untrusted) runs show the honest UNTRUSTED_TARGET warning;
    curated demo runs show CURATED_COOPERATIVE."""
    print("[journey] trace trust badges (untrusted paste vs curated demo)")
    page.goto(BASE + "/workspace")
    page.get_by_role("tab", name="Paste").click()
    page.get_by_label("Language").select_option("python")
    page.get_by_label("Filename").fill("m8g0_trust.py")
    page.get_by_label("paste source code").fill(
        "def main():\n    print('trust probe')\n    return 5\n\n"
        "if __name__ == '__main__':\n    main()\n")
    page.get_by_role("button", name="Load code").click()
    expect(page.get_by_role("list", name="snapshot files")).to_be_visible(timeout=15000)
    page.get_by_role("button", name="Run in restricted container").click()
    expect(page.locator(".execdock")).to_be_visible(timeout=60000)
    warning = page.get_by_role("note", name="trace trust warning")
    expect(warning).to_be_visible(timeout=60000)
    ok("untrusted" in warning.inner_text().lower()
       and page.locator(".badge", has_text="Untrusted program").count() >= 1,
       "pasted run labeled UNTRUSTED_TARGET with the honest warning")
    shot(page, "m8g0_trace_trust_untrusted.png")

    page.goto(BASE + "/demos/PY-03")
    page.get_by_role("button", name="Run (observatory)").click()
    expect(page.locator(".execdock")).to_be_visible(timeout=90000)
    trust_badge = page.locator(".badge", has_text="Trusted trace")
    expect(trust_badge.first).to_be_visible(timeout=60000)
    ok(page.get_by_role("note", name="trace trust warning").count() == 0,
       "curated demo run labeled trusted, with no untrusted warning")
    shot(page, "m8g0_trace_trust_curated.png")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        for journey in (journey_catalog_recovery, journey_trace_trust_badges):
            try:
                journey(page)
            except Exception as e:  # noqa: BLE001
                FAILED.append(f"{journey.__name__}: {type(e).__name__}: {e}")
                print(f"  FAIL: {journey.__name__} raised {e}")
        browser.close()
    print()
    if FAILED:
        print(f"Stage 8 gate E2E: {len(FAILED)} FAILED checks:")
        for f in FAILED:
            print(f"  - {f}")
        return 1
    print("Stage 8 gate E2E: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
