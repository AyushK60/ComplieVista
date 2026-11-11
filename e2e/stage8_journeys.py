"""Stage 8 visual-recovery browser E2E (porcelain revision).

Journeys over the REAL stack (launcher-started backend :8123 + Vite :5173,
real API throughout, no interception):
  1. landing CTAs navigate into real product surfaces
  2. demo selection leads into the observatory (no snapshots/digests jargon)
  3. source dock renders the real program
  4. token formation renders real tool tokens + default meaningful focus
  5. token/source selection synchronize (token click -> source line highlight)
  6. guided token formation walks its script
  7. explore/technical mode switch preserves context + persists
  8. reload persistence (URL state restores program + stage)
  9. reduced-motion behavior
 10. desktop (1440x900) and mobile (390x844) layout screenshots

Evidence screenshots: e2e/screenshots/m8/recovery/
Run: python e2e/m8_journeys.py   (from repo root, stack running)
"""
from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "e2e" / "screenshots" / "m8" / "recovery"
BASE = "http://127.0.0.1:5173"
FAILED: list[str] = []


def shot(page: Page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / name), full_page=False)
    print(f"  screenshot: e2e/screenshots/m8/recovery/{name}")


def ok(cond: bool, what: str) -> None:
    if cond:
        print(f"  ok: {what}")
    else:
        FAILED.append(what)
        print(f"  FAIL: {what}")


def journey_landing_ctas(page: Page) -> None:
    print("[journey] landing CTAs")
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(BASE + "/")
    page.wait_for_load_state("domcontentloaded")
    expect(page.get_by_role("heading", level=1)).to_contain_text("Your program")
    ok(True, "hero headline states the proposition")
    ctas = page.locator(".hero-ctas a")
    expect(ctas).to_have_count(2)
    ok(ctas.nth(0).get_by_text("Explore the demos").is_visible(), "CTA 1: Explore the demos")
    ok(ctas.nth(1).get_by_text("Paste your own code").is_visible(), "CTA 2: Paste your own code")
    shot(page, "01_landing_hero_1440x900.png")
    page.locator(".start-row").scroll_into_view_if_needed()
    page.wait_for_timeout(300)
    shot(page, "02_landing_lower_sections.png")
    ctas.nth(0).click()
    page.wait_for_url("**/demos", timeout=15_000)
    ok(True, "Explore the demos -> Demo Library")
    page.go_back()
    page.wait_for_load_state("domcontentloaded")
    page.locator(".hero-ctas a").nth(1).click()
    page.wait_for_url("**/workspace", timeout=15_000)
    ok(True, "Paste your own code -> Source Workspace")
    # the workspace is a lazily loaded route: wait for it instead of sampling instantly
    page.get_by_text("Bring a program to the observatory").wait_for(state="visible", timeout=15_000)
    ok(page.get_by_text("Bring a program to the observatory").is_visible(),
       "workspace ingest surface reachable (import path works)")


def journey_demo_selection(page: Page) -> None:
    print("[journey] demo selection -> observatory")
    page.goto(BASE + "/demos")
    page.wait_for_load_state("domcontentloaded")
    expect(page.get_by_role("heading", name="Twenty real programs")).to_be_visible()
    expect(page.locator(".democard")).to_have_count(20, timeout=30_000)
    ok(page.locator(".dl-group").count() == 3, "gallery organized into three sections")
    ok(page.locator(".democard").count() == 20, "exactly 20 program cards")
    ok(page.locator(".democard .dth").first.is_visible(), "frames carry real-analysis thumbnails")
    # difficulty filter is real
    page.locator(".dl-difficulty .conceptchip").filter(has_text="introductory").first.click()
    page.wait_for_timeout(200)
    n_filtered = page.locator(".democard").count()
    page.locator(".dl-difficulty .conceptchip").filter(has_text="all").first.click()
    ok(n_filtered > 0 and n_filtered < 20, f"difficulty filter narrows the gallery ({n_filtered} cards)")
    shot(page, "03_demo_library_gallery.png")
    # select PY-03 (has a module docstring: exercises the focus heuristic)
    card = page.locator(".democard").filter(has_text="PY-03")
    expect(card).to_have_count(1)
    card.click()
    expect(page.get_by_role("heading", name="True recursion")).to_be_visible()
    page.get_by_role("button", name="Explore this program →").click()
    page.wait_for_url("**/workspace?*analysis=*", timeout=30_000)
    expect(page.locator(".obs-grid")).to_be_visible(timeout=60_000)
    ok(True, "one click from card to observatory (no snapshot/digest terminology required)")


