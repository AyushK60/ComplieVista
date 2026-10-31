from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page()
    page.on("console", lambda m: print("console:", m.type, m.text[:120], m.location or ""))
    page.on("pageerror", lambda e: print("PAGEERROR:", str(e)[:300]))
    page.goto("http://127.0.0.1:5173/workspace")
    page.wait_for_timeout(3000)
    b.close()
