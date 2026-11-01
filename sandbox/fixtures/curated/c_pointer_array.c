#include <stdio.h>
#include <stdlib.h>

/* M5-B curated sample: array + pointer + malloc/free lifetime.
   Used for the curated debug profile (gdb frame/variable/pointer observations)
   and for pasted runs (allocator interposition only). */

struct point { int x; int y; };

static int process(struct point *p, int *values, int n) {
    int total = 0;
    for (int i = 0; i < n; i++) {
        total += values[i];
    }
    p->y = total;
    return total;
}

int main(void) {
    int arr[4] = {10, 20, 30, 40};
    int *mid = &arr[2];
    int *heap = malloc(4 * sizeof(int));
    struct point p = {2, 3};
    if (heap) {
        for (int i = 0; i < 4; i++) heap[i] = arr[i] + i;
    }
    int total = process(&p, arr, 4);
    printf("mid=%p total=%d first_heap=%d\n", (void *)mid, total,
           heap ? heap[0] : -1);
    free(heap);
    return 0;
}
