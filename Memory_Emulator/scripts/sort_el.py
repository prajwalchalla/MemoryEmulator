import sys
import pprint

el_file = sys.argv[1]

el_data = []

with open(el_file) as elfd:
    for line in elfd.readlines():
        splits = line.strip().split()
        src, dest, weight = int(splits[0]), int(splits[1]), int(splits[2])
        el_data.append({
            'src': src,
            'dest': dest,
            'weight': weight
        })

sorted_el = sorted(el_data, key=lambda x: x['weight'], reverse=True)
pprint.pprint(sorted_el)