/* C-05 translation unit 1: implementations of the shared header. */
#include "math_utils.h"

long math_sum_series(int start, int count) {
    long total = 0;
    for (int i = 0; i < count; i++) {
        total += start + i;
    }
    return total;
}

int math_gcd(int a, int b) {
    while (b != 0) {
        int t = a % b;
        a = b;
        b = t;
    }
    return a;
}
