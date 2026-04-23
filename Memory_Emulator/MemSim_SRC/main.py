'''
This is core MemSim. In here we do not have core, and private caches. 
Assume that cache coherencies will be resolved at L3 cache shared and.
We implement a filter function that will disregard the pipeline for all the hits in L1, and L2 cache. 
Only L2 misses will be passed onto L3 cache. This will speed up the simulations.
'''

import configparser
from event_recorder import StatsRecorder
from filter import Filter
from llc import Cache
from directory import Directory
from pprint import pprint
import argparse

class system:
    def __init__(self,config,output_folder,out_filename) -> None:
        
        #self.coreids=config.get("sim_config","coreids").split()
        self.coreids=[int(cid) for cid in config.get("sim_config","coreids").split()]
        self.numCPUs=config.getint("sim_config","numCPU")
        filename='{}_stats.csv'.format(out_filename) 
        total_stats='{}_total_stats.json'.format(out_filename) 
        self.recorder=StatsRecorder(filename,total_stats,output_folder)
        self.filter_function=config.getint("Filter_function","filter_function")
        linesize=config.getint("L3_cache","linesize")
        

        print("#######  Initializing  #######")
        if self.numCPUs==0:
            print("Number of CPUs found is zero. Please recheck the system config.")
        #intialize the number of cores and then the private caches
        print("CPU core ids are:", self.coreids)

        if self.filter_function:
            print("Filter function detected, Accesses will be filtered out based on L2 cache size. L2 is assumed to be private cache.")
            filter_size=config.getint("Filter_function","capacity")
            filter_assoc=config.getint("Filter_function","assoc")
            filter_latency=config.getint("Filter_function","access_latency")
            filter_cpus=config.getint("Filter_function","num_L2_caches")
            filter_dir=config.getint("Filter_function","dir")
            directory=None
            if(filter_dir==0):
                directory=None
            else:
                directory=Directory("Dir",self.coreids)   
                print("Directory initialized for the filter function. Coherency will be considered.") 
            self.filter=Filter(self.coreids,filter_size*1024,filter_assoc,linesize,filter_latency,self.recorder,directory)
            print(self.filter)
            pprint(vars(self.filter))
        else:
            print("Filter function absent. A simple L3 cache is assumed.")

        L3cache_size=config.getint("L3_cache","capacity",fallback=1024*1024816)
        L3_associativty=config.getint("L3_cache","assoc",fallback=16)
        l3_access_latency=config.getint("L3_cache","access_latency")
        L3_banks=config.getint("L3_cache","banks")
        self.L3=Cache("L3",0,L3cache_size*1024*1024,linesize,L3_associativty,self.recorder,l3_access_latency,L3_banks)
        print("succesfully initialized")
        

    def operation(self,address, timestamp, lc, id, ip):
        if(lc==10):
            self.recorder.update_total_stats("T00_discarded")
            return None
        elif(lc==90):
            read=0
        else:
            #lc=0,1,2, constant load, strided or irregular load
            read=1    
        if(self.filter_function):
            result=self.filter.request_filter(ip,lc,address,id,timestamp,read)
            if result is None:
                pass
            elif isinstance(result, list) and len(result) == 2 and all(isinstance(item, list) for item in result):
                list1, list2 = result
                self.L3.operation(list1[0],list1[1],list1[2],list1[3],list1[4],list1[5])
                self.L3.operation(list2[0],list2[1],list2[2],list2[3],list2[4],list2[5])
                
            elif isinstance(result, list):
                self.L3.operation(result[0],result[1],result[2],result[3],result[4],result[5])
            else:
                print("Returned an unknown type")     
                
        else:
            result_L3=self.L3.operation(ip,lc,address,id,timestamp,read)

        


def main():
    parser=argparse.ArgumentParser(description="python3 main.py --input --outputfolder --filename")
    parser.add_argument('--input', type=str, help='The input trace file along with its full folder location.')
    parser.add_argument('--outfolder', type=str, default='default_value', help='location where you want to place output files in.')
    parser.add_argument('--filename', type=str, default='default_value', help='Prefix name of the output files.')
    # Parse the command-line arguments
    args = parser.parse_args()

    # Access the arguments
    print('Input files is:', args.input)
    print('Output folder location is:', args.outfolder)
    print('Output Filename is:', args.filename)
    file_open=args.input
    output_folder=args.outfolder
    out_file_name=args.filename

    configs=configparser.ConfigParser(inline_comment_prefixes=";")
    configs.read("config.ini")
    sys=system(configs,output_folder,out_file_name)
    
    header_line = "TRACE: <IP> <LoadClass/Store> <Addrs> <CPU> <time> <sampleID> <DSO_id>"
    
    with open(file_open) as f:
       
        for line in f:
            if line.strip() == header_line:
                break
        
        # Read the first line after the header
        first_line = f.readline().strip()
        parts = first_line.split()
        ip = parts[0]
        # Extract the memory address from the third field of the TRACE line, convert it from hexadecimal to decimal, and assign it to the variable 'address'
        load_store_class=int(parts[1])
        address = int(parts[2], 16)
        # Extract the timestamp from the fifth field of the TRACE line and assign it to the variable 'timestamp'
        cpu=(parts[3])
        init_timestamp = float(parts[4])
        sys.operation(address=address, timestamp=0, lc=load_store_class, id=int(cpu), ip=ip)
        
        for line in f:
            # Split the line into parts using whitespace as the delimiter
            parts = line.split()
            # Extract the IP address from the second field of the TRACE line and assign it to the variable 'ip'
            ip = parts[0]
            # Extract the memory address from the third field of the TRACE line, convert it from hexadecimal to decimal, and assign it to the variable 'address'
            load_store_class=int(parts[1])
            address = int(parts[2], 16)
            # Extract the timestamp from the fifth field of the TRACE line and assign it to the variable 'timestamp'
            cpu=(parts[3])
            timestamp = float(parts[4])-init_timestamp
            sys.operation(address=address, timestamp=timestamp, lc=load_store_class, id=int(cpu), ip=ip)

    sys.recorder.save_total_stats()
    sys.recorder.save_to_file()


if __name__ == "__main__":
    main()
