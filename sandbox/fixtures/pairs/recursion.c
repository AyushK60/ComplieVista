#include <stdio.h>
/* M6-C pair: recursion (tree-recursive fib; defined, bounded). */
static long fib(long n) {
    if (n < 2) return n;
    return fib(n - 1) + fib(n - 2);
}
int main(void) {
    printf("fib20=%ld\n", fib(20));
    return 0;
}
