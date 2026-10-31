"""Debug: mirror journey_c AST click flow with console capture."""
from playwright.sync_api import sync_playwright

C_SRC = open("demos/m0/c_fixture.c").read()

with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 900})
    page.on("console", lambda m: print("console:", m.text[:150]))
    page.on("pageerror", lambda e: print("PAGEERROR:", str(e)[:200]))
    page.goto("http://127.0.0.1:5173/workspace")
    page.get_by_role("tab", name="Paste").click()
    page.get_by_label("Language").select_option("c")
    page.get_by_label("Filename").fill("demo.c")
    page.get_by_label("paste source code").fill(C_SRC)
    page.get_by_role("button", name="Create snapshot").click()
    page.wait_for_selector("text=Snapshot created", timeout=20000)
    page.get_by_role("button", name="Analyze with real").click()
    page.get_by_role("tab", name="ast AVAILABLE").wait_for(timeout=120000)
    page.get_by_role("tab", name="ast AVAILABLE").click()
    page.wait_for_selector(".astnode", timeout=20000)
    root = page.locator(".astnode", has_text="FunctionDecl").first
    root.locator(".tw").click()
    node = page.locator(".astnode", has_text="CompoundStmt").first
    node.wait_for(timeout=10000)
    print("node box:", node.bounding_box())
    node.click()
    page.wait_for_timeout(600)
    print("hl:", page.evaluate("document.querySelectorAll('.codeline.hl').length"))
    b.close()
