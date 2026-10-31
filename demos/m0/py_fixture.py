"""M0 Python fixture: deterministic, mirrors the C fixture.

Static inspection uses tokenize/ast/compile/dis ONLY and must never execute this module.
Expected stdout if ever (manually, curated context only) run: "total=28"
"""

M0_SCALE = 3


def scale_and_adjust(base: int, limit: int) -> int:
    scaled = base * M0_SCALE
    if scaled > limit:
        return limit
    return scaled


def main() -> None:
    values = [1, 2, 3, 4]
    total = 0
    for value in values:
        total += scale_and_adjust(value, 10)
    print(f"total={total}")


if __name__ == "__main__":
    main()
