#include <stdio.h>
/* M6-C pair: conditional branch. Classify 0..29 by modulo rules. */
static int classify(int n) {
    if (n % 15 == 0) return 3;
    if (n % 5 == 0) return 2;
    if (n % 3 == 0) return 1;
    return 0;
}
int main(void) {
    int counts[4] = {0, 0, 0, 0};
    for (int n = 0; n < 30; n++) {
        counts[classify(n)]++;
    }
    printf("c0=%d c1=%d c2=%d c3=%d\n", counts[0], counts[1], counts[2], counts[3]);
    return 0;
}
