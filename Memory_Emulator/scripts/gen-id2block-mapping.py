import sys
import json

id2blk = {}

def main(args):
    inFile = str(args[1])
    with open(inFile) as inpGraph:
        lines = inpGraph.readlines()
        start = lines.index('Printing blocks info ...\n') + 2
        end = lines.index('Printing blocks info done.\n')

        for line in lines[start:end]:
            #Block, Start, End, Size
            [b_id, b_start, b_end, b_size] = line.strip().split(' ')
            id2blk[b_id.replace(',', '')] = {
                'start': b_start.replace(',', ''),
                'end': b_end.replace(',', ''),
                'size': b_size
            }
            
    print(json.dumps(id2blk, indent=4))

if __name__ == '__main__':
    args = sys.argv
    main(args)