"""Learning layer (diff, lesson, quiz, share link, print poster, phone layout) against the real stack.

Builds the -O0/-O1/-O2 experiment for demo C-02 through the app's own API, then:
  * diff: rows exist, selecting a row shows real -O0 / -O2 instructions
  * lesson: Next walks source -> IR -> assembly -> next line; wording never says "0 LLVM IR" for a
    line the compiler gave no IR location; "Copy link" produces a link that reopens the lesson
  * quiz: answer reveals real counts and a score
  * print: under print media the controls are hidden, panes are not height-clipped, and a PDF is produced
  * phone (375 px) and tablet (768 px): no horizontal page scroll in any of the three views
Usage: python e2e/learning_suite.py   (stack running on :5173)
"""
from __future__ import annotations

import json
import sys
import urllib.request

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"
FAIL: list[str] = []


def ok(cond: bool, what: str) -> None:
    print(("  ok: " if cond else "  FAIL: ") + what)
    if not cond:
        FAIL.append(what)


def post(path: str) -> dict:
    return json.load(urllib.request.urlopen(urllib.request.Request(BASE + path, method="POST"), timeout=120))


def main() -> None:
    exp = post("/api/v1/demos/C-02/optimize")["experiment_id"]
    import time
    for _ in range(60):
        st = json.load(urllib.request.urlopen(f"{BASE}/api/v1/experiments/{exp}"))["status"]
        if st in ("COMPLETED", "FAILED"):
            break
        time.sleep(2)
    ok(st == "COMPLETED", "C-02 -O0/-O1/-O2 experiment completed")
    run = post("/api/v1/demos/C-02/run")
    url = (f"{BASE}/workspace?demo=C-02&project=demo-library&execution={run['execution_id']}"
           f"&snapshot={run['snapshot_id']}&target={run['target_id']}")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE)
        page = ctx.new_page()
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        print("[diff]")
        page.goto(url + "&view=diff"); page.wait_for_selector(".ol-row", timeout=60000)
        ok(page.locator(".ol-row").count() >= 5, "diff lists the changed lines")
        page.locator(".ol-row").first.click(); page.wait_for_timeout(600)
        pres = page.locator(".ol-side pre").all_inner_texts()
        ok(len(pres) == 2 and pres[0].strip() not in ("", "loading…"), "selecting a line shows real -O0 instructions")

        print("[lesson]")
        page.goto(url + "&view=lesson"); page.wait_for_selector(".ol-say", timeout=60000)
        seen = set()
        for _ in range(40):
            seen.add(page.inner_text(".ol-say"))
            nxt = page.locator(".ol-nav .btn.primary")
            if nxt.is_disabled():
                break
            nxt.click()
        ok(len(seen) >= 6, f"lesson walks through many distinct stages ({len(seen)} seen)")
        ok(not any("links to 0 LLVM IR instruction(s); at -O2 it links to 0" in s for s in seen),
           "no misleading '0 IR instructions' sentence")
        ok(page.locator(".ol-nav .btn.primary").is_disabled(), "lesson ends cleanly")
        page.locator(".ol-head .btn").click(); page.wait_for_timeout(300)
        link = page.evaluate("() => navigator.clipboard.readText()")
        ok("view=lesson" in link and "step=" in link, "copied link carries view and step")
        page2 = ctx.new_page(); page2.goto(link); page2.wait_for_selector(".ol-say", timeout=60000)
        ok(page2.locator(".ol-phases").count() == 1, "the copied link reopens the lesson")
        page2.close()

        print("[quiz]")
        page.goto(url + "&view=quiz"); page.wait_for_selector(".ol-opts", timeout=60000)
        page.locator(".ol-opts .btn").first.click(); page.wait_for_timeout(500)
        ok("score 1 /" in page.inner_text(".ol-head .muted") or "score 0 /" in page.inner_text(".ol-head .muted"), "quiz keeps a score")
        ok("The real build shows" in page.inner_text("[aria-live=polite]"), "quiz reveals the real counts")

        print("[print]")
        page.goto(url + "&view=diff"); page.wait_for_selector(".ol-row", timeout=60000)
        page.emulate_media(media="print")
        hidden = page.evaluate("() => ['.ol-tabs', '.navtools'].every((s) => { const e = document.querySelector(s); return !e || getComputedStyle(e).display === 'none'; })")
        ok(hidden, "print media hides the tabs and header tools")
        ok(page.evaluate("() => getComputedStyle(document.querySelector('.ol-rows')).maxHeight") == "none",
           "print media removes the diff list height cap")
        pdf = page.pdf(print_background=True)
        ok(pdf[:4] == b"%PDF" and len(pdf) > 5000, f"a PDF is produced ({len(pdf)} bytes)")
        page.emulate_media(media="screen")

        print("[phone and tablet]")
        for w, h in ((375, 812), (768, 1024)):
            pg = browser.new_page(viewport={"width": w, "height": h})
            for view in ("diff", "lesson", "quiz"):
                pg.goto(url + f"&view={view}"); pg.wait_for_selector(".ol", timeout=60000); pg.wait_for_timeout(800)
                over = pg.evaluate("() => document.documentElement.scrollWidth - innerWidth")
                ok(over <= 1, f"{w}px {view}: no horizontal page scroll (overflow {over}px)")
            pg.close()

        ok(not errors, "zero console errors" + (f": {errors[:2]}" if errors else ""))
        browser.close()
    print("\nFAILURES: " + "; ".join(FAIL) if FAIL else "\nALL CHECKS PASSED")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
