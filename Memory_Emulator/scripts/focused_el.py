import sys

focused = {    
     1: [808, 12899, 12900],
     4: [12907, 12908, 12906, 13994],
     5: [5680, 5674],
     6: [13997, 14000],
     7: [12905, 5673, 12904],
     8: [12526, 12920],
}
focus_nodes = []

for _, values in focused.items():
    focus_nodes += values

el_file = sys.argv[1]

el_data = []

with open(el_file) as elfd:
    for line in elfd.readlines():
        splits = line.strip().split()
        src, dest, weight = int(splits[0]), int(splits[1]), int(splits[2])
        if (src in focus_nodes or dest in focus_nodes):
            el_data.append(f'{src} {dest} {weight}')
print('\n'.join(el_data))