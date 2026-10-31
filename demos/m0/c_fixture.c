/* M0 C fixture: deterministic, exercises expressions, function, branch, loop, array, macro.
   Expected stdout when compiled and run: "total=28\n" */
#include <stdio.h>

#define M0_SCALE 3

static int scale_and_adjust(int base, int limit) {
    int scaled = base * M0_SCALE;
    if (scaled > limit) {
        return limit;
    }
    return scaled;
}

int main(void) {
    int values[4] = {1, 2, 3, 4};
    int total = 0;
    for (int i = 0; i < 4; i = i + 1) {
        total = total + scale_and_adjust(values[i], 10);
    }
    printf("total=%d\n", total);
    return 0;
}
