"""M6-C pair: recursion (Python side)."""
def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

def main():
    print(f"fib20={fib(20)}")

if __name__ == "__main__":
    main()
