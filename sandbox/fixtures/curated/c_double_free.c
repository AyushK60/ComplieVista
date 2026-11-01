#include <stdio.h>
#include <stdlib.h>

/* M5-B curated memory-safety sample: deliberate double free. The restricted run
   reproduces the REAL glibc diagnostic on stderr and the allocator interposer
   logs the two free() calls before the abort. This shows an actual detected bug;
   it does NOT imply allocator events were exhaustively observed. */
int main(void) {
    char *buf = malloc(64);
    if (!buf) return 1;
    buf[0] = 'x';
    free(buf);
    free(buf); /* double free: glibc aborts with a real diagnostic */
    printf("unreachable\n");
    return 0;
}
