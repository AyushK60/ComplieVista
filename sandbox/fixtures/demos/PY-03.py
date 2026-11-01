"""PY-03 true recursion: tree-recursive fib(12) with visible frame growth and
unwinding. The trace depth cap (64) is far above this program's max depth 12,
so the full call tree is recorded honestly.
"""
CALLS = 0


def fib(n: int) -> int:
    global CALLS
    CALLS += 1
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


if __name__ == "__main__":
    result = fib(12)
    print(f"fib12={result}")
    print(f"calls={CALLS}")
