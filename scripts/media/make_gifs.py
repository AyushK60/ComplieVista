#!/usr/bin/env python3
"""Record short GIFs of the main features by driving the REAL running app.

    backend/.venv/bin/python scripts/media/make_gifs.py          # all three
    backend/.venv/bin/python scripts/media/make_gifs.py links    # one of: journey links watch

Needs: the stack running (Start.cmd), Playwright (installed with the backend venv) and
Pillow (`backend/.venv/bin/pip install Pillow`). Frames are real screenshots; nothing is
mocked. Output: docs/media/*.gif (kept small: 960 px wide, adaptive 96-colour palette).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, expect, sync_playwright

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs" / "media"
BASE = "http://127.0.0.1:5173"
W, H = 1280, 780
C_SRC = (REPO / "backend" / "tests" / "fixtures" / "linemap" / "demo.c").read_text()


class Rec:
    def __init__(self, page: Page):
        self.page = page
        self.frames: list[tuple[Image.Image, int]] = []

    def snap(self, ms: int = 900) -> None:
        png = self.page.screenshot()
        im = Image.open(io.BytesIO(png)).convert("RGB")
        im = im.resize((960, round(960 * im.height / im.width)), Image.LANCZOS)
        self.frames.append((im, ms))

    def save(self, name: str) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        pal = [f.quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
               for f, _ in self.frames]
        pal[0].save(OUT / name, save_all=True, append_images=pal[1:], loop=0,
                    duration=[d for _, d in self.frames], optimize=True, disposal=2)
        kb = (OUT / name).stat().st_size // 1024
        print(f"  wrote docs/media/{name}: {len(self.frames)} frames, {kb} KB")


def load_c(page: Page, rec: Rec | None = None) -> None:
    page.goto(BASE + "/workspace")
    page.get_by_role("tab", name="Paste").click()
    page.get_by_label("Language").select_option("c")
    page.get_by_label("Filename").fill("demo.c")
    editor = page.get_by_label("paste source code")
    expect(editor).to_be_visible(timeout=20000)
    editor.click()
    page.keyboard.press("Control+A")
    page.keyboard.insert_text(C_SRC)
    if rec:
        rec.snap(1400)
    page.get_by_role("button", name="Load code").click()
    expect(page.get_by_role("list", name="snapshot files")).to_be_visible(timeout=20000)


def nav(page: Page):
    return page.get_by_role("navigation", name="compilation journey")


def gif_journey(page: Page) -> None:
    rec = Rec(page)
    load_c(page, rec)
    rec.snap(1200)
    page.get_by_role("button", name=re.compile("^Analyze with")).click()
    expect(nav(page)).to_be_visible(timeout=120000)
    page.wait_for_timeout(800)
    rec.snap(1500)
    for stage in ("Token Formation", "LLVM IR (-O0)", "Assembly"):
        nav(page).get_by_role("button", name=stage, exact=True).click()
        expect(page.get_by_role("heading", name=stage, level=2)).to_be_visible(timeout=20000)
        page.wait_for_timeout(900)
        rec.snap(1800)
    nav(page).get_by_role("button", name="Syntax Tree", exact=True).click()
    expect(page.get_by_role("heading", name="Syntax Tree", level=2)).to_be_visible(timeout=20000)
    page.wait_for_timeout(1800)
    rec.snap(2400)
    rec.save("compilation-journey.gif")


def gif_links(page: Page) -> None:
    rec = Rec(page)
    load_c(page)
    page.get_by_role("button", name=re.compile("^Analyze with")).click()
    expect(nav(page)).to_be_visible(timeout=120000)
    page.get_by_role("tab", name="Optimization lab").click(timeout=60000)
    page.get_by_role("button", name=re.compile(r"Build -O0.*-O2")).click()
    link = page.locator(".slv")
    expect(link).to_be_visible(timeout=240000)
    link.scroll_into_view_if_needed()
    link.get_by_label("level for line links").select_option("O0")
    page.wait_for_timeout(700)
    rec.snap(1500)
    src = link.get_by_label("source").locator(".slv-row")
    for n in (4, 10, 17):                      # return x*x ; total += square(i) ; printf
        src.nth(n - 1).click()
        page.wait_for_timeout(500)
        rec.snap(2000)
    link.get_by_label("level for line links").select_option("O2")
    src.nth(9).click()
    page.wait_for_timeout(500)
    rec.snap(2200)
    link.get_by_label("level for line links").select_option("O0")
    src.nth(15).click()                        # the dead local: code at -O0 ...
    page.wait_for_timeout(500)
    rec.snap(1800)
    link.get_by_label("level for line links").select_option("O2")
    page.wait_for_timeout(500)
    rec.snap(2600)                             # ... none at -O2
    rec.save("source-ir-asm-links.gif")


def gif_watch(page: Page) -> None:
    rec = Rec(page)
    page.goto(BASE + "/demos/PY-03")
    expect(page.locator(".demo-detail")).to_be_visible(timeout=15000)
    page.wait_for_timeout(500)
    rec.snap(1600)
    page.get_by_role("button", name="Run (observatory)").click()
    expect(page.locator(".execdock")).to_be_visible(timeout=120000)
    page.get_by_role("tab", name="Watch it work").click()
    page.wait_for_timeout(1500)
    rec.snap(1600)
    nxt = page.get_by_role("button", name="next meaningful event")
    for _ in range(9):
        nxt.click()
        page.wait_for_timeout(450)
        rec.snap(900)
    rec.snap(1800)
    rec.save("watch-it-work.gif")


JOBS = {"journey": gif_journey, "links": gif_links, "watch": gif_watch}


def main() -> int:
    wanted = sys.argv[1:] or list(JOBS)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name in wanted:
            print(f"[{name}]")
            page = browser.new_page(viewport={"width": W, "height": H})
            JOBS[name](page)
            page.close()
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
