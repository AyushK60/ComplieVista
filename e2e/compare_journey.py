#!/usr/bin/env python3
"""Compare page E2E (run from the repo root with the stack up): clicking "Run both pipelines" must lock
the cards while the comparison is in flight, scroll to it, show live progress, then show both rails'
real output; a second click on the same pair is served from this visit's cache; Run again re-runs it.
Real UI, real backend, real containers; nothing is mocked."""
from __future__ import annotations

import re
import sys

from playwright.sync_api import expect, sync_playwright

BASE = "http://127.0.0.1:5173"
FAIL: list[str] = []


def ok(cond: bool, msg: str) -> None:
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAIL.append(msg)


def main() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1440, "height": 900})
        page.goto(BASE + "/compare")
        cards = page.locator(".paircard")
        expect(cards.first).to_be_visible(timeout=15000)
        ok(cards.count() == 5, "five matched pairs are offered")
        ok(page.locator(".paircard .dth").count() >= 10, "each pair shows the real C and Python frames")

        cards.nth(0).click()
        progress = page.locator(".cmp-progress")
        expect(progress).to_be_visible(timeout=15000)
        ok(all(c.is_disabled() for c in cards.all()), "every card is locked while a comparison is in flight")
        page.wait_for_timeout(1500)  # smooth scrolling takes a moment
        ok(page.evaluate("window.scrollY") > 300, "the page scrolled down to the comparison")
        t1 = progress.inner_text()
        page.wait_for_timeout(2500)
        ok(progress.inner_text() != t1 or "s" in progress.inner_text(), "the progress line keeps counting")
        ok(progress.get_by_role("button", name="Cancel").is_visible(), "a Cancel button is offered")

        verdict = page.locator(".cmp-verdict")
        expect(verdict).to_be_visible(timeout=240000)
        ok("both rails produced the expected output" in verdict.inner_text(), "the verdict says both rails matched")
        rails = page.locator(".rail.panel")
        ok(rails.count() == 2, "both rails are shown")
        ok("sum=299995" in page.locator(".cmp-grid").inner_text(), "the real program output is shown (sum=299995)")
        ok(all(not c.is_disabled() for c in cards.all()), "cards unlock when the comparison ends")

        # the same pair again: instant, from this visit's cache
        page.evaluate("window.scrollTo(0, 0)")
        cards.nth(0).click()
        expect(verdict).to_be_visible(timeout=3000)
        ok(page.locator(".cmp-progress").count() == 0, "reopening a finished pair needs no new run")

        # cancel a fresh run
        cards.nth(1).click()
        expect(page.locator(".cmp-progress")).to_be_visible(timeout=15000)
        page.locator(".cmp-progress").get_by_role("button", name="Cancel").click()
        expect(page.locator(".cmp-progress")).to_have_count(0, timeout=5000)
        ok(all(not c.is_disabled() for c in cards.all()), "cancelling unlocks the cards")
        b.close()
    print()
    if FAIL:
        print(f"E2E RESULT: FAIL ({len(FAIL)}): {FAIL}")
        return 1
    print("E2E RESULT: PASS (compare)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
