"""M6-C pair: list traversal sum (Python side)."""
def main():
    values = [(i * 37) % 101 for i in range(1000)]
    total = 0
    for v in values:
        total += v
    print(f"total={total}")

if __name__ == "__main__":
    main()
