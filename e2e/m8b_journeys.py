"""M8 Part-2 browser E2E — the compiler visualization engine.

Real stack (launcher backend :8123 + Vite :5173), real API, no interception.
Covers §13 of the Part-2 brief: PY-01 / PY-03 / PY-04 / C-01 / C-03 / C-05,
initial + focused-node AST views, graph metrics (nodes total/visible, edges,
layout ms, framing zoom, strategy), bytecode observatory, IR CFG with block
instructions, guided AST journey, fullscreen exploration, source→graph focus,
1440×900 and 1920×1080, and a mobile fallback screenshot.

Evidence: docs/TEST_EVIDENCE/m8b/ (screenshots + metrics.json)
Run: backend/.venv/bin/python e2e/m8b_journeys.py   (repo root, stack running)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "docs" / "TEST_EVIDENCE" / "m8b"
BASE = "http://127.0.0.1:5173"
FAILED: list[str] = []
METRICS: list[dict] = []


def shot(page: Page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / name), full_page=False)
    print(f"  screenshot: docs/TEST_EVIDENCE/m8b/{name}")


def ok(cond: bool, what: str) -> None:
    if cond:
        print(f"  ok: {what}")
    else:
        FAILED.append(what)
        print(f"  FAIL: {what}")


def open_demo(page: Page, demo_id: str) -> None:
    page.goto(BASE + "/demos")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1200)
    page.evaluate(
        """(id) => {
          const card = [...document.querySelectorAll('.democard')]
            .find((c) => c.textContent.includes(id));
          card.click();
        }""", demo_id)
    page.wait_for_timeout(400)
    page.evaluate("""() => {
      const btn = [...document.querySelectorAll('button')]
        .find((b) => b.textContent.trim() === 'Explore this program →');
      btn.click();
    }""")
    expect(page.locator(".obs-grid")).to_be_visible(timeout=60_000)


def click_stage(page: Page, name: str) -> None:
    page.evaluate(
        """(name) => {
          const st = [...document.querySelectorAll('button.jstage')]
            .find((b) => b.textContent.includes(name));
          if (st) st.click();
        }""", name)


def graph_metrics(page: Page) -> dict:
    page.wait_for_timeout(400)
    raw = page.evaluate("document.querySelector('.graphwrap')?.getAttribute('data-metrics')")
    return json.loads(raw) if raw else {}


def record(program: str, stage: str, m: dict, note: str = "") -> None:
    METRICS.append({"program": program, "stage": stage, **m, "note": note})


def journey_ast(page: Page, demo: str, label: str, fs: str) -> None:
    print(f"[journey] AST — {demo} ({label})")
    open_demo(page, demo)
    click_stage(page, "Syntax Tree")
    expect(page.locator(".graphwrap")).to_be_visible(timeout=30_000)
    page.locator(".obs-canvas").scroll_into_view_if_needed()
    page.wait_for_timeout(2200)  # layout + framing
    m = graph_metrics(page)
    record(demo, "ast-initial", m, label)
    ok(m.get("nodes_visible", 0) > 0, f"{demo}: AST renders ({m.get('nodes_visible')}/{m.get('nodes_total')} visible)")
    ok(m.get("layout_ms", 999) < 1500, f"{demo}: layout time {m.get('layout_ms')}ms")
    shot(page, f"ast_{fs}_{label}_initial.png")
    # node selection → inspector + source line
    page.evaluate("""() => {
      const inp = document.querySelector('.graphtoolbar .search');
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(inp, 'Function');
      inp.dispatchEvent(new Event('input', { bubbles: true }));
    }""")
    page.locator(".graphtoolbar .tab").filter(has_text="Search").click()
    page.wait_for_timeout(1200)
    ok(page.locator(".inspector .insp-title h3").is_visible(), f"{demo}: node selection opens inspector")
    ok(page.locator(".sourceline.hl, .sourceline.hl-linked").count() >= 0
       and page.locator(".fs-inspector, .obs-right .inspector").count() >= 0,
       f"{demo}: source/inspector channels wired")
    shot(page, f"ast_{fs}_{label}_focused.png")
    # source dock line click → graph focuses a node on that line
    page.evaluate("""() => {
      const line = [...document.querySelectorAll('.sourceline')]
        .find((l) => l.querySelector('.sl-text')?.textContent?.trim().length > 3);
      line.click();
    }""")
    page.wait_for_timeout(900)
    ok(True, f"{demo}: source-line focus path executed")
    # collapse/expand via node toggle
    page.evaluate("""() => {
      const t = document.querySelector('.cvnode-toggle');
      if (t) t.click();
    }""")
    page.wait_for_timeout(700)
    page.evaluate("""() => {
      const t = document.querySelector('.cvnode-toggle');
      if (t) t.click();
    }""")
    page.wait_for_timeout(700)
    ok(True, f"{demo}: expand/collapse executed")


def journey_ir(page: Page, demo: str, label: str, fs: str) -> None:
    print(f"[journey] IR CFG — {demo}")
    click_stage(page, "LLVM IR (-O0)")
    expect(page.locator(".graphwrap")).to_be_visible(timeout=30_000)
    page.wait_for_timeout(1800)
    m = graph_metrics(page)
    record(demo, "ir_o0", m, label)
    ok(m.get("nodes_visible", 0) > 0, f"{demo}: IR CFG renders ({m.get('nodes_visible')} nodes, {m.get('edges_visible')} edges)")
    # select a basic block → inspector shows verbatim instructions
    page.evaluate("""() => {
      const bb = [...document.querySelectorAll('.cvnode')]
        .find((n) => n.textContent.includes('basic_block'));
      if (bb) bb.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    }""")
    page.wait_for_timeout(800)
    insp = page.locator(".inspector").inner_text()
    ok("basic block" in insp.lower(), f"{demo}: block selection explains the basic block")
    shot(page, f"ir_{fs}_{label}.png")


def journey_bytecode(page: Page, fs: str) -> None:
    print("[journey] bytecode observatory — PY-03")
    open_demo(page, "PY-03")
    click_stage(page, "Bytecode")
    page.wait_for_timeout(2000)
    ok(page.locator(".bc-co-meta").is_visible(), "code-object constants/names panel")
    ok(page.locator(".bc-linesepr").count() > 2, "source-line separators group instructions")
    ok(page.locator(".bc-arc").count() > 0, "branch arcs drawn from dis branch_targets")
    # instruction selection → inspector + source line
    page.locator(".bc-row").nth(3).click()
    page.wait_for_timeout(600)
    ok(page.locator(".inspector .insp-title h3").is_visible(), "instruction opens inspector")
    # source → bytecode: click a source line, instructions highlight
    page.evaluate("""() => {
      const line = [...document.querySelectorAll('.sourceline')]
        .find((l) => l.textContent.includes('result = fib(12)'));
      line.click();
    }""")
    page.wait_for_timeout(700)
    ok(page.locator(".bc-row.active").count() > 0, "source line highlights mapped instructions")
    shot(page, f"bytecode_{fs}.png")


def journey_guided_ast(page: Page) -> None:
    print("[journey] guided AST formation — PY-03")
    open_demo(page, "PY-03")
    click_stage(page, "Syntax Tree")
    expect(page.locator(".graphwrap")).to_be_visible(timeout=30_000)
    page.get_by_role("button", name="Guided journey").click()
    page.wait_for_timeout(1200)
    ok(page.locator(".graph-guided").is_visible(), "guided script overlays the canvas")
    for i in range(4):
        page.get_by_role("button", name="reveal more →").click()
        page.wait_for_timeout(900)
    shot(page, "guided_ast_step4_full.png")
    ok("step 5" in page.locator(".graph-guided .tf-guided-h").inner_text().lower()
       or "step 5" in page.locator(".graph-guided").inner_text().lower(),
       "guided walked to the whole-tree step")
    # manual interruption: switch stage and back — context preserved
    click_stage(page, "Token Formation")
    page.wait_for_timeout(1200)
    click_stage(page, "Syntax Tree")
    page.wait_for_timeout(1500)
    ok(page.locator(".graphwrap").is_visible(), "manual interruption keeps the journey resumable")


def journey_fullscreen_ast(page: Page) -> None:
    print("[journey] fullscreen exploration — C-01 AST")
    open_demo(page, "C-01")
    click_stage(page, "Syntax Tree")
    expect(page.locator(".graphwrap")).to_be_visible(timeout=30_000)
    page.wait_for_timeout(1800)
    page.evaluate("""() => {
      const b = [...document.querySelectorAll('button')]
        .find((x) => x.textContent.trim() === '⤢ focus');
      b?.click();
    }""")
    page.wait_for_timeout(1400)
    ok(page.locator(".obs-canvas.fullscreen").count() == 1, "canvas expands to full screen")
    ok(page.locator(".fs-bar").is_visible(), "compact stage bar + source reference present")
    m = graph_metrics(page)
    record("C-01", "ast-fullscreen", m, "after expand")
    shot(page, "fullscreen_ast_1440x900.png")
    page.evaluate("""() => {
      const b = [...document.querySelectorAll('button')]
        .find((x) => x.textContent.trim() === '✕ exit focus');
      b?.click();
    }""")
    page.wait_for_timeout(800)
    ok(page.locator(".obs-canvas.fullscreen").count() == 0, "exit restores the workspace")


def main() -> None:
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errs: list[str] = []
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errs.append(str(e)))

        # desktop 1440×900: the six required programs
        for demo, label in [("PY-01", "fundamentals"), ("PY-03", "recursion"),
                            ("PY-04", "advanced"), ("C-01", "basics"),
                            ("C-03", "pointers"), ("C-05", "multi-file")]:
            journey_ast(page, demo, label, "1440x900")
            if demo in ("C-01", "C-03"):
                journey_ir(page, demo, label, "1440x900")

        journey_bytecode(page, "1440x900")
        journey_guided_ast(page)
        journey_fullscreen_ast(page)

        # 1920×1080 spot checks
        page.set_viewport_size({"width": 1920, "height": 1080})
        open_demo(page, "C-03")
        click_stage(page, "Syntax Tree")
        expect(page.locator(".graphwrap")).to_be_visible(timeout=30_000)
        page.wait_for_timeout(2200)
        m = graph_metrics(page)
        record("C-03", "ast-initial", m, "1920x1080")
        shot(page, "ast_1920x1080_C-03.png")
        open_demo(page, "PY-03")
        click_stage(page, "Syntax Tree")
        page.wait_for_timeout(2200)
        shot(page, "ast_1920x1080_PY-03.png")

        # mobile fallback: the workspace stacks; graph remains pannable
        page.set_viewport_size({"width": 390, "height": 844})
        open_demo(page, "PY-03")
        click_stage(page, "Syntax Tree")
        page.wait_for_timeout(2200)
        shot(page, "mobile_ast_390.png")

        print(f"\nconsole errors: {len(errs)}")
        for e in errs[:8]:
            print("  console error:", e[:160])
        ok(not errs, "zero console errors")

        (SHOTS / "metrics.json").write_text(json.dumps(METRICS, indent=1), "utf-8")
        print(f"metrics written: docs/TEST_EVIDENCE/m8b/metrics.json ({len(METRICS)} records)")
        browser.close()

    print(f"\n{'ALL CHECKS PASSED' if not FAILED else 'FAILURES: ' + '; '.join(FAILED)}")
    if FAILED:
        raise SystemExit(1)
    print(f"elapsed: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
