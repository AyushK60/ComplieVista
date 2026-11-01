#include <stdio.h>

/* M6-C pair: arithmetic add. Deterministic, defined behavior, bounded work. */
int main(void) {
    long sum = 0;
    for (long i = 0; i < 100000L; i++) {
        sum += i % 7;
    }
    printf("sum=%ld\n", sum);
    return 0;
}
