#include <stdio.h>
/* M6-C pair: sorting (insertion sort on a fixed 200-element permutation). */
int main(void) {
    long v[200];
    for (int i = 0; i < 200; i++) v[i] = (i * 89 + 13) % 211;
    for (int i = 1; i < 200; i++) {
        long key = v[i];
        int j = i - 1;
        while (j >= 0 && v[j] > key) { v[j + 1] = v[j]; j--; }
        v[j + 1] = key;
    }
    long long checksum = 0;
    for (int i = 0; i < 200; i++) checksum = (checksum * 31 + v[i]) % 1000000007LL;
    printf("sorted=%lld\n", checksum);
    return 0;
}
