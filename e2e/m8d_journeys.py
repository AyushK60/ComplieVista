"""Repair-phase browser journeys — the §7.4 list, adapted to shipped features.
Real stack, no mocks. Evidence: docs/TEST_EVIDENCE/m8d/
Run: backend/.venv/bin/python e2e/m8d_journeys.py   (repo root, stack running)
"""
from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "docs" / "TEST_EVIDENCE" / "m8d"
BASE = "http://127.0.0.1:5173"
FAILED: list[str] = []
CONSOLE_ERRORS: list[str] = []


def shot(page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / name), full_page=False)
    print(f"  screenshot: docs/TEST_EVIDENCE/m8d/{name}")


def ok(cond: bool, what: str) -> None:
    if cond:
        print(f"  ok: {what}")
    else:
        FAILED.append(what)
        print(f"  FAIL: {what}")


def open_demo(page, demo_id: str) -> None:
    page.goto(BASE + "/demos")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1200)
    page.evaluate(
        """(id) => {
          const card = [...document.querySelectorAll('.democard')]
            .find((c) => c.textContent.includes(id));
          if (!card) throw new Error('card missing ' + id);
          card.click();
        }""", demo_id)
    page.wait_for_timeout(400)


def explore(page, demo_id: str) -> None:
    open_demo(page, demo_id)
    page.evaluate("""() => {
      [...document.querySelectorAll('button')]
        .find((b) => b.textContent.includes('Explore this program →')).click();
    }""")
    expect(page.locator(".obs-app")).to_be_visible(timeout=90_000)
    page.wait_for_timeout(2500)


def click_stage(page, name: str) -> None:
    page.evaluate(
        """(name) => {
          [...document.querySelectorAll('button.jstage')]
            .find((b) => b.textContent.includes(name))?.click();
        }""", name)


def click_view(page, name: str) -> None:
    page.evaluate(
        """(name) => {
          [...document.querySelectorAll('.obs-viewtabs button')]
            .find((b) => b.textContent === name)?.click();
        }""", name)


def j1_landing_to_ast(page) -> None:
    print("[j1] landing → gallery → PY-01 → tokens → AST")
    page.goto(BASE + "/")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1200)
    page.evaluate("""() => {
      [...document.querySelectorAll('.hero-ctas a')]
        .find((a) => a.textContent.includes('Explore a Program')).click();
    }""")
    page.wait_for_url("**/demos", timeout=15_000)
    explore(page, "PY-01")
    ok(page.locator(".tokenformation").is_visible(), "tokens open by default")
    ok(not page.evaluate("document.documentElement.scrollHeight > document.documentElement.clientHeight + 40"),
       "workspace fits the viewport (no page scroll)")
    shot(page, "j1_tokens_1440.png")
    click_stage(page, "Syntax Tree")
    page.wait_for_timeout(2200)
    ok(page.locator(".graphwrap").is_visible(), "AST renders in the canvas column")
    ok(page.evaluate("document.querySelectorAll('.react-flow__edge').length > 0"), "edges rendered")
    shot(page, "j1_ast_1440.png")


def j2_walkthrough_loops(page) -> None:
    print("[j2] PY-02 → Watch This Program Work (loop story)")
    open_demo(page, "PY-02")
    page.evaluate("""() => {
      [...document.querySelectorAll('button')]
        .find((b) => b.textContent.includes('Watch This Program Work')).click();
    }""")
    page.wait_for_url("**/workspace?*walkthrough=1", timeout=120_000)
    expect(page.locator(".walkthrough")).to_be_visible(timeout=30_000)
    page.wait_for_timeout(3500)
    ok(page.locator(".wt-flow").is_visible(), "flow panel present")
    # advance and check the loop-pass counter appears when revisiting a line
    seen = False
    for _ in range(60):
        page.evaluate("""() => {
          [...document.querySelectorAll('.theater-controls .btn')]
            .find((b) => b.getAttribute('aria-label') === 'next meaningful event')?.click();
        }""")
        page.wait_for_timeout(120)
        if page.locator(".wt-flow .chip.partial").count() > 0:
            seen = True
            break
    ok(seen, "derived loop-pass counter appears while the loop runs (labeled)")
    shot(page, "j2_walkthrough_loop_1440.png")


