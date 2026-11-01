#include <stdio.h>

/* C-03 pointers and arrays on the stack: swap through pointers, bounded
   pointer arithmetic (never out of bounds), array decay observed in IR. */
static void swap(int *a, int *b) {
    int tmp = *a;
    *a = *b;
    *b = tmp;
}

static long sum_slice(const int *values, int len) {
    long total = 0;
    for (int i = 0; i < len; i++) {
        total += *(values + i);  /* in-bounds pointer arithmetic */
    }
    return total;
}

int main(void) {
    int arr[5] = {4, 1, 7, 2, 9};
    int *front = &arr[0];
    int *back = &arr[4];
    swap(front, back);
    long total = sum_slice(arr, 5);
    printf("first=%d last=%d sum=%ld\n", arr[0], arr[4], total);
    return 0;
}
