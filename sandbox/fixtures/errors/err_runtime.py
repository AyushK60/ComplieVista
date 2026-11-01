"""Runtime error fixture: ZeroDivisionError escapes to the harness and the
recorded trace shows the exception event and termination honestly."""
def divide(a, b):
    return a // b


if __name__ == "__main__":
    print(divide(6, 3))
    print(divide(1, 0))
    print("unreachable")
