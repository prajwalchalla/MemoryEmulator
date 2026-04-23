import sys

trace_file = sys.argv[1]
window_sz = int(sys.argv[2])

ips = []

print('loading trace file ...')
with open(trace_file) as fd:
    for line in fd:
        ips.append(line.split()[0])

ips = ips[3:]
print('ips:', len(ips))

print('extracting sequences ...')
sequences = {}
for i in range(len(ips)-window_sz):
    seq = '~'.join(ips[i:window_sz])
    if seq not in sequences.keys():
        sequences[seq] = 0
    sequences[seq] += 1

print('sorting sequences ...')
sorted_seqs = dict(sorted(sequences.items(), key=lambda item: item[1]))

for seq, cnt in sorted_seqs.items():
    print(cnt, seq)