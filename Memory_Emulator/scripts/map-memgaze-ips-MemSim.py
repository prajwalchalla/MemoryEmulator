#!/usr/bin/python

import sys
import csv

lookup_cache = {}

def find_nearest_small_value(key, sorted_li):
    for elem in sorted_li:
        if elem <= key:
            return elem


def get_original_addr(dyninst_addr, memgaze_dyninst_map):
    global lookup_cache
    if dyninst_addr not in lookup_cache.keys():
        nearest_val = find_nearest_small_value(dyninst_addr, list(memgaze_dyninst_map.keys()))
        if nearest_val is None:
            lookup_cache[dyninst_addr] = dyninst_addr
        else:
            addr = memgaze_dyninst_map[nearest_val]
            lookup_cache[dyninst_addr] = addr + (dyninst_addr - nearest_val)
    return lookup_cache[dyninst_addr]

def main():
    dyninstmapfile = sys.argv[1]
    tracefile = sys.argv[2]
    outfile = sys.argv[3]

    memgaze_dyninst_map = {}

    # Read and parse the mapping file
    with open(dyninstmapfile) as mf:
        for line in mf:
            original_addr, dyninst_addr = line.strip().split()
            memgaze_dyninst_map[int(dyninst_addr, 16)] = int(original_addr, 16)
        memgaze_dyninst_map = dict(sorted(memgaze_dyninst_map.items(), reverse=True))

    count = 0

    # Process the CSV trace file
    with open(tracefile) as tf:
        reader = csv.reader(tf)
        with open(outfile, 'w', newline='') as of:
            writer = csv.writer(of)
            for row in reader:
                count += 1

                # Skip the row if `row[0]` is empty
                if not row or not row[0].strip():
                    continue
                
                # If the row doesn't contain an address (0x), write it unchanged
                if not any('0x' in cell for cell in row):
                    writer.writerow(row)
                    continue
                # Process the first column as the address
                ip = int(row[0], 16)
                orig_ip = hex(get_original_addr(ip, memgaze_dyninst_map))
                # Add the new value as the last column
                row.append(orig_ip)
                writer.writerow(row)
                # Print progress every 10 million lines
                if count % 10000000 == 0:
                    print(f'Processed {count} lines')


if __name__ == '__main__':
    main()