def j3_recursion(page) -> None:
    print("[j3] PY-03 → walkthrough recursion + execution observatory")
    open_demo(page, "PY-03")
    page.evaluate("""() => {
      [...document.querySelectorAll('button')]
        .find((b) => b.textContent.includes('Watch This Program Work')).click();
    }""")
    page.wait_for_url("**/workspace?*walkthrough=1", timeout=120_000)
    expect(page.locator(".walkthrough .wt-vartable")).to_be_visible(timeout=30_000)
    page.wait_for_timeout(2000)
    ok(page.locator(".wt-stack .wt-frame").count() >= 1, "stack frames shown")
    shot(page, "j3_walkthrough_recursion_1440.png")
    click_view(page, "Execution observatory")
    expect(page.locator(".theater")).to_be_visible(timeout=30_000)
    ok(len(page.locator(".theater-stats").inner_text()) > 0, "call structure available")
    shot(page, "j3_execution_observatory_1440.png")


def j4_c_ir(page) -> None:
    print("[j4] C-01 → tokens → AST → LLVM IR")
    explore(page, "C-01")
    click_stage(page, "Syntax Tree")
    page.wait_for_timeout(2000)
    ok(page.locator(".graphwrap").is_visible(), "C AST renders")
    click_stage(page, "LLVM IR (-O0)")
    page.wait_for_timeout(2200)
    ok(page.locator(".graphwrap").is_visible(), "IR CFG renders")
    shot(page, "j4_c_ir_1440.png")


def j5_c03_memory(page) -> None:
    print("[j5] C-03 → execution + memory observations")
    open_demo(page, "C-03")
    page.evaluate("""() => {
      [...document.querySelectorAll('button')]
        .find((b) => b.textContent.includes('Run (observatory)') || b.textContent.includes('Run & replay')).click();
    }""")
    page.wait_for_url("**/workspace?*execution=*", timeout=120_000)
    expect(page.locator(".execdock")).to_be_visible(timeout=30_000)
    page.wait_for_timeout(6000)
    page.evaluate("""() => {
      [...document.querySelectorAll('.exectabs button')]
        .find((b) => b.textContent === 'MemoryScope')?.click();
    }""")
    page.wait_for_timeout(2500)
    ok(page.locator(".memscope").is_visible(), "C MemoryScope renders (alloc ladder)")
    shot(page, "j5_c_memory_1440.png")


def j6_c05(page) -> None:
    print("[j6] C-05 multi-file")
    explore(page, "C-05")
    ok(page.locator(".obs-filebar .filechip").count() >= 2, "multiple translation units listed")
    click_stage(page, "Syntax Tree")
    page.wait_for_timeout(1800)
    shot(page, "j6_c05_1440.png")


def j7_compare(page) -> None:
    print("[j7] paired comparison")
    page.goto(BASE + "/compare")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1200)
    page.evaluate("""() => {
      [...document.querySelectorAll('.paircard')]
        .find((c) => c.textContent.includes('recursion'))?.click();
    }""")
    expect(page.locator(".cmp-verdict")).to_be_visible(timeout=150_000)
    ok(page.locator(".cmp-verdict.ok").count() == 1, "both rails matched")
    shot(page, "j7_compare_1440.png")


def j8_paste(page) -> None:
    print("[j8] paste custom code → analyze (Python + C)")
    page.goto(BASE + "/workspace")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(800)
    page.evaluate("""() => {
      const ta = document.querySelector('.paste-area');
      const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
      setter.call(ta, 'def sq(n):\\n    return n * n\\n\\n\\nprint(sq(9))\\n');
      ta.dispatchEvent(new Event('input', { bubbles: true }));
      [...document.querySelectorAll('button')]
        .find((b) => b.textContent.includes('Create snapshot')).click();
    }""")
    page.wait_for_timeout(3000)
    ok(page.locator(".obs-app").is_visible(), "snapshot created → workspace")
    # analyze explicitly (static, user's own code — still an explicit action)
    page.evaluate("""() => {
      [...document.querySelectorAll('button')]
        .find((b) => b.textContent.includes('Analyze with'))?.click();
    }""")
    page.wait_for_timeout(6000)
    ok(page.locator(".tokenformation, .graphwrap, .stagecanvas").first.is_visible(), "analysis renders")
    # C paste
    page.goto(BASE + "/workspace")
    page.wait_for_timeout(800)
    page.evaluate("""() => {
      [...document.querySelectorAll('.ingest-tabs button')].find((b) => b.textContent.includes('Paste'))?.click();
      const sel = document.querySelector('.ingest-body select');
      const setter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;
      setter.call(sel, 'c');
      sel.dispatchEvent(new Event('change', { bubbles: true }));
    }""")
    page.wait_for_timeout(300)
    page.evaluate("""() => {
      const ta = document.querySelector('.paste-area');
      const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
      setter.call(ta, '#include <stdio.h>\\nint main(void) { int s = 0; for (int i = 0; i < 4; i++) s += i; printf(\\"%d\\\\n\\", s); return 0; }\\n');
      ta.dispatchEvent(new Event('input', { bubbles: true }));
      [...document.querySelectorAll('button')]
        .find((b) => b.textContent.includes('Create snapshot')).click();
    }""")
    page.wait_for_timeout(3000)
    page.evaluate("""() => {
      [...document.querySelectorAll('button')]
        .find((b) => b.textContent.includes('Analyze with'))?.click();
    }""")
    page.wait_for_timeout(9000)
    ok(page.locator(".stagecanvas").first.is_visible(), "C analysis renders")
    shot(page, "j8_paste_c_1440.png")


