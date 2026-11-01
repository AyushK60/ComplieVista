"""PY-04 closure + generator suspension + exception scope.

The generator's frame suspends twice (visible in the trace as return events
without frame exit — see ADR-0008/M5QA); the closure captures `start` by
reference; the exception is caught and the finally block runs.
"""


def make_counter(start: int):
    count = start

    def bump(by: int) -> int:
        nonlocal count
        count += by
        return count
    return bump


def gen_pairs(limit: int):
    for i in range(limit):
        yield i * 2


if __name__ == "__main__":
    bump = make_counter(10)
    first = bump(5)
    second = bump(2)
    collected = []
    gen = gen_pairs(3)
    try:
        for v in gen:
            collected.append(v)
            if v == 0:
                suspended = "yes" if gen.gi_frame is not None else "no"
                next(gen)  # leave the generator suspended mid-stream
        raise ValueError("scope demo")
    except ValueError as exc:
        caught = str(exc)
    finally:
        done = "finally-ran"
    print(f"counter={first},{second}")
    print(f"pairs={','.join(str(v) for v in collected)}")
    print(f"suspended={suspended}")
    print(f"caught={caught}")
    print(f"finally={done}")
