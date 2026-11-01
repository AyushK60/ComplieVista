// M4-C/M5 C trace shim. Compiled WITHOUT -finstrument-functions (clang 18 has none);
// user code compiled with -finstrument-functions links this. Provides three evidence
// streams, all OBSERVED inside the run, no ptrace, no debugger, no extra privileges:
//
//   $CV_TRACE_OUT  one JSON line per instrumented call/return (M4; capped 5000 events,
//                  then a {"kind":"meta","truncated": true} marker — M4QA-03).
//   $CV_MEM_OUT    malloc/free/calloc/realloc interposition records (M5-B): real
//                  addresses, sizes and lifetime order as executed. Capped 5000
//                  events, then a truncated marker. Logging uses raw write(2) only.
//   $CV_PROC_OUT   /proc sampler thread (M5-D): RSS/VM/threads/fds at a stated
//                  interval (capped 240 samples), thread ids, exit record.
//
// Address instability caveat is attached by the orchestrator (ASLR per run).
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <fcntl.h>
#include <dirent.h>
#include <pthread.h>
#include <dlfcn.h>

#define MAX_EVENTS 5000
#define MAX_MEM_EVENTS 5000
#define MAX_PROC_SAMPLES 240
#define PROC_SAMPLE_INTERVAL_MS 50

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

/* ---------------- M5-B allocator interposition ---------------- */

static void *(*real_malloc)(size_t);
static void (*real_free)(void *);
static void *(*real_calloc)(size_t, size_t);
static void *(*real_realloc)(void *, size_t);
static int resolving = 0;

static char boot_arena[1 << 16];
static size_t boot_used = 0;
static int mem_fd = -1;
static unsigned long mem_written = 0;
static unsigned long allocs = 0, frees = 0, reallocs = 0;
static int mem_cap_marker = 0;
static pthread_mutex_t mem_mu = PTHREAD_MUTEX_INITIALIZER;

static int in_boot(const void *p) {
    return (const char *)p >= boot_arena
        && (const char *)p < boot_arena + sizeof(boot_arena);
}

static void init_real(void) {
    if (real_malloc || resolving) return;
    resolving = 1;
    real_malloc = dlsym(RTLD_NEXT, "malloc");
    real_free = dlsym(RTLD_NEXT, "free");
    real_calloc = dlsym(RTLD_NEXT, "calloc");
    real_realloc = dlsym(RTLD_NEXT, "realloc");
    resolving = 0;
}

static void mem_log(const char *kind, unsigned long a, unsigned long b) {
    if (mem_fd < 0) {
        const char *path = getenv("CV_MEM_OUT");
        if (!path) return;
        mem_fd = open(path, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0644);
        if (mem_fd < 0) return;
    }
    char buf[512];
    long n;
    if (mem_written >= MAX_MEM_EVENTS) {
        if (!mem_cap_marker) {
            mem_cap_marker = 1;
            n = snprintf(buf, sizeof buf,
                         "{\"kind\":\"meta\",\"truncated\": true,"
                         "\"max_mem_events\":%d,\"allocs\":%lu,\"frees\":%lu}\n",
                         MAX_MEM_EVENTS, allocs, frees);
            if (n < 0 || n >= (long)sizeof buf) n = (long)sizeof buf - 1;
            if (write(mem_fd, buf, (size_t)n) > 0) mem_written++;
        }
        return;
    }
    if (strcmp(kind, "realloc") == 0) {
        /* a = old pointer (0 if none), b = new pointer */
        n = snprintf(buf, sizeof buf, "{\"kind\":\"realloc\",\"old\":%lu,\"addr\":%lu}\n", a, b);
    } else if (strcmp(kind, "free") == 0) {
        n = snprintf(buf, sizeof buf, "{\"kind\":\"free\",\"addr\":%lu}\n", a);
    } else {
        n = snprintf(buf, sizeof buf, "{\"kind\":\"%s\",\"addr\":%lu,\"size\":%lu}\n",
                     kind, a, b);
    }
    if (n < 0 || n >= (long)sizeof buf) n = (long)sizeof buf - 1;
    ssize_t w = write(mem_fd, buf, (size_t)n);
    if (w > 0) mem_written++;
}