def j9_modes_focus_resize_reload(page) -> None:
    print("[j9] modes, focus canvas, dock resize, reload persistence")
    explore(page, "PY-03")
    # modes
    page.get_by_role("button", name="Technical").click()
    page.wait_for_timeout(300)
    ok(page.locator("html[data-mode='technical']").count() == 1, "technical mode")
    ok(page.locator(".prov").first.is_visible(), "provenance visible in technical mode")
    page.get_by_role("button", name="Explore").click()
    # focus canvas
    click_stage(page, "Syntax Tree")
    page.wait_for_timeout(1500)
    page.evaluate("""() => {
      [...document.querySelectorAll('button')]
        .find((b) => b.textContent.trim() === '⤢ focus')?.click();
    }""")
    page.wait_for_timeout(900)
    ok(page.locator(".obs-canvas.fullscreen").count() == 1, "focus canvas expands")
    page.evaluate("""() => {
      [...document.querySelectorAll('button')]
        .find((b) => b.textContent.trim() === '✕ exit focus')?.click();
    }""")
    page.wait_for_timeout(700)
    ok(page.locator(".obs-canvas.fullscreen").count() == 0, "focus canvas restores")
    # dock resize persists
    w0 = page.evaluate("document.querySelector('.obs-left').getBoundingClientRect().width")
    page.evaluate("""() => {
      const h = document.querySelector('.dock-handle');
      const r = h.getBoundingClientRect();
      h.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, clientX: r.x, clientY: r.y + 100 }));
      window.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: r.x + 70, clientY: r.y + 100 }));
      window.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, clientX: r.x + 70, clientY: r.y + 100 }));
    }""")
    page.wait_for_timeout(400)
    w1 = page.evaluate("document.querySelector('.obs-left').getBoundingClientRect().width")
    ok(abs(w1 - w0) > 40, f"source dock resized ({w0:.0f} → {w1:.0f})")
    # reload persistence (URL restores analysis; dock width persists)
    page.reload()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(6000)
    w2 = page.evaluate("document.querySelector('.obs-left')?.getBoundingClientRect().width ?? 0")
    ok(abs(w2 - w1) < 2, f"dock width persists across reload ({w2:.0f})")
    ok(page.locator(".obs-app").is_visible(), "journey restored after reload")
    shot(page, "j9_workspace_1440.png")
    # playback controls exist in the walkthrough (needs a run — PY-03 has one via Run)
    run_btn = page.locator(".obs-filebar button", has_text="Run in restricted container")
    expect(run_btn).to_be_visible(timeout=30_000)
    run_btn.click()
    page.wait_for_url("**/workspace?*execution=*", timeout=120_000)
    expect(page.locator(".walkthrough, .execdock")).to_be_visible(timeout=30_000)
    page.wait_for_timeout(4000)
    click_view(page, "Watch it work")
    expect(page.locator(".theater-controls input[type='range']")).to_be_visible(timeout=30_000)
    ok(True, "playback scrubber present")
    ok(page.evaluate("[...document.querySelectorAll('.theater-controls select option')].some(o => o.textContent.includes('2×'))"),
       "speed settings up to 2×")


def main() -> None:
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", lambda m: CONSOLE_ERRORS.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: CONSOLE_ERRORS.append(str(e)))

        j1_landing_to_ast(page)
        j2_walkthrough_loops(page)
        j3_recursion(page)
        j4_c_ir(page)
        j5_c03_memory(page)
        j6_c05(page)
        j7_compare(page)
        j8_paste(page)
        j9_modes_focus_resize_reload(page)

        print(f"\nconsole errors: {len(CONSOLE_ERRORS)}")
        for e in CONSOLE_ERRORS[:10]:
            print("  console error:", e[:160])
        ok(not CONSOLE_ERRORS, "zero console errors")
        browser.close()

    print(f"\n{'ALL CHECKS PASSED' if not FAILED else 'FAILURES: ' + '; '.join(FAILED)}")
    if FAILED:
        raise SystemExit(1)
    print(f"elapsed: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
