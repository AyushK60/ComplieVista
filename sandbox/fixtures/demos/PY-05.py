"""PY-05 classes + stdlib imports + bounded concurrency.

Two worker threads write results into PREASSIGNED slots (index-addressed), so
the output is deterministic even though thread scheduling order is NOT — the
scheduling limitations are part of the guided story (join is deterministic;
interleaving inside `work` is not observed or claimed).
"""
import json
import math
import threading

RESULTS = [None, None]


def work(idx: int, value: int) -> None:
    RESULTS[idx] = {"input": value, "sqrt": math.isqrt(value),
                    "double": value * 2}


class Accumulator:
    def __init__(self) -> None:
        self.total = 0

    def add(self, amount: int) -> int:
        self.total += amount
        return self.total


if __name__ == "__main__":
    acc = Accumulator()
    acc.add(15)
    threads = [threading.Thread(target=work, args=(i, v))
               for i, v in enumerate((36, 10))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"acc={acc.total}")
    print(f"threads={json.dumps(RESULTS, sort_keys=True)}")
