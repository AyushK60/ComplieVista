"""M6-C pair: arithmetic add (Python side). Matches add.c semantics."""
def main():
    total = 0
    for i in range(100000):
        total += i % 7
    print(f"sum={total}")

if __name__ == "__main__":
    main()