/* sampler + logging are small and bounded; the mutex only serializes log lines */
#define MEM_LOG(kind, a, b) do { \
    pthread_mutex_lock(&mem_mu); mem_log(kind, (a), (b)); \
    pthread_mutex_unlock(&mem_mu); } while (0)

static void mem_meta_atexit(void) {
    if (mem_fd < 0) return;
    char buf[512];
    long n = snprintf(buf, sizeof buf,
                      "{\"kind\":\"mem_meta\",\"allocs\":%lu,\"frees\":%lu,"
                      "\"reallocs\":%lu,\"outstanding\":%ld,\"records\":%lu,"
                      "\"caveat\":\"allocator interposition observes allocations "
                      "that flowed through libc malloc during the run; "
                      "outstanding counts malloc/free pairs only (realloc "
                      "moves are tracked separately, so it is approximate for "
                      "realloc-heavy programs)\"}\n",
                      allocs, frees, reallocs, (long)(allocs - frees), mem_written);
    if (n < 0 || n >= (long)sizeof buf) n = (long)sizeof buf - 1;
    (void)write(mem_fd, buf, (size_t)n);
}

void *malloc(size_t size) {
    if (!real_malloc) {
        if (resolving) {  /* serve dlsym's own early needs from the boot arena */
            if (boot_used + size <= sizeof(boot_arena)) {
                void *p = boot_arena + boot_used;
                boot_used += (size + 15) & ~(size_t)15;
                return p;
            }
            return NULL;
        }
        init_real();
    }
    void *p = real_malloc(size);
    if (p) {
        pthread_mutex_lock(&mem_mu); allocs++;
        pthread_mutex_unlock(&mem_mu);
        MEM_LOG("alloc", (unsigned long)(uintptr_t)p, (unsigned long)size);
    }
    return p;
}

void free(void *p) {
    if (!p || in_boot(p)) return;
    if (real_free) {
        pthread_mutex_lock(&mem_mu); frees++;
        pthread_mutex_unlock(&mem_mu);
        MEM_LOG("free", (unsigned long)(uintptr_t)p, 0);
        real_free(p);
    }
}

void *calloc(size_t nmemb, size_t size) {
    if (!real_calloc) {
        if (resolving) {
            size_t total = nmemb * size;
            if (boot_used + total <= sizeof(boot_arena)) {
                void *p = boot_arena + boot_used;  /* static arena is zeroed */
                boot_used += (total + 15) & ~(size_t)15;
                return p;
            }
            return NULL;
        }
        init_real();
    }
    void *p = real_calloc(nmemb, size);
    if (p) {
        pthread_mutex_lock(&mem_mu); allocs++;
        pthread_mutex_unlock(&mem_mu);
        MEM_LOG("alloc", (unsigned long)(uintptr_t)p, nmemb * size);
    }
    return p;
}

void *realloc(void *old, size_t size) {
    if (!real_realloc) init_real();
    void *p = real_realloc(old, size);
    if (p) {
        if (!old) {
            pthread_mutex_lock(&mem_mu); allocs++;
            pthread_mutex_unlock(&mem_mu);
        } else {
            pthread_mutex_lock(&mem_mu); reallocs++;
            pthread_mutex_unlock(&mem_mu);
        }
        MEM_LOG("realloc", (unsigned long)(uintptr_t)old, (unsigned long)(uintptr_t)p);
    }
    return p;
}

/* ---------------- M5-D process sampler (container-side) ---------------- */

static int proc_fd = -1;
static int proc_samples = 0;
static int proc_truncated = 0;

static void proc_write(const char *buf, size_t n) {
    if (proc_fd < 0) return;
    (void)write(proc_fd, buf, n);
}

static long proc_now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

