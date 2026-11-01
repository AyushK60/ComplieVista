"""M6-C pair: conditional branch (Python side)."""
def classify(n):
    if n % 15 == 0:
        return 3
    if n % 5 == 0:
        return 2
    if n % 3 == 0:
        return 1
    return 0

def main():
    counts = [0, 0, 0, 0]
    for n in range(30):
        counts[classify(n)] += 1
    print(f"c0={counts[0]} c1={counts[1]} c2={counts[2]} c3={counts[3]}")

if __name__ == "__main__":
    main()
