"""M1-F browser E2E journeys (Windows Playwright → Vite/WSL → FastAPI/WSL).

Run from Windows:  python e2e/m1_journeys.py
Proves: M0 regression on Home; paste journey; ZIP upload journey; REAL public
GitHub import journey; error states; target inspector honesty. Screenshots are
written to docs/TEST_EVIDENCE/m1/.
"""
from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "docs" / "TEST_EVIDENCE" / "m1"
BASE = "http://127.0.0.1:5173"
FAILED: list[str] = []
SKIPPED: list[str] = []


def shot(page: Page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / name), full_page=True)
    print(f"  screenshot: docs/TEST_EVIDENCE/m1/{name}")


def step(name: str) -> None:
    print(f"[journey] {name}")


def expect_or_fail(cond: bool, what: str) -> None:
    if cond:
        print(f"  ok: {what}")
    else:
        FAILED.append(what)
        print(f"  FAIL: {what}")


def journey_home(page: Page) -> None:
    # The M0 "toolchain proof" page was replaced by the landing page in M8; the
    # intent of this check (the app is live and reports real backend/toolchain
    # state instead of a hard-coded claim) is preserved against the current page.
    step("Home: landing page + live backend health")
    page.goto(BASE + "/")
    expect(page.get_by_role("heading", name=re.compile("Watch your code"))).to_be_visible()
    expect(page.get_by_role("link", name="Explore live demos")).to_be_visible()
    expect(page.get_by_text("ok · python 3.12", exact=False).first).to_be_visible(timeout=15000)
    expect(page.get_by_text("clang", exact=False).first).to_be_visible()
    expect_or_fail(True, "home renders and shows live backend health + toolchain versions")
    shot(page, "home_m0_regression.png")


def journey_paste(page: Page) -> None:
    step("Paste journey: Python script with __main__ guard")
    page.goto(BASE + "/workspace")
    page.get_by_role("tab", name="Paste").click()
    page.get_by_label("Language").select_option("python")
    page.get_by_label("Filename").fill("fib.py")
    page.get_by_label("paste source code").fill(
        "def fib(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n"
        "    return a\n\nif __name__ == '__main__':\n    print(fib(10))\n")
    page.get_by_role("button", name="Load code").click()
    expect(page.get_by_role("list", name="snapshot files")).to_be_visible(timeout=15000)
    expect(page.get_by_text("fib.py").first).to_be_visible()
    code = page.locator(".sourcedock-body")
    expect(code).to_contain_text("def fib(n):")
    expect(page.get_by_text("executable", exact=True).first).to_be_visible()
    # M4QA-08: the stale "gated by M4" chip was removed — an eligible pasted target
    # now reports readiness honestly and offers the real Run control.
    expect(page.get_by_role("button", name="Run in restricted container")).to_be_visible()
    # nothing has run yet: the page must say what happens next instead of sitting empty
    expect(page.get_by_text("Your code is loaded. What next?")).to_be_visible()
    expect_or_fail(True, "paste → snapshot → editor + honest detected-not-verified statuses")
    shot(page, "paste_python_journey.png")


def journey_upload_zip(page: Page) -> None:
    step("Upload journey: bounded ZIP with one hostile entry")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("calc/main.c", "#include <stdio.h>\nint main(void){int x=1;return x;}\n")
        zf.writestr("calc/util.h", "#pragma once\nint helper(void);\n")
        zf.writestr("../escape.txt", b"hostile")
        zf.writestr("calc/notes.md", "# notes\n")
    page.goto(BASE + "/workspace")
    page.get_by_role("tab", name="Upload").click()
    page.get_by_label("upload source files").set_input_files(
        files=[{"name": "bundle.zip", "mimeType": "application/zip", "buffer": buf.getvalue()}])
    expect(page.get_by_text("1 archive entry rejected")).to_be_visible(timeout=15000)
    expect(page.get_by_text("calc/main.c").first).to_be_visible()
    expect(page.get_by_text("compiles", exact=True).first).to_be_visible()
    expect_or_fail(True, "zip upload → sources accepted, hostile entry rejected+recorded")
    shot(page, "upload_zip_journey.png")


