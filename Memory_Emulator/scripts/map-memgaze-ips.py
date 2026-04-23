#!/usr/bin/python

import sys

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

    with open(dyninstmapfile) as mf:
        for line in mf:
            [original_addr, dyninst_addr] = line.strip().split()
            memgaze_dyninst_map[int(dyninst_addr, 16)] = int(original_addr, 16)
        memgaze_dyninst_map = dict(sorted(memgaze_dyninst_map.items(), reverse=True))

    count = 0
    with open(tracefile) as tf, open(outfile, 'w') as of:
        for line in tf:
            count += 1
            if '0x' not in line:
                of.write(line)
                continue
            splits = line.split()
            ip = int(splits[0], 16)
            orig_ip = hex(get_original_addr(ip, memgaze_dyninst_map))
            trim = ' '.join(splits[1:])
            of.write(f'{orig_ip} {trim}\n')
            if count % 10000000 == 0:
                print(f'Processed {count} lines')
if __name__ == '__main__':
    main()
