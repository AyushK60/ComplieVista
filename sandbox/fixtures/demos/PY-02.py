"""PY-02 loops and collections: accumulator over a list with filtering.

Bytecode interest: FOR_ITER/COMPARE_OP jumps; the loop is visible in the
recorded line-event stream.
"""
NUMBERS = [12, 7, 3, 20, 15, 8, 1, 33]


def accumulate(values: list[int]) -> dict:
    total = 0
    evens = []
    for v in values:
        total += v
        if v % 2 == 0:
            evens.append(v)
    return {"total": total, "evens": evens, "count": len(evens)}


if __name__ == "__main__":
    r = accumulate(NUMBERS)
    print(f"total={r['total']}")
    print(f"evens={','.join(str(x) for x in r['evens'])}")
    print(f"count={r['count']}")
