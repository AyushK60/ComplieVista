// M4-C: -finstrument-functions trace shim. Compiled WITHOUT the flag (clang 18 has
// no -fno-instrument-functions); user code compiled with -finstrument-functions
// links this. Emits one JSON line per call/return to the file named by $CV_TRACE_OUT.
// M4QA-03: the event stream is capped at MAX_EVENTS in-band — after the cap the
// shim writes a single {"kind":"meta","truncated": true,...} marker and stops, so a
// call-dense program cannot grow the host-side trace file without bound.
// No ptrace, no debugger, no extra privileges — real call/return observations from
// the compiler's own instrumentation.
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>

#define MAX_EVENTS 5000

static FILE *trace_file = NULL;
static unsigned long events_written = 0;
static int cap_marker_written = 0;

static void trace_write(const char *kind, void *fn) {
    if (!trace_file) {
        const char *path = getenv("CV_TRACE_OUT");
        if (!path) return;
        trace_file = fopen(path, "w");
        if (!trace_file) return;
        setvbuf(trace_file, NULL, _IOLBF, 0);
    }
    if (events_written >= MAX_EVENTS) {
        if (!cap_marker_written) {
            cap_marker_written = 1;
            fprintf(trace_file,
                    "{\"kind\":\"meta\",\"truncated\": true,\"max_events\":%d}\n",
                    MAX_EVENTS);
            fflush(trace_file);
        }
        return;
    }
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    fprintf(trace_file, "{\"kind\":\"%s\",\"addr\":%lu,\"ts_ms\":%lld.%03ld}\n",
            kind, (unsigned long)(uintptr_t)fn,
            (long long)ts.tv_sec, ts.tv_nsec / 1000000);
    events_written++;
}

void __cyg_profile_func_enter(void *fn, void *call_site)
    __attribute__((no_instrument_function));
void __cyg_profile_func_exit(void *fn, void *call_site)
    __attribute__((no_instrument_function));

void __cyg_profile_func_enter(void *fn, void *call_site) {
    (void)call_site;
    trace_write("call", fn);
}
void __cyg_profile_func_exit(void *fn, void *call_site) {
    (void)call_site;
    trace_write("return", fn);
}
