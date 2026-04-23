import sys

def main(args):
    tracefile = str(args[1])

    tracelog = {}
    with open(tracefile) as tf:
        for line in tf.readlines():
            splits = line.strip().split()
            ip, addr, core, time = splits[0], splits[1], splits [2], splits[3]
            if time not in tracelog.keys():
                tracelog[time] = []
            tracelog[time].append([ip, addr, core])
    
    for time in tracelog.keys():
        cores = set([x[2] for x in tracelog[time]])
        if len(cores) != 1:
            print(time, cores)   

if __name__ == '__main__':
    main(sys.argv)