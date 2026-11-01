#include <stdio.h>

/* C-01 expressions, functions, branching — the LLVM IR stage shows the
   unoptimized function bodies; OptimizationLab contrasts -O0 vs -O2. */
static int clamp(int v, int lo, int hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

static int weighted(int a, int b) {
    int sum = a + b;
    return clamp(sum / 2, 0, 100);
}

int main(void) {
    int r1 = weighted(30, 44);
    int r2 = weighted(-5, 9);
    int r3 = clamp(150, 0, 100);
    printf("r1=%d r2=%d r3=%d\n", r1, r2, r3);
    return 0;
}
