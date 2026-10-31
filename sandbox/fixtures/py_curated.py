# M0 curated Docker fixture (Python): deterministic output, no side effects.
M0_SCALE = 3


def scale_and_adjust(base, limit):
    scaled = base * M0_SCALE
    if scaled > limit:
        return limit
    return scaled


total = 0
for value in [1, 2, 3, 4]:
    total += scale_and_adjust(value, 10)
print(f"total={total}")
