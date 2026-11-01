"""PY-01 fundamentals: variables, expressions, functions, branching.

Deterministic; expected output pinned in the demo manifest. Guided story:
watch the call/line/return events for `area` and the branch taken at runtime.
"""
BASE = 3
HEIGHT = 7


def area(base: int, height: int) -> int:
    if base <= 0 or height <= 0:
        return 0
    return base * height // 2


if __name__ == "__main__":
    tri = area(BASE, HEIGHT)
    scaled = area(BASE * 2, HEIGHT) // BASE
    kind = "valid" if tri > 0 else "degenerate"
    print(f"area={tri}")
    print(f"scaled={scaled}")
    print(f"kind={kind}")