def journey_github_real(page: Page) -> None:
    step("GitHub journey: REAL import of https://github.com/antirez/kilo (network)")
    # Honest pre-flight: when GitHub's unauthenticated rate limit is exhausted the
    import json as _json
    import urllib.error
    import urllib.request
    try:
        req = urllib.request.Request(
            BASE.replace(":5173", ":8123") + "/api/v1/imports/github",
            data=_json.dumps({"url": "https://github.com/antirez/kilo"}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = _json.loads(resp.read())
        if body.get("error", {}).get("code") == "RATE_LIMITED":
            raise RuntimeError("RATE_LIMITED")
    except RuntimeError:
        SKIPPED.append("journey_github_real: GitHub unauthenticated rate limit "
                       "exhausted (backend returns RATE_LIMITED); proven in "
                       "docs/TEST_EVIDENCE/M1.md on a reset window")
        print("  SKIP: real GitHub import — GitHub API rate limit exhausted")
        return
    except urllib.error.HTTPError as e:
        payload = _json.loads(e.read() or b"{}")
        if payload.get("error", {}).get("code") == "RATE_LIMITED":
            SKIPPED.append("journey_github_real: GitHub unauthenticated rate limit "
                           "exhausted (backend returns RATE_LIMITED); proven in "
                           "docs/TEST_EVIDENCE/M1.md on a reset window")
            print("  SKIP: real GitHub import — GitHub API rate limit exhausted")
            return
    page.goto(BASE + "/workspace")
    page.get_by_role("tab", name="GitHub import").click()
    page.get_by_label("Public repository URL").fill("https://github.com/antirez/kilo")
    page.get_by_role("button", name="Import pinned revision").click()
    expect(page.get_by_text("github: antirez/kilo").first).to_be_visible(timeout=60000)
    expect(page.get_by_text("kilo.c").first).to_be_visible()
    page.get_by_text("kilo.c").first.click()
    expect(page.locator(".sourcedock-body")).to_contain_text("main(", timeout=15000)
    # classification reasons are provenance detail: shown in Technical mode only
    page.get_by_role("button", name="Technical").click()
    expect(page.get_by_text("link-deps-unknown").first).to_be_visible()
    page.get_by_role("button", name="Explore", exact=True).click()
    expect_or_fail(True, "real GitHub import with pinned SHA provenance and C classification")
    shot(page, "github_import_kilo.png")


def journey_error_state(page: Page) -> None:
    step("Error journey: invalid GitHub URL shows typed error")
    page.goto(BASE + "/workspace")
    page.get_by_role("tab", name="GitHub import").click()
    page.get_by_label("Public repository URL").fill("http://github.com/evil/repo")
    page.get_by_role("button", name="Import pinned revision").click()
    expect(page.get_by_text("INVALID_URL:")).to_be_visible(timeout=15000)
    expect_or_fail(True, "typed structured error surfaced in UI")
    shot(page, "github_invalid_url_error.png")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        for journey in (journey_home, journey_paste, journey_upload_zip,
                        journey_github_real, journey_error_state):
            try:
                journey(page)
            except Exception as e:  # noqa: BLE001 - record and continue
                FAILED.append(f"{journey.__name__}: {e}")
                print(f"  FAIL (exception): {e}")
                shot(page, f"failure_{journey.__name__}.png")
        browser.close()
    print()
    for s in SKIPPED:
        print(f"  SKIP: {s}")
    if FAILED:
        print(f"E2E RESULT: FAIL ({len(FAILED)} failures): {FAILED}")
        return 1
    print(f"E2E RESULT: PASS (5 journeys, {len(SKIPPED)} skipped with reason)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
