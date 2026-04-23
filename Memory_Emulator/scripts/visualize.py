import networkx as nx

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import numpy as np

def parse(s):
    pair = s.replace('{','').replace('}','').split(',')
    return int(pair[0]), int(pair[1])


with open('graph.out') as graph_file:
    weighted_edges = []
    for line in graph_file:
        splits = line.strip().split(' ')
        src_vertex = int(splits[0])
        for p in splits[2:]:
            dest_vertex, weight = parse(p)
            weighted_edges.append((src_vertex, dest_vertex, weight))
    with open('edge-list.txt', 'w') as outfile:
        outfile.writelines([f'{x[0]}-({x[2]})>{x[1]}\n' for x in weighted_edges if x[2]>100])