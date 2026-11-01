"""M5-C curated sample: reference aliasing, a reference cycle, exception cleanup
(frame lifetime), one observed child process, and a secret-named binding.

Pasted-run fixture: the trace harness records frame snapshots with id()-based
identity (alias), the bounded object graph (the cycle), tracemalloc + gc records,
and the sampler records the forked child while it is alive.
"""
import os
import sys


def build_shared():
    box = {"value": [1, 2, 3]}
    alias = box                      # two names, one object (observed identity)
    box["cycle"] = box               # reference cycle (observed in object graph)
    return box, alias


def raiser():
    raise ValueError("cleanup path")


def cleanup_witness():
    try:
        raiser()
    except ValueError as exc:
        return f"caught {exc}"
    finally:
        witness = "finally ran"      # frame lifetime visible in trace returns
    return None


def child_process_case() -> int:
    pid = os.fork()
    if pid == 0:
        import time
        time.sleep(0.5)              # alive long enough to be sampled
        os._exit(7)
    _, status = os.waitpid(pid, 0)
    return status


if __name__ == "__main__":
    box, alias = build_shared()
    password = "correct horse battery staple"   # secret-name rule: never previewed
    box["value"].append(4)
    print("alias-same:", box is alias)
    print("cleanup:", cleanup_witness())
    status = child_process_case()
    print("child-status:", os.waitstatus_to_exitcode(status))
    print("password-len:", len(password))
