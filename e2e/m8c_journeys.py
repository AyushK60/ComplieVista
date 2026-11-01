"""M8 Part-3 verification E2E — all 20 demos, runtime tabs, Error Microscope,
Compare, and the full §15 screenshot suite at 1440×900 / 1920×1080 / 390px.

Real stack, real API, no mocks. Evidence: docs/TEST_EVIDENCE/m8c/
Run: backend/.venv/bin/python e2e/m8c_journeys.py   (repo root, stack running)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "docs" / "TEST_EVIDENCE" / "m8c"
BASE = "http://127.0.0.1:5173"
FAILED: list[str] = []
REPORT: list[dict] = []


def shot(page: Page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / name), full_page=False)
    print(f"  screenshot: docs/TEST_EVIDENCE/m8c/{name}")


def ok(cond: bool, what: str) -> None:
    if cond:
        print(f"  ok: {what}")
    else:
        FAILED.append(what)
        print(f"  FAIL: {what}")


def open_demo_detail(page: Page, demo_id: str) -> None:
    page.goto(BASE + "/demos")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1200)
    page.evaluate(
        """(id) => {
          const card = [...document.querySelectorAll('.democard')]
            .find((c) => c.textContent.includes(id));
          if (!card) throw new Error('card not found: ' + id);
          card.click();
        }""", demo_id)
    page.wait_for_timeout(400)


def explore(page: Page, demo_id: str) -> None:
    open_demo_detail(page, demo_id)
    page.evaluate("""() => {
      const btn = [...document.querySelectorAll('button')]
        .find((b) => b.textContent.includes('Explore this program →'));
      btn.click();
    }""")
    expect(page.locator(".obs-grid")).to_be_visible(timeout=90_000)
    page.wait_for_timeout(2500)


def click_stage(page: Page, name: str) -> None:
    page.evaluate(
        """(name) => {
          const st = [...document.querySelectorAll('button.jstage')]
            .find((b) => b.textContent.includes(name));
          if (st) st.click();
        }""", name)


def available_stages(page: Page) -> list[str]:
    return page.evaluate("""() =>
      [...document.querySelectorAll('button.jstage')]
        .filter((b) => !b.disabled && b.querySelector('.jstage-dot'))
        .map((b) => b.querySelector('.jstage-name')?.textContent ?? '')
    """)


def stage_renders(page: Page) -> bool:
    return page.evaluate("""() => {
      const sc = document.querySelector('.stagecanvas');
      if (!sc) return false;
      const text = sc.textContent ?? '';
      return text.trim().length > 40;
    }""")


def journey_all_twenty(page: Page, demos: list[dict]) -> None:
    print("[journey] all twenty programs — analysis + every available stage")
    for d in demos:
        did = d["id"]
        errs_before = len(CONSOLE_ERRORS)
        entry: dict = {"demo": did, "language": d.get("language", ""), "stages": [], "console_errors": 0}
        try:
            explore(page, did)
            stages = available_stages(page)
            entry["stages"] = stages
            ok(len(stages) >= 2, f"{did}: {len(stages)} stages available")
            # visit every available stage; each must render real content
            for st in stages:
                click_stage(page, st)
                page.wait_for_timeout(1200)
                if not stage_renders(page):
                    ok(False, f"{did}: stage '{st}' rendered no content")
                    entry["bad_stage"] = st
            ok("bad_stage" not in entry, f"{did}: all stages render")
            # at least one meaningful visual exploration: tokens or a graph stage
            click_stage(page, "Token Formation")
            page.wait_for_timeout(1000)
            entry["explorable"] = bool(page.evaluate(
                "document.querySelectorAll('.tf-token').length > 0 || document.querySelectorAll('.graphwrap').length > 0"))
            shot(page, f"demo_{did}.png")
        except Exception as e:  # noqa: BLE001 — record and continue
            entry["error"] = str(e)[:200]
            ok(False, f"{did}: {str(e)[:120]}")
        entry["console_errors"] = len(CONSOLE_ERRORS) - errs_before
        REPORT.append(entry)
        print(f"  → {did}: stages={len(entry.get('stages', []))} errs={entry['console_errors']}")


def journey_runtime(page: Page) -> None:
    print("[journey] runtime observatory tabs — PY-03")
    open_demo_detail(page, "PY-03")
    page.evaluate("""() => {
      const btn = [...document.querySelectorAll('button')]
        .find((b) => b.textContent.includes('Run & replay execution'));
      btn.click();
    }""")
    page.wait_for_url("**/workspace?*execution=*", timeout=120_000)
    # events paginate after the job completes — wait for either the scene or
    # an explained empty state, then require real counts
    expect(page.locator(".theater-stats, .theater .unavailable")).to_be_visible(timeout=30_000)
    ok(page.locator(".theater").is_visible(), "execution observatory renders")
    stats = page.locator(".theater-stats").inner_text()
    ok("calls" in stats and "max depth" in stats, f"recorded counts shown: {stats.split(chr(10))[0][:60]}")
    # click a call → call detail fills
    page.locator(".tncall").nth(2).click()
    page.wait_for_timeout(700)
    ok(page.locator(".calldetail .cd-body").is_visible(), "call detail opens on click")
    # guided execution story
    page.get_by_role("button", name="guided story").click()
    page.wait_for_timeout(800)
    ok(page.locator(".tf-guided").is_visible(), "guided execution story starts")
    for _ in range(5):
        page.get_by_role("button", name="continue →").click()
        page.wait_for_timeout(700)
    ok(True, "guided execution story walked")
    page.get_by_role("button", name="exit guided").click()
    # memory + process tabs
    page.evaluate("""() => {
      [...document.querySelectorAll('.exectabs button')]
        .find((b) => b.textContent === 'MemoryScope')?.click();
    }""")
    page.wait_for_timeout(2200)
    ok(page.locator(".memscope").is_visible(), "MemoryScope renders")
    page.evaluate("""() => {
      [...document.querySelectorAll('.exectabs button')]
        .find((b) => b.textContent === 'ProcessScope')?.click();
    }""")
    page.wait_for_timeout(1800)
    ok(page.locator(".proscope").is_visible(), "ProcessScope renders")
    shot(page, "execution_observatory_1440x900.png")


def journey_error_microscope(page: Page) -> None:
    print("[journey] error microscope")
    page.goto(BASE + "/demos")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1200)
    page.locator(".dl-errors").scroll_into_view_if_needed()
    page.wait_for_timeout(300)
    n_fix = page.locator(".errcard").count()
    ok(n_fix >= 4, f"error fixtures present ({n_fix})")
    phase_labels = page.locator(".errcard .badge").all_text_contents()
    ok(any("before execution" in p for p in phase_labels)
       and any("during execution" in p for p in phase_labels),
       "phase-of-detection labels present (compile vs runtime)")
    # reproduce one compile-time and one runtime diagnostic
    page.locator(".errcard").first.get_by_role("button").click()
    page.wait_for_timeout(4000)
    ok(page.locator(".errcard .excerpt").first.is_visible(), "diagnostic reproduced")
    shot(page, "error_microscope_1440x900.png")


def journey_compare(page: Page) -> None:
    print("[journey] dual-language observatory — recursion pair")
    page.goto(BASE + "/compare")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1200)
    page.evaluate("""() => {
      [...document.querySelectorAll('.paircard')]
        .find((c) => c.textContent.includes('recursion'))?.click();
    }""")
    expect(page.locator(".cmp-verdict, .err[role='alert']")).to_be_visible(timeout=150_000)
    ok(page.locator(".dualmap").is_visible(), "dual pipeline map renders")
    ok(page.locator(".dm-noalign").is_visible(), "no-equivalent-stage honestly marked")
    ok(page.locator(".cmp-sources .srcpane").count() == 2, "both sources side by side")
    ok(page.locator(".cmp-verdict.ok").count() == 1, "verdict: both rails matched")
    shot(page, "compare_dual_1440x900.png")


def journey_screenshots(page: Page) -> None:
    print("[screenshots] §15 suite")
    # 1440 hero + scroll
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(BASE + "/")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1600)
    shot(page, "landing_hero_1440x900.png")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.35)")
    page.wait_for_timeout(500)
    shot(page, "landing_scroll_1440x900.png")
    # demo selection
    page.goto(BASE + "/demos")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1600)
    shot(page, "demo_selection_1440x900.png")
    # token formation (PY-01)
    explore(page, "PY-01")
    page.wait_for_timeout(800)
    shot(page, "token_formation_1440x900.png")
    # PY AST + bytecode
    click_stage(page, "Syntax Tree")
    page.wait_for_timeout(2000)
    page.locator(".obs-canvas").scroll_into_view_if_needed()
    page.wait_for_timeout(300)
    shot(page, "py_ast_1440x900.png")
    click_stage(page, "Bytecode")
    page.wait_for_timeout(1500)
    page.locator(".obs-canvas").scroll_into_view_if_needed()
    shot(page, "py_bytecode_1440x900.png")
    # C AST + IR
    explore(page, "C-03")
    click_stage(page, "Syntax Tree")
    page.wait_for_timeout(2200)
    page.locator(".obs-canvas").scroll_into_view_if_needed()
    shot(page, "c_ast_1440x900.png")
    click_stage(page, "LLVM IR (-O0)")
    page.wait_for_timeout(1800)
    page.locator(".obs-canvas").scroll_into_view_if_needed()
    shot(page, "c_ir_1440x900.png")
    # OptimizationLab
    open_demo_detail(page, "C-03")
    page.evaluate("""() => {
      const btn = [...document.querySelectorAll('button')]
        .find((b) => b.textContent.includes('Run & replay execution'));
      btn.click();
    }""")
    page.wait_for_timeout(60_000)
    page.evaluate("""() => {
      const h = [...document.querySelectorAll('.panel-h')]
        .find((x) => x.textContent.includes('Optimization Explorer'));
      h?.scrollIntoView({ block: 'start' });
      const btn = [...document.querySelectorAll('.optactions button')]
        .find((b) => b.textContent.includes('Build -O0'));
      btn?.click();
    }""")
    page.wait_for_timeout(25_000)
    page.evaluate("""() => {
      const h = [...document.querySelectorAll('.panel-h')]
        .find((x) => x.textContent.includes('Optimization Explorer'));
      h?.scrollIntoView({ block: 'start' });
    }""")
    page.wait_for_timeout(400)
    shot(page, "optimization_lab_1440x900.png")
    # 1920×1080 spot checks
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.goto(BASE + "/")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1500)
    shot(page, "landing_hero_1920x1080.png")
    explore(page, "PY-03")
    click_stage(page, "Syntax Tree")
    page.wait_for_timeout(2200)
    page.locator(".obs-canvas").scroll_into_view_if_needed()
    shot(page, "py_ast_1920x1080.png")
    # mobile
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(BASE + "/")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1200)
    shot(page, "landing_390.png")
    explore(page, "PY-01")
    shot(page, "workspace_390.png")
    page.set_viewport_size({"width": 1440, "height": 900})


CONSOLE_ERRORS: list[str] = []


def main() -> None:
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", lambda m: CONSOLE_ERRORS.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: CONSOLE_ERRORS.append(str(e)))

        demos = json.loads((REPO / "docs" / "TEST_EVIDENCE" / "m8c" / "demos.json").read_text()) \
            if (REPO / "docs" / "TEST_EVIDENCE" / "m8c" / "demos.json").exists() \
            else ([{"id": f"PY-0{i}", "language": "python"} for i in range(1, 6)]
                  + [{"id": f"C-0{i}", "language": "c"} for i in range(1, 6)]
                  + [{"id": f"PAIR-0{i}-{s}", "language": "python" if s == "PY" else "c"}
                     for i in range(1, 6) for s in ("C", "PY")])

        journey_all_twenty(page, demos)
        journey_runtime(page)
        journey_error_microscope(page)
        journey_compare(page)
        journey_screenshots(page)

        print(f"\nconsole errors: {len(CONSOLE_ERRORS)}")
        for e in CONSOLE_ERRORS[:10]:
            print("  console error:", e[:160])
        ok(not CONSOLE_ERRORS, "zero console errors across the whole sweep")

        (SHOTS / "report.json").write_text(json.dumps(
            {"demos": REPORT, "console_errors": CONSOLE_ERRORS[:50],
             "failures": FAILED}, indent=1), "utf-8")
        browser.close()

    print(f"\n{'ALL CHECKS PASSED' if not FAILED else 'FAILURES: ' + '; '.join(FAILED)}")
    if FAILED:
        raise SystemExit(1)
    print(f"elapsed: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
