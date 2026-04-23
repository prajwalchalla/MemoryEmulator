
import networkx as nx
import matplotlib.pyplot as plt

from netgraph import Graph, InteractiveGraph
from pprint import pprint
import json

import colorsys
import sys

from community import community_louvain
import networkx as nx

grpah_variant = {
    '1': 'IP',
    '2': 'Memory',
    '3': 'IP + Memory'
}

test_dir = sys.argv[1]
variant_id = sys.argv[2]
test_out_dir = f'{test_dir}/out-{variant_id}'

basicblocks = json.load(open(f'{test_dir}/basicblocks.json'))
# print(basicblocks.keys())

graph = f'{test_out_dir}/trace-graph.el'
weightedEdgeList = []
with open(graph) as file:
    for line in file.readlines():
        splits = line.strip().split()
        weightedEdgeList.append(
            (int(splits[0]), int(splits[1]), int(splits[2]))
        )

G = nx.DiGraph()
G.add_weighted_edges_from(weightedEdgeList)

# partitions = f'{test_out_dir}/trace-graph-community.tree'
# node2comm = {}
# lvl0_done = False
# with open(partitions) as file:
#     for line in file.readlines():
#         splits = line.strip().split()
#         node, comm = int(splits[0]), int(splits[1])
#         if node == -1 or comm == -1:
#             if lvl0_done:
#                 break
#             lvl0_done = True
#             continue
#         node2comm[node] = comm

node2comm = community_louvain.best_partition(G)

# print(node2comm)

N = len(set(node2comm.values()))
i=0
HSV_tuples = [(x * 1.0 / N, 0.5, 0.5) for x in range(N)]
community_to_color =  {}
for rgb in HSV_tuples:
    rgb = map(lambda x: int(x * 255), colorsys.hsv_to_rgb(*rgb))
    community_to_color[i] = '#%02x%02x%02x' % tuple(rgb)
    i+=1

node_color = {node: community_to_color[community_id]
                for node, community_id in node2comm.items()}
# print(node_color)

annotations = {}
nodes = []
for el in weightedEdgeList:
    nodes.append(el[0])
nodes = list(set(nodes))
for node in nodes:
    annotations[node] = basicblocks[f'{node}']['function']
# print(annotations)


edges = [(x[0], x[1]) for x in weightedEdgeList]
labels = [x[2] for x in weightedEdgeList]
# print(dict(zip(edges,labels)))


Graph(
    G,
    node_color=node_color,
    edge_alpha=1,
    node_labels=True,
    node_layout='community', 
    node_layout_kwargs=dict(node_to_community=node2comm),
    edge_layout='bundled', 
    arrows=True,
    edge_layout_kwargs=dict(k=1000),
    scale=(.8,.8)
)
plt.title(grpah_variant[variant_id])
plt.savefig(f'{test_out_dir}/clustering-0.pdf', bbox_inches="tight", dpi=800, facecolor='w')