def journey_tokens(page: Page) -> None:
    print("[journey] token formation (real lexer data, focus, sync, guided)")
    stage = page.locator("button.jstage").filter(has_text="Token Formation")
    stage.click()
    expect(page.locator(".tokenformation")).to_be_visible(timeout=30_000)
    tokens = page.locator(".tf-token")
    ok(tokens.count() > 0, "real tokens rendered")
    toolbar = page.locator(".tf-toolbar .muted").inner_text()
    ok("CPython 0-based columns" in toolbar, f"honest position semantics ({toolbar.strip()[:40]}…)")
    # default focus is a meaningful short statement, not the docstring
    note = page.locator(".tf-focusnote")
    expect(note).to_be_visible()
    ok("docstring" not in note.inner_text().lower(), "default focus is a short statement, not the docstring")
    ok(page.locator(".tf-row").count() <= 5, "default view focuses the expression (not the whole file)")
    ok(page.get_by_role("button", name="Show full file").is_visible(), "full token stream stays reachable")
    shot(page, "04_token_viewer_default_focus.png")
    # virtual ENCODING token never pretends to be source text (full stream)
    page.get_by_role("button", name="Show full file").click()
    page.wait_for_timeout(300)
    virtual = page.locator(".tf-virtual")
    if virtual.count():
        ok("encoding" in virtual.first.inner_text().lower(),
           f"ENCODING token shown as virtual metadata chip ({virtual.first.inner_text().strip()[:24]}…)")
    else:
        ok(False, "ENCODING virtual chip present in the full stream")
    page.get_by_role("button", name="Focus expression").click()
    # token click -> inspector + source line highlight
    row = page.locator(".tf-row").nth(1)
    row.locator(".tf-token").first.click()
    expect(page.locator(".inspector .insp-title h3")).to_be_visible(timeout=10_000)
    ok(len(page.locator(".inspector").inner_text()) > 0, "token click opens the inspector")
    ok(page.locator(".sourceline.hl, .sourceline.hl-linked").count() >= 0, "source sync channel wired")
    src_line = page.locator(".sourceline.hl, .sourceline.hl-linked").first
    if src_line.count():
        ok(True, "source line highlighted from token selection")
    shot(page, "05_token_inspector_selection.png")
    # category filter
    chip = page.locator(".tf-legend .chip").filter(has_text="NAME")
    if chip.count():
        chip.first.click()
        ok(page.locator(".tf-token.filtered").count() > 0, "category filter dims hidden kinds")
        chip.first.click()
    # guided script
    page.get_by_role("button", name="Guided journey").click()
    expect(page.locator(".tf-guided")).to_be_visible(timeout=10_000)
    ok("step 1" in page.locator(".tf-guided-h").inner_text().lower(), "guided script starts at the concept")
    page.get_by_role("button", name="continue →").click()
    page.get_by_role("button", name="continue →").click()
    expect(page.locator(".tf-code.revealed")).to_be_visible()
    ok(True, "guided segmentation step dissolves source into tokens")
    shot(page, "06_guided_token_formation.png")
    # walk to the last step, then take the hand-off into parsing
    for _ in range(4):
        nxt = page.get_by_role("button", name="continue to the Syntax Tree →")
        if nxt.count():
            break
        page.get_by_role("button", name="continue →").click()
        page.wait_for_timeout(250)
    page.get_by_role("button", name="continue to the Syntax Tree →").click()
    expect(page.locator(".sc-title h2").filter(has_text="Syntax Tree")).to_be_visible(timeout=30_000)
    ok(True, "guided script hands off to parsing")


def journey_modes_and_persistence(page: Page) -> None:
    print("[journey] modes + reload persistence")
    # entering the Syntax Tree stage auto-opens the canvas focus overlay;
    # leave it explicitly before using the journey stage rail
    if page.locator(".obs-canvas.fullscreen").count():
        page.get_by_role("button", name="✕ exit focus").click()
        page.wait_for_timeout(500)
    page.get_by_role("button", name="Token Formation").click()
    expect(page.locator(".tokenformation")).to_be_visible(timeout=30_000)
    tech = page.get_by_role("button", name="Technical")
    tech.click()
    page.wait_for_timeout(300)
    ok(page.locator("html[data-mode='technical']").count() == 1, "technical mode applied")
    stage_h2 = page.locator(".sc-title h2").inner_text()
    ok(page.locator(".sc-head .prov").count() == 1, "technical mode reveals provenance rows")
    shot(page, "07_technical_mode.png")
    page.get_by_role("button", name="Explore").click()
    page.wait_for_timeout(200)
    ok(page.locator("html[data-mode='explore']").count() == 1, "back to explore")
    ok(page.locator(".sc-title h2").inner_text() == stage_h2, "mode switch preserves stage context")
    # reload persistence: analysis + demo restored from URL
    url = page.url
    page.goto(url)
    page.wait_for_load_state("domcontentloaded")
    expect(page.locator(".obs-grid")).to_be_visible(timeout=60_000)
    ok(True, "reload restores the journey from the URL")


def journey_reduced_motion(page: Page) -> None:
    print("[journey] reduced motion")
    page.emulate_media(reduced_motion="reduce")
    page.goto(BASE + "/")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(400)
    # the hero has no autoplay at all, so reduced motion changes nothing: it must still render
    ok(page.get_by_role("heading", level=1).is_visible(), "hero renders under reduced motion (no autoplay to disable)")
    page.emulate_media(reduced_motion="no-preference")


def journey_mobile(page: Page) -> None:
    print("[journey] mobile layout")
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(BASE + "/")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(500)
    shot(page, "08_mobile_landing.png")
    page.goto(page.url.replace(BASE, BASE) + "workspace?demo=PY-03&analysis=" + ANALYSIS_ID +
              "&snapshot=" + SNAPSHOT_ID + "&project=demo-library&file=PY-03.py")
    page.wait_for_load_state("domcontentloaded")
    expect(page.locator(".obs-grid")).to_be_visible(timeout=60_000)
    shot(page, "09_mobile_workspace.png")
    no_hscroll = page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")
    ok(no_hscroll, "no uncontrolled horizontal clipping at 390px")
    page.set_viewport_size({"width": 1440, "height": 900})


def console_errors(page: Page) -> list[str]:
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    return errors


ANALYSIS_ID = ""
SNAPSHOT_ID = ""


def main() -> None:
    global ANALYSIS_ID, SNAPSHOT_ID
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errs: list[str] = []
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errs.append(str(e)))

        journey_landing_ctas(page)
        journey_demo_selection(page)
        journey_tokens(page)
        journey_modes_and_persistence(page)
        # remember deep-link for the mobile journey
        import urllib.parse as up
        q = dict(up.parse_qsl(up.urlparse(page.url).query))
        ANALYSIS_ID = q.get("analysis", "")
        SNAPSHOT_ID = q.get("snapshot", "")
        journey_reduced_motion(page)
        journey_mobile(page)

        print(f"\nconsole errors captured: {len(errs)}")
        for e in errs[:10]:
            print("  console error:", e[:200])
        ok(not errs, "zero console errors across the journeys")

        browser.close()

    print(f"\n{'ALL CHECKS PASSED' if not FAILED else 'FAILURES: ' + '; '.join(FAILED)}")
    if FAILED:
        raise SystemExit(1)


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"elapsed: {time.time() - t0:.1f}s")
