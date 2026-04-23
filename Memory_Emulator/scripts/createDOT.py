#!/usr/bin/python3

import sys
import json


def createDotFile(edgeList, outfile):
    strHeader = "digraph G { \n"
    strFooter = "} \n"
    fileLines = [strHeader]
    for edge in edgeList:
        src, dest, weight = edge[0], edge[1], edge[2]
        lineFmt = "\t" + str(src) + " -> " + str(dest) + " [style=bold,label=\"" + str(weight) + "\"] ;\n"
        fileLines.append(lineFmt)
    fileLines.append(strFooter)
    with open(outfile, "w") as f:
        f.writelines(fileLines)

def main(args):
    graphFile = str(args[1])
    basicblocks = json.load(open(sys.argv[2]))
    outfile = f'{graphFile}.dot'
    simplified_outfile = f'{graphFile}-simplified.dot'

    edgelist = []
    with open(graphFile) as gf:
        for line in gf:
            splits = line.strip().split()
            src, dest, weight = splits[0], splits[1], splits[2]
            src_func = basicblocks[src]['function'].split('::')[-1].partition('<')[0].split()[-1].replace('.','_')
            dest_func = basicblocks[dest]['function'].split('::')[-1].partition('<')[0].split()[-1].replace('.','_')
            edgelist.append([src_func, dest_func, weight])
    createDotFile(edgelist, outfile)

    simplified = {}
    with open(graphFile) as gf:
        for line in gf:
            splits = line.strip().split()
            src, dest, weight = splits[0], splits[1], splits[2]
            src_func = basicblocks[src]['function'].split('::')[-1].partition('<')[0].split()[-1].replace('.','_')
            dest_func = basicblocks[dest]['function'].split('::')[-1].partition('<')[0].split()[-1].replace('.','_')

            key = f'{src_func}~{dest_func}'
            if key not in simplified.keys():
                simplified[key] = 0
            simplified[key] += int(weight)
    simplifiedEdgeList = []
    for k, v in simplified.items():
        src_func, dest_func = k.split('~')
        simplifiedEdgeList.append([src_func, dest_func, v])
    createDotFile(simplifiedEdgeList, simplified_outfile)


if __name__ == '__main__':
    main(sys.argv)