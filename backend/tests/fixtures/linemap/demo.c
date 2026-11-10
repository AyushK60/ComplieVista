#include <stdio.h>

static int square(int x) {
    return x * x;
}

int sum_squares(int n) {
    int total = 0;
    for (int i = 0; i < n; i++) {
        total += square(i);
    }
    return total;
}

int main(void) {
    int unused = 42;
    printf("%d\n", sum_squares(10));
    return 0;
}
