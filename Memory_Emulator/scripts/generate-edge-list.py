import sys

def parse(s):
    pair = s.replace('{','').replace('}','').split(',')
    return int(pair[0]), int(pair[1])

def main(args):
    inFile = str(args[1])
    weighted_edges = []
    with open(inFile) as inpGraph:
        lines = inpGraph.readlines()
        start = lines.index("Generating graph ...\n")+1
        for line in lines[start:]:
            splits = line.strip().split(' ')
            src_vertex = int(splits[0])
            for p in splits[2:]:
                dest_vertex, weight = parse(p)
                weighted_edges.append((src_vertex, dest_vertex, weight))
    
    edgeList = [f'{x[0]} {x[1]} {x[2]}' for x in weighted_edges if x[2] > 1]
    print('\n'.join(edgeList))

if __name__ == '__main__':
    args = sys.argv
    main(args)