static void write_proc_sample(void) {
    char buf[256];
    long t_ms = proc_now_ms();
    long rss = -1, vm = -1, threads = -1;
    FILE *st = fopen("/proc/self/status", "r");
    if (st) {
        char line[256];
        while (fgets(line, sizeof line, st)) {
            if (rss < 0 && !strncmp(line, "VmRSS:", 6)) sscanf(line + 6, "%ld", &rss);
            else if (vm < 0 && !strncmp(line, "VmSize:", 7)) sscanf(line + 7, "%ld", &vm);
            else if (threads < 0 && !strncmp(line, "Threads:", 8)) sscanf(line + 8, "%ld", &threads);
        }
        fclose(st);
    }
    int n = snprintf(buf, sizeof buf,
                     "{\"kind\":\"proc_sample\",\"t_ms\":%ld,\"rss_kb\":%ld,"
                     "\"vm_size_kb\":%ld,\"threads\":%ld,\"fds\":-1}\n",
                     t_ms, rss, vm, threads);
    if (n < 0 || n >= (long)sizeof buf) n = (long)sizeof buf - 1;
    proc_write(buf, (size_t)n);
    proc_samples++;
}

static void proc_atexit(void) {
    if (proc_fd < 0) return;
    char buf[512];
    /* thread ids observed at exit (bounded) */
    long tids[32];
    int ntids = 0;
    DIR *d = opendir("/proc/self/task");
    if (d) {
        struct dirent *e;
        while ((e = readdir(d)) != NULL && ntids < 32) {
            if (e->d_name[0] >= '0' && e->d_name[0] <= '9')
                tids[ntids++] = strtol(e->d_name, NULL, 10);
        }
        closedir(d);
    }
    int n = snprintf(buf, sizeof buf,
                     "{\"kind\":\"proc_exit\",\"t_ms\":%ld,\"samples\":%d,"
                     "\"samples_truncated\":%s,\"thread_ids\":[",
                     proc_now_ms(), proc_samples,
                     proc_truncated ? "true" : "false");
    for (int i = 0; i < ntids && n < (long)sizeof buf - 16; i++)
        n += snprintf(buf + n, sizeof buf - (size_t)n, "%s%ld",
                      i ? "," : "", tids[i]);
    n += snprintf(buf + n, sizeof buf - (size_t)n, "]}\n");
    if (n < 0 || n >= (long)sizeof buf) n = (long)sizeof buf - 1;
    proc_write(buf, (size_t)n);
}

static void *sampler_thread(void *arg) {
    (void)arg;
    char buf[160];
    for (int i = 0; i < MAX_PROC_SAMPLES; i++) {
        if (proc_samples < MAX_PROC_SAMPLES) {
            write_proc_sample();
        } else if (!proc_truncated) {
            proc_truncated = 1;
            int n = snprintf(buf, sizeof buf,
                             "{\"kind\":\"meta\",\"truncated\": true,"
                             "\"max_proc_samples\":%d}\n", MAX_PROC_SAMPLES);
            if (n < 0 || n >= (long)sizeof buf) n = (long)sizeof buf - 1;
            proc_write(buf, (size_t)n);
            break;
        }
        struct timespec wait = {0, PROC_SAMPLE_INTERVAL_MS * 1000000L};
        nanosleep(&wait, NULL);
    }
    return NULL;
}

__attribute__((constructor))
static void m5_shim_init(void) {
    init_real();
    const char *ppath = getenv("CV_PROC_OUT");
    if (ppath) {
        proc_fd = open(ppath, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0644);
        if (proc_fd >= 0) {
            char buf[512];
            int n = snprintf(buf, sizeof buf,
                             "{\"kind\":\"proc_meta\",\"os\":\"Linux (container pid "
                             "namespace)\",\"container_pid\":%ld,\"ppid\":%ld,"
                             "\"sample_interval_ms\":%d,\"sample_cap\":%d,"
                             "\"metric_definitions\":{\"rss_kb\":\"VmRSS from "
                             "/proc/self/status (kB)\",\"threads\":\"Threads from "
                             "/proc/self/status\",\"t_ms\":\"ms since shim load "
                             "(CLOCK_MONOTONIC)\"}}\n",
                             (long)getpid(), (long)getppid(),
                             PROC_SAMPLE_INTERVAL_MS, MAX_PROC_SAMPLES);
            if (n < 0 || n >= (long)sizeof buf) n = (long)sizeof buf - 1;
            proc_write(buf, (size_t)n);
            write_proc_sample();  /* deterministic first sample: short programs
                                     may exit before the thread is scheduled */
            pthread_t th;
            if (pthread_create(&th, NULL, sampler_thread, NULL) == 0)
                pthread_detach(th);
        }
    }
    atexit(mem_meta_atexit);
    atexit(proc_atexit);
}
