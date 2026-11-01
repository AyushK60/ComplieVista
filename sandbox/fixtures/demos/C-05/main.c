/* C-05 translation unit 2 (primary): main TU links against math_utils.c via
   the shared header. The linker (not the preprocessor) resolves the cross-TU
   symbols — visible in the linked binary's symbol table. */
#include <stdio.h>
#include "math_utils.h"

int main(void) {
    long series = math_sum_series(5, 10);
    int gcd = math_gcd(48, 36);
    printf("series=%ld gcd=%d\n", series, gcd);
    return 0;
}
