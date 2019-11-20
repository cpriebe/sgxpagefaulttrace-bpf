#!/usr/bin/python

from bcc import BPF
from ctypes import c_int
from time import sleep, strftime
import argparse

SGX_FAULT_BPF = """
#include <uapi/linux/ptrace.h>

enum stat_types {
    S_FAULTS = 1,
    S_FIRST_PAGE = 2,
    S_PAGES = 3,
    S_UNACCOUNTED = 4,
    S_MAXSTAT
};

BPF_ARRAY(stats, u64, S_MAXSTAT);

static void stats_increment(int key) {
    u64 *leaf = stats.lookup(&key);
    if (leaf) (*leaf)++;
}

/* Array sizes for max supported enclave size:
 * 128GB: 524288
 *  64GB: 262144
 *  32GB: 131072
 *  16GB:  65536
 *  8GB:   32768
 * Example:
 * For bitmap to be big enough for enclaves up to 128 GB: 524288 * 64 * 4096
 *
 * Large arrays take longer to clear and therefore might only work accurately
 * with larger intervals, so support 8GB for now.
 */
BPF_ARRAY(pages_seen, u64, 32768);

/* Returns -1 if address could not be looked up. Otherwise returns 1 if page has
 * been seen before, or 0 if not.
 */
static int page_seen_test_and_set(struct pt_regs *ctx, u64 addr) {
    u64 addr_idx = addr / 4096;

    int stat = S_FIRST_PAGE;
    u64 *first_page_idx = stats.lookup(&stat);
    if (!first_page_idx) return -1;

    if (!*first_page_idx)
        (*first_page_idx) = addr_idx;

    // We don't know the enclave range, so use first observed address as pivot.
    // First bit in bitmap represents first observed page.
    u64 idx;
    if (addr_idx >= *first_page_idx)
        idx = addr_idx - *first_page_idx;
    else
        // Wrap around, pages lower than the first page are at end of bitmap
        idx = 32768 * 64 - (*first_page_idx - addr_idx);

    // This can happen if the enclave is larger than what the pages_seen array
    // can hold, or if there are multiple enclaves used at once.
    if (idx > 32768 * 64) return -1;

    // Every u64 in the array represents 64 pages
    int idx_blk = (idx / 64);
    u64 *page_blk = pages_seen.lookup(&idx_blk);
    if (!page_blk) return -1;

    int res = ((*page_blk) & ((u64) 1 << (idx % 64))) ? 1 : 0;
    (*page_blk) |= (u64) 1 << (idx % 64);

    return res;
}

int sgx_fault_page_probe0(struct pt_regs *ctx, void *vma, unsigned long addr, unsigned int flags)
{
    stats_increment(S_FAULTS);

    int res = page_seen_test_and_set(ctx, addr);
    if (res == -1)
        stats_increment(S_UNACCOUNTED);
    else if (res == 0)
        stats_increment(S_PAGES);

    return 0;
}
"""


# Stat indexes
S_FAULTS = c_int(1)
S_FIRST_PAGE = c_int(2)
S_PAGES = c_int(3)
S_UNACCOUNTED= c_int(4)

parser = argparse.ArgumentParser(description="Trace SGX page faults.",
formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("-i", "--interval", default=1, type=int,
  help="measurement and output interval, in seconds")
parser.add_argument("-c", "--cumulative", action="store_true",
  help="do not clear counts at each interval")
args = parser.parse_args()

# Load BPF program
b = BPF(text=SGX_FAULT_BPF)
b.attach_kprobe(event="sgx_fault_page", fn_name="sgx_fault_page_probe0")

print("Tracing... Ctrl-C to end.")

# output
print("[%s] %-12s %-12s %-12s %-12s %-12s" % (strftime("%H:%M:%S"), "PAGES", "SIZE (MB)", "UNACCOUNTED", "FAULTS", "BANDWIDTH (MB)"))
while (1):
    try:
        sleep(args.interval)
    except KeyboardInterrupt:
        exit()

    pages = b["stats"][S_PAGES].value
    pgsize = pages/256.0
    faults = b["stats"][S_FAULTS].value
    bandwidth = faults/256.0
    unaccounted = b["stats"][S_UNACCOUNTED].value
    print("[%s] %-12s %-12.2f %-12s %-12s %-12.2f" % (strftime("%H:%M:%S"), str(pages), pgsize, unaccounted, str(faults), bandwidth))
    if not args.cumulative:
        b["stats"].clear()
        b["pages_seen"].clear()
