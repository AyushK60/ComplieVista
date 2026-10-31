import ast

p = "e2e/m3_journeys.py"
s = open(p, encoding="utf-8").read()

m4_journeys = '''

def journey_m4_execution(page: Page) -> None:
    """M4: real execution of pasted Python + C, recorded replay timeline,
    GitHub-origin blocked."""
    step("M4: paste Python -> Run -> real trace replay timeline")
    paste_and_analyze(page, "python", "fib_run.py",
                      "def fib(n):\\n    a, b = 0, 1\\n    for _ in range(n):\\n"
                      "        a, b = b, a + b\\n    return a\\n\\n"
                      "if __name__ == '__main__':\\n    print(fib(10))\\n")
    page.get_by_role("button", name="Run in restricted container").click()
    expect(page.get_by_text("Recorded replay")).to_be_visible(timeout=120000)
    expect(page.locator(".replay-banner")).to_contain_text("exit=0")
    page.get_by_role("button", name="jump to end").click()
    page.get_by_role("button", name="jump to start").click()
    page.get_by_role("button", name="step forward").click()
    page.get_by_role("button", name="step back").click()
    ok("recorded replay timeline: play/pause/step/jump controls over real trace")
    shot(page, "m4_python_execution.png")

    step("M4: paste C -> Run -> real build + instrumented run")
    page.goto(BASE + "/workspace")
    page.get_by_role("tab", name="Paste").click()
    page.get_by_label("Language").select_option("c")
    page.get_by_label("Filename").fill("calls.c")
    page.get_by_label("paste source code").fill(
        "#include <stdio.h>\\nstatic int adjust(int b, int l) {\\n"
        "    return b > l ? l : b;\\n}\\n"
        "int main(void) {\\n    printf(\\"total=%d\\\\n\\", adjust(4, 2));\\n    return 0;\\n}\\n")
    page.get_by_role("button", name="Create snapshot").click()
    expect(page.get_by_text("Snapshot created")).to_be_visible(timeout=20000)
    page.get_by_role("button", name="Run in restricted container").click()
    expect(page.get_by_text("Recorded replay")).to_be_visible(timeout=120000)
    expect(page.locator(".replay-banner")).to_contain_text("exit=0")
    page.locator("details summary", has_text="Program output").click()
    expect(page.locator(".excerpt").last).to_contain_text("total=2", timeout=10000)
    ok("C build + run with real stdout in restricted container")
    shot(page, "m4_c_execution.png")

    step("M4: GitHub-imported code stays blocked from execution")
    page.goto(BASE + "/workspace")
    page.get_by_role("tab", name="GitHub import").click()
    page.get_by_label("Public repository URL").fill("https://github.com/antirez/kilo")
    page.get_by_role("button", name="Import pinned revision").click()
    expect(page.get_by_text("kilo.c").first).to_be_visible(timeout=60000)
    assert page.get_by_role("button", name="Run in restricted container").count() == 0, \\
        "GitHub-imported code must not be runnable (M4-A)"
    ok("GitHub-imported code: no Run button (fail-closed)")
    shot(page, "m4_github_no_run.png")


def journey_m4_adversarial_ui(page: Page) -> None:
    step("M4 adversarial: infinite loop times out, UI shows TIMEOUT")
    paste_and_analyze(page, "python", "spinui.py",
                      "if __name__ == '__main__':\\n    while True:\\n        pass\\n")
    page.get_by_role("button", name="Run in restricted container").click()
    expect(page.get_by_text("Execution timeout", exact=False).first).to_be_visible(timeout=120000)
    ok("infinite loop contained by wall-clock timeout; honest TIMEOUT shown")
    shot(page, "m4_timeout.png")
'''

# insert before def main
anchor = "def main() -> int:"
assert anchor in s
s = s.replace(anchor, m4_journeys + "\n" + anchor, 1)
# register in the journey list
old_list = """        for journey in (journey_c_graph, journey_python_graph,
                        journey_large_and_error, journey_viewports):"""
new_list = """        for journey in (journey_c_graph, journey_python_graph,
                        journey_large_and_error, journey_viewports,
                        journey_m4_execution, journey_m4_adversarial_ui):"""
assert old_list in s
s = s.replace(old_list, new_list)
s = s.replace('print("E2E RESULT: PASS (5 M3 journeys)")',
              'print("E2E RESULT: PASS (6 journeys incl. M4)")')
open(p, "w", encoding="utf-8", newline="\n").write(s)
import ast
ast.parse(s)
print("M4 journeys added, syntax OK")
