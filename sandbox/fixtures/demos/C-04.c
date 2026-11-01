#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* C-04 structs + dynamic memory: real malloc/free on the correct path.
   Every allocation is freed; the allocator interposition (M5) records the
   lifetime, and the program checks the NULL return (no UB on OOM). */
typedef struct {
    int id;
    int score;
    char tag[8];
} record_t;

int main(void) {
    record_t *records = malloc(3 * sizeof(record_t));
    if (!records) {
        fprintf(stderr, "allocation failed\n");
        return 1;
    }
    memset(records, 0, 3 * sizeof(record_t));
    for (int i = 0; i < 3; i++) {
        records[i].id = i + 1;
        records[i].score = (i + 1) * 11;
        strcpy(records[i].tag, "ok");
    }
    int total = 0;
    for (int i = 0; i < 3; i++) {
        total += records[i].score;
    }
    printf("total=%d last=%s\n", total, records[2].tag);
    free(records);
    return 0;
}
