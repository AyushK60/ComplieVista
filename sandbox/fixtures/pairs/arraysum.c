#include <stdio.h>
/* M6-C pair: array traversal sum (fixed array, defined behavior). */
int main(void) {
    long values[1000];
    for (int i = 0; i < 1000; i++) values[i] = (i * 37) % 101;
    long total = 0;
    for (int i = 0; i < 1000; i++) total += values[i];
    printf("total=%ld\n", total);
    return 0;
}
