import sys
import pprint

test_out_dir = sys.argv[1]

partitions = f'{test_out_dir}/trace-graph-community.tree'
lvl = -1
comm2node = {}
with open(partitions) as file:
    for line in file.readlines():
        splits = line.strip().split()
        node, comm = int(splits[0]), int(splits[1])
        if node == -1 or comm == -1:
            lvl += 1
            comm2node[lvl] = {}
            continue
        if comm not in comm2node[lvl].keys():
            comm2node[lvl][comm] = []
        comm2node[lvl][comm].append(node)

pprint.pprint(comm2node)