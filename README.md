# sgxpagefaulttrace-bpf

Simple BPF tool to trace SGX page faults. This tool uses BPF and traces the Intel SGX driver's `sgx_fault_page` function to record counts of the total number of EPC page faults and the number of distinct pages that fault during a specified interval.  

## Requirements

This requires `bcc`/`bcc-tools`/`bpfcc-tools` installed, e.g.

```
sudo apt-get install bpfcc-tools
```

for Ubuntu. See https://github.com/iovisor/bcc/blob/master/INSTALL.md for full instructions.

## Usage

```
usage: sgxpagetrace_ebpf.py [-h] [-i INTERVAL] [-c]

Trace SGX page faults.

optional arguments:
  -h, --help            show this help message and exit
  -i INTERVAL, --interval INTERVAL
                        measurement and output interval, in seconds
  -c, --cumulative      do not clear counts at each interval
```

## Example

```
$ sudo ./sgxpagetrace_ebpf.py -i 1
Tracing... Ctrl-C to end.
[13:25:46] PAGES        SIZE (MB)    UNACCOUNTED  FAULTS       BANDWIDTH (MB)
[13:31:37] 0            0.00         0            0            0.00        
[13:31:38] 0            0.00         0            0            0.00        
[13:31:39] 0            0.00         0            0            0.00        
[13:31:40] 0            0.00         0            0            0.00        
[13:31:41] 23164        90.48        0            39113        152.79      
[13:31:43] 23821        93.05        0            56052        218.95      
[13:31:44] 23825        93.07        0            57394        224.20      
[13:31:45] 23821        93.05        0            60415        236.00      
[13:31:46] 27976        109.28       0            60312        235.59      
[13:31:47] 24257        94.75        0            61896        241.78      
[13:31:48] 30227        118.07       0            63521        248.13      
[13:31:49] 24077        94.05        0            63569        248.32
[...]
```

The output contains six columns:

| Column  | Description |
| ------------- | ------------- |
| [hh:mm:ss] | Current time. |
| PAGES | Number of distinct pages that faulted in the specified interval. |
| SIZE (MB) | Cumulative size of PAGES in Megabyte. |
| UNACCOUNTED | Number of pages that faulted but that could not be accounted for as part of PAGES. This can happen as the tool uses a bitmap to keep track of previously seen pages. The size of the bitmap is restricted (currently 8 GB). Unaccounted pages can occur either for enclaves larger than 8GB or when multipe enclaves are run concurrently. |
| FAULTS | Total number of page faults in the specified interval. |
| BANDWIDTH (MB) | Cumulative size of paged in pages in Megabyte. |

## Known issues

1. Currently the maximum supported enclave size is 8GB (See comment in BPF script).
2. The tool currently does not handle page faults from different enclaves within the same interval well. If the virtual address ranges of these enclaves happen to overlap, the results in the PAGES column might be inaccurate. If they do not overlap, page faults for one enclave might be counted as UNACCOUNTED.
