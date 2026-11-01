"""M6-C pair: sorting (Python side, same algorithm)."""
def main():
    v = [(i * 89 + 13) % 211 for i in range(200)]
    for i in range(1, 200):
        key = v[i]
        j = i - 1
        while j >= 0 and v[j] > key:
            v[j + 1] = v[j]
            j -= 1
        v[j + 1] = key
    checksum = 0
    for x in v:
        checksum = (checksum * 31 + x) % 1000000007
    print(f"sorted={checksum}")

if __name__ == "__main__":
    main()
