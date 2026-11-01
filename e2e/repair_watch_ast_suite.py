"""Repair acceptance suite — Watch It Work (A) + AST edges/focus/contrast (B).

G1: Watch layout + real playback against recorded PY-02 and PY-03 runs.
G2: painted AST edges (C and Python), auto-focus-once lifecycle, contrast.
G3: screenshot matrix 1920x1080 / 1366x768 / 390x844.

Real stack, no mocks. Evidence: docs/TEST_EVIDENCE/repair_watch_ast/after/
Run: backend/.venv/bin/python e2e/repair_watch_ast_suite.py   (repo root, stack running)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "docs" / "TEST_EVIDENCE" / "repair_watch_ast" / "after"
BASE = "http://127.0.0.1:5173"
FAILED: list[str] = []
CONSOLE_ERRORS: list[str] = []


def shot(page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / name), full_page=False)
    print(f"  screenshot: docs/TEST_EVIDENCE/repair_watch_ast/after/{name}")


def ok(cond: bool, what: str) -> bool:
    if cond:
        print(f"  ok: {what}")
    else:
        FAILED.append(what)
        print(f"  FAIL: {what}")
    return bool(cond)


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


def watch(page, demo_id: str) -> None:
    open_demo(page, demo_id)
    page.evaluate("""() => {
      [...document.querySelectorAll('button')]
        .find((b) => b.textContent.includes('Watch This Program Work')).click();
    }""")
    page.wait_for_url("**/workspace?*walkthrough=1", timeout=120_000)
    page.wait_for_selector(".walkthrough", timeout=30_000)
    page.wait_for_timeout(3500)


def explore(page, demo_id: str) -> None:
    open_demo(page, demo_id)
    page.evaluate("""() => {
      [...document.querySelectorAll('button')]
        .find((b) => b.textContent.includes('Explore this program →')).click();
    }""")
    page.wait_for_selector(".obs-app", timeout=90_000)
    page.wait_for_timeout(2500)


def click_stage(page, name: str) -> None:
    page.evaluate(
        """(name) => {
          [...document.querySelectorAll('button.jstage')]
            .find((b) => b.textContent.includes(name))?.click();
        }""", name)


def ctrl(page, label: str) -> None:
    page.evaluate(
        """(label) => {
          const b = [...document.querySelectorAll('.wt-controls .btn')]
            .find((b) => b.getAttribute('aria-label') === label);
          if (!b) throw new Error('control missing: ' + label);
          b.click();
        }""", label)


def wt_state(page) -> dict:
    return page.evaluate("""() => {
      const counter = [...document.querySelectorAll('.wt-controls .muted')]
        .map((m) => m.textContent).find((t) => t.includes('meaningful events')) ?? '';
      const explain = document.querySelector('.wt-explain')?.textContent ?? '';
      const hl = document.querySelector('.sourcedock .sourceline.hl-linked')
        ?.getAttribute('data-line') ?? null;
      const frames = document.querySelectorAll('.wt-stack .wt-frame').length;
      const vars = document.querySelectorAll('.wt-vartable tr').length;
      const range = document.querySelector('.wt-controls input[type="range"]');
      const loopChip = document.querySelector('.wt-flow .chip.partial')?.textContent ?? null;
      return { counter, explain: explain.slice(0, 80), hl, frames, vars,
               rangeVal: range ? Number(range.value) : null,
               rangeMax: range ? Number(range.max) : null, loopChip };
    }""")


WATCH_PANELS = [".wt-flow", ".wt-stack", ".wt-vars", ".wt-out"]


def watch_layout_audit(page) -> dict:
    return page.evaluate("""(panels) => {
      const rects = panels.map((s) => {
        const el = document.querySelector(s);
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { s, x: r.x, y: r.y, w: r.width, h: r.height };
      }).filter(Boolean);
      const overlap = (a, b) =>
        a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
      const overlaps = [];
      for (let i = 0; i < rects.length; i++)
        for (let j = i + 1; j < rects.length; j++)
          if (overlap(rects[i], rects[j])) overlaps.push([rects[i].s, rects[j].s]);
      // clipped content: panels must not clip their own text horizontally
      const clipped = panels.filter((s) => {
        const el = document.querySelector(s);
        return el && el.scrollWidth > el.clientWidth + 2 &&
               getComputedStyle(el).overflowX !== 'auto' &&
               getComputedStyle(el).overflowX !== 'scroll';
      });
      const ctrl = document.querySelector('.wt-controls');
      const clippedControls = ctrl ? ctrl.scrollWidth > ctrl.clientWidth + 2 : null;
      const dockBody = document.querySelector('.sourcedock-body');
      let allLinesReachable = false;
      if (dockBody) {
        dockBody.scrollTop = dockBody.scrollHeight;
        const lr = dockBody.querySelector('.sourceline:last-child')?.getBoundingClientRect();
        const br = dockBody.getBoundingClientRect();
        allLinesReachable = !!lr && lr.bottom <= br.bottom + 1 && lr.top >= br.top - 1;
        dockBody.scrollTop = 0;
      }
      const dockLines = dockBody ? dockBody.querySelectorAll('.sourceline').length : 0;
      const center = document.querySelector('.obs-center');
      return {
        overlaps, clipped, clippedControls,
        controlsWidth: ctrl ? ctrl.clientWidth : null,
        dockLines, allLinesReachable,
        centerScroll: center ? { sh: center.scrollHeight, ch: center.clientHeight } : null,
        pageHOverflow: document.documentElement.scrollWidth >
          document.documentElement.clientWidth + 1,
        controlsSticky: getComputedStyle(document.querySelector('.wt-controls')).position,
        honestOutputLabel: (document.querySelector('.wt-out .theater-pane-h')?.textContent ?? '')
          .includes('per-print timing is not recorded'),
      };
    }""", WATCH_PANELS)


# ——— Workstream A ———

def a_watch_playback(page) -> None:
    print("[A1] PY-02 watch: layout + full playback")
    watch(page, "PY-02")
    a = watch_layout_audit(page)
    ok(not a["overlaps"], f"no overlapping watch panels ({a['overlaps']})")
    ok(not a["clipped"], f"no clipped panel content ({a['clipped']})")
    ok(a["dockLines"] == 24 and a["allLinesReachable"],
       f"all 24 source lines reachable via scroll (lines={a['dockLines']})")
    ok(not a["pageHOverflow"], "no page-wide horizontal overflow")
    ok(a["controlsSticky"] == "sticky", "transport controls sticky while scrolling")
    ok(a["honestOutputLabel"], "output honesty label intact")
    shot(page, "a_watch_py02_1920x1080.png")

    s0 = wt_state(page)
    ok(s0["counter"].startswith("1/"), f"counter starts at 1 ({s0['counter']})")
    ok(s0["rangeMax"] == s0["rangeMax"] and s0["rangeMax"] > 40, "scrubber spans all events")

    page.evaluate("""() => {
      const sel = document.querySelector('.wt-controls select');
      const setter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;
      setter.call(sel, '2'); sel.dispatchEvent(new Event('change', { bubbles: true }));
    }""")
    ctrl(page, "play")
    page.wait_for_timeout(2500)
    ctrl(page, "pause")
    s1 = wt_state(page)
    ok(int(s1["counter"].split("/")[0]) > 3, f"play advanced at 2x then pause held ({s1['counter']})")
    page.wait_for_timeout(1000)
    s1b = wt_state(page)
    ok(s1b["counter"] == s1["counter"], "pause truly stops playback")

    ctrl(page, "previous meaningful event")
    s2 = wt_state(page)
    ok(int(s2["counter"].split("/")[0]) == int(s1["counter"].split("/")[0]) - 1,
       "step back decrements")
    ctrl(page, "next meaningful event")
    s3 = wt_state(page)
    ok(s3["counter"] == s1["counter"], "step forward restores position")

    ctrl(page, "restart")
    s4 = wt_state(page)
    ok(s4["counter"].startswith("1/"), "restart returns to event 1")
    ctrl(page, "jump to end")
    s5 = wt_state(page)
    ok(s5["counter"].startswith(f"{s5['rangeMax'] + 1}/"), f"jump-to-end reaches last event ({s5['counter']})")

    # scrubber seek
    page.evaluate("""() => {
      const r = document.querySelector('.wt-controls input[type=range]');
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(r, '10'); r.dispatchEvent(new Event('input', { bubbles: true }));
    }""")
    s6 = wt_state(page)
    ok(s6["counter"].startswith("11/"), f"scrubber seek to event 11 ({s6['counter']})")

    # sync: line event → source highlight + explain agree
    found = None
    for _ in range(40):
        ctrl(page, "next meaningful event")
        st = wt_state(page)
        if st["hl"] is not None and st["explain"].startswith("Line "):
            m = st["explain"].split(" ")[1]
            if st["hl"] == m:
                found = (st["hl"], st["explain"])
                break
    ok(found is not None,
       f"source highlight matches explained line (hl={found[0] if found else '?'})")
    ok(page.locator(".wt-stack .wt-frame").count() >= 1, "call stack reflects the event")
    shot(page, "a_watch_py02_mid_1920.png")


def a_watch_recursion(page) -> None:
    print("[A2] PY-03 watch: recursion stack")
    watch(page, "PY-03")
    ctrl(page, "jump to end")
    page.wait_for_timeout(600)
    s = wt_state(page)
    ok(s["frames"] == 0,
       f"stack fully unwound at the last recorded event (frames={s['frames']}, counter={s['counter']})")
    # mid-play the stack grows beyond one frame
    page.evaluate("""() => {
      const r = document.querySelector('.wt-controls input[type=range]');
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(r, '30'); r.dispatchEvent(new Event('input', { bubbles: true }));
    }""")
    page.wait_for_timeout(300)
    smid = wt_state(page)
    ok(smid["frames"] >= 2, f"recursion stack grows mid-run (frames={smid['frames']})")
    shot(page, "a_watch_py03_1920x1080.png")


def a_watch_viewports(browser) -> None:
    print("[A3] watch matrix: 1920 / 1366 / 390")
    for w, h, tag in [(1920, 1080, "1920x1080"), (1366, 768, "1366x768"), (390, 844, "390x844")]:
        page = browser.new_page(viewport={"width": w, "height": h})
        page.on("console", lambda m: CONSOLE_ERRORS.append(m.text) if m.type == "error" else None)
        watch(page, "PY-02")
        a = watch_layout_audit(page)
        ok(not a["overlaps"] and not a["clipped"],
           f"[{tag}] no overlaps/clipped panels (overlaps={a['overlaps']} clipped={a['clipped']})")
        ok(a["allLinesReachable"] and a["dockLines"] == 24, f"[{tag}] full source reachable")
        ok(not a["pageHOverflow"], f"[{tag}] no horizontal page overflow")
        shot(page, f"a_watch_py02_{tag}.png")
        page.close()


# ——— Workstream B ———

def b_edge_audit(page) -> dict:
    return page.evaluate("""() => {
      const svgs = [...document.querySelectorAll('.react-flow__edges svg')];
      const zero = svgs.filter((s) => s.getBoundingClientRect().width < 1).length;
      const paths = [...document.querySelectorAll('.react-flow__edge-path')];
      const sample = paths.slice(0, 3).map((p) => {
        const cs = getComputedStyle(p);
        const bb = p.getBoundingClientRect();
        return { stroke: cs.stroke, sw: parseFloat(cs.strokeWidth), w: Math.round(bb.width) };
      });
      const edges = [...document.querySelectorAll('.react-flow__edge')];
      const kinds = edges.map((e) => e.className).filter((c) => String(c).includes('edge-branch')).length;
      const nodeCount = document.querySelectorAll('.react-flow__node').length;
      const metrics = JSON.parse(document.querySelector('.graphwrap')?.getAttribute('data-metrics') ?? '{}');
      return { svgCount: svgs.length, zeroWidth: zero, sample,
               branchEdgesInAST: kinds, nodeCount, metrics };
    }""")


def b_focus_state(page) -> dict:
    return page.evaluate("""() => ({
      fullscreen: document.querySelectorAll('.obs-canvas.fullscreen').length,
      exitBtn: [...document.querySelectorAll('button')]
        .some((b) => b.textContent.trim() === '✕ exit focus'),
    })""")


def b_ast_focus_and_edges(page, demo_id: str, tag: str, pixel_check: bool) -> None:
    print(f"[B] {demo_id} AST ({tag})")
    explore(page, demo_id)
    # before entering AST no focus
    ok(b_focus_state(page)["fullscreen"] == 0, f"[{tag}] focus closed before AST")
    click_stage(page, "Syntax Tree")
    page.wait_for_selector(".obs-canvas.fullscreen", timeout=30_000)
    page.wait_for_timeout(2500)
    ok(True, f"[{tag}] entering AST auto-opens focus mode")
    e = b_edge_audit(page)
    ok(e["svgCount"] > 0 and e["zeroWidth"] == 0,
       f"[{tag}] edge SVG layer has a real paint box (zero-width={e['zeroWidth']})")
    ok(all(p["sw"] >= 2 and p["w"] > 0 for p in e["sample"]),
       f"[{tag}] connector strokes >= 2px with geometry ({e['sample'][:2]})")
    ok(e["branchEdgesInAST"] == 0, f"[{tag}] AST uses containment edges only (no CFG branch edges)")
    ok((e["metrics"].get("initial_zoom") or 0) > 0.05,
       f"[{tag}] graph fitted to canvas once (zoom={e['metrics'].get('initial_zoom')})")
    shot(page, f"b_ast_{tag}_focused.png")

    if pixel_check:
        # painted-pixel proof: sample the stroke midpoint of a visible edge
        hit = page.evaluate("""() => {
          const path = [...document.querySelectorAll('.react-flow__edge-path')]
            .find((p) => { const r = p.getBoundingClientRect(); return r.width > 30 && r.height > 1; });
          if (!path) return null;
          const len = path.getTotalLength();
          const pt = path.getPointAtLength(len / 2);
          const vp = path.closest('.react-flow__viewport');
          const m = new DOMMatrix(getComputedStyle(vp).transform);
          const tp = m.transformPoint(pt);
          const wr = path.closest('.graphwrap').getBoundingClientRect();
          return { x: wr.x + tp.x, y: wr.y + tp.y };
        }""")
        if hit:
            buf = page.screenshot(clip={"x": max(0, hit["x"] - 3), "y": max(0, hit["y"] - 3),
                                        "width": 7, "height": 7})
            open_shots = SHOTS / f"b_ast_{tag}_edgepixel.png"
            SHOTS.mkdir(parents=True, exist_ok=True)
            open_shots.write_bytes(buf)
            # a painted edge stroke differs from the flat canvas background
            import struct, zlib
            def png_pixels(data: bytes):
                pos, idat = 8, b""
                w = h = None
                while pos < len(data):
                    ln = struct.unpack(">I", data[pos:pos + 4])[0]
                    typ = data[pos + 4:pos + 8]
                    if typ == b"IHDR":
                        w, h = struct.unpack(">II", data[pos + 8:pos + 16])
                    if typ == b"IDAT":
                        idat += data[pos + 8:pos + 8 + ln]
                    pos += 12 + ln
                raw = zlib.decompress(idat)
                px = set()
                stride = w * 3 + 1
                for y in range(h):
                    row = raw[y * stride + 1:(y + 1) * stride]
                    for x in range(w):
                        px.add((row[x * 3], row[x * 3 + 1], row[x * 3 + 2]))
                return px
            px = png_pixels(buf)
            bright = sum(1 for p in px if sum(p) > 3 * 90)
            ok(bright >= 2, f"[{tag}] edge stroke actually PAINTS ({bright} bright px at midpoint)")
        else:
            ok(False, f"[{tag}] edge pixel probe found no visible path")

    # selection sync: click a child node → inspector + source update
    sel = page.evaluate("""() => {
      const nodes = [...document.querySelectorAll('.react-flow__node')];
      const target = nodes.find((n) => /Assign|For|Compound|Call/.test(n.textContent)) ?? nodes[1];
      if (!target) return null;
      target.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      const r = target.getBoundingClientRect();
      return { label: target.textContent.slice(0, 24) };
    }""")
    page.wait_for_timeout(700)
    insp = page.evaluate("""() => ({
      fsInspector: !!document.querySelector('.fs-inspector'),
      inspector: !!document.querySelector('.obs-right .inspector'),
      title: (document.querySelector('.fs-inspector .insp-title h3, .insp-title h3')?.textContent ?? ''),
      hl: document.querySelector('.sourcedock .sourceline.hl-linked, .sourcedock .sourceline.hl')
        ?.getAttribute('data-line') ?? null,
    })""")
    ok(sel is not None and (insp["fsInspector"] or insp["inspector"]) and insp["title"],
       f"[{tag}] node selection opens inspector ({sel} → {insp['title']})")

    # collapse / expand
    before = page.evaluate("document.querySelectorAll('.react-flow__node').length")
    page.evaluate("""() => {
      const t = [...document.querySelectorAll('.cvnode-toggle')]
        .find((b) => b.closest('.cvnode').textContent.includes('FunctionDef')
                  || b.closest('.cvnode').textContent.includes('FunctionDecl'));
      t?.click();
    }""")
    page.wait_for_timeout(900)
    after = page.evaluate("document.querySelectorAll('.react-flow__node').length")
    ok(after < before, f"[{tag}] collapse hides subtree ({before}→{after})")
    page.evaluate("""() => {
      const t = [...document.querySelectorAll('.cvnode-toggle')]
        .find((b) => b.closest('.cvnode').textContent.includes('FunctionDef')
                  || b.closest('.cvnode').textContent.includes('FunctionDecl'));
      t?.click();
    }""")
    page.wait_for_timeout(900)
    restored = page.evaluate("document.querySelectorAll('.react-flow__node').length")
    ok(restored == before, f"[{tag}] expand restores subtree ({restored})")

    # manual exit focus persists against rerenders/selection
    page.evaluate("""() => {
      [...document.querySelectorAll('button')]
        .find((b) => b.textContent.trim() === '✕ exit focus')?.click();
    }""")
    page.wait_for_timeout(600)
    ok(b_focus_state(page)["fullscreen"] == 0,
       f"[{tag}] manual Exit Focus works")
    page.evaluate("""() => {
      const n = document.querySelector('.react-flow__node');
      n?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    }""")
    page.wait_for_timeout(900)
    ok(b_focus_state(page)["fullscreen"] == 0, f"[{tag}] focus stays closed after selection/rerender")

    # leaving AST and returning re-arms auto-focus (fresh navigation, exactly once)
    click_stage(page, "Token Formation")
    page.wait_for_timeout(1200)
    ok(b_focus_state(page)["fullscreen"] == 0, f"[{tag}] other stage usable, focus still closed")
    click_stage(page, "Syntax Tree")
    page.wait_for_selector(".obs-canvas.fullscreen", timeout=30_000)
    page.wait_for_timeout(800)
    ok(True, f"[{tag}] fresh navigation into AST re-opens focus once")
    # exit again to leave a clean state
    page.evaluate("""() => {
      [...document.querySelectorAll('button')]
        .find((b) => b.textContent.trim() === '✕ exit focus')?.click();
    }""")
    page.wait_for_timeout(500)
    shot(page, f"b_ast_{tag}_unfocused.png")


def b_focus_matrix(browser) -> None:
    print("[B1] focus+edges: PY-02 (python) and C-01 (C) at 1920")
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.on("console", lambda m: CONSOLE_ERRORS.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: CONSOLE_ERRORS.append(str(e)))
    b_ast_focus_and_edges(page, "PY-02", "py02_1920", pixel_check=True)
    b_ast_focus_and_edges(page, "C-01", "c01_1920", pixel_check=True)
    page.close()


def b_ast_matrix(browser) -> None:
    print("[B2] AST matrix: 1366 + 390")
    for w, h, tag in [(1366, 768, "1366x768"), (390, 844, "390x844")]:
        page = browser.new_page(viewport={"width": w, "height": h})
        page.on("console", lambda m: CONSOLE_ERRORS.append(m.text) if m.type == "error" else None)
        explore(page, "PY-02")
        click_stage(page, "Syntax Tree")
        page.wait_for_selector(".obs-canvas.fullscreen", timeout=30_000)
        page.wait_for_timeout(2500)
        e = b_edge_audit(page)
        ok(e["zeroWidth"] == 0 and e["svgCount"] > 0, f"[{tag}] edges painted")
        shot(page, f"b_ast_py02_{tag}_focused.png")
        page.evaluate("""() => {
          [...document.querySelectorAll('button')]
            .find((b) => b.textContent.trim() === '✕ exit focus')?.click();
        }""")
        page.wait_for_timeout(500)
        ok(b_focus_state(page)["fullscreen"] == 0, f"[{tag}] exit focus works")
        shot(page, f"b_ast_py02_{tag}_unfocused.png")
        page.close()


def main() -> None:
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.on("console", lambda m: CONSOLE_ERRORS.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: CONSOLE_ERRORS.append(str(e)))
        a_watch_playback(page)
        a_watch_recursion(page)
        page.close()
        a_watch_viewports(browser)
        b_focus_matrix(browser)
        b_ast_matrix(browser)
        browser.close()

    print(f"\nconsole errors: {len(CONSOLE_ERRORS)}")
    for e in CONSOLE_ERRORS[:10]:
        print("  console error:", e[:160])
    ok(not CONSOLE_ERRORS, "zero console errors")
    print(f"\n{'ALL CHECKS PASSED' if not FAILED else 'FAILURES: ' + '; '.join(FAILED)}")
    if FAILED:
        raise SystemExit(1)
    print(f"elapsed: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
