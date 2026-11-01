#include <stdio.h>

/* C-02 preprocessor + conditional build + loop (CFG: header/exit blocks).
   The preprocessor stage shows MACRO expansion; DEMO_MODE selects the build
   path at compile time (recorded in flags, not run-time branching). */
#define DEMO_MODE 2
#define SCALE(x) ((x) * DEMO_MODE)

int main(void) {
    long acc = 0;
#if DEMO_MODE > 1
    for (int i = 1; i <= 10; i++) {
        if (i % 2 == 0) {
            acc += SCALE(i);
        } else {
            acc += i;
        }
    }
#else
    acc = -1;
#endif
    printf("acc=%ld\n", acc);
    return 0;
}
