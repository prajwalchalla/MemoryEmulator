

import math

class CacheLine:
    def __init__(self):
        self.valid = False
        self.dirty = False
        self.address = None
        self.timestamp = 0  # For LRU replacement
        self.evicted=False #change to true when the line is evicted
    #This function was for debugging
    def print_line(self):
        print(self.valid,self.dirty,self.address,self.timestamp,self.evicted)

class CacheSet:
    #CacheSet class is passed to the cache. We can use it to trace the cache misses due to associativity if needed.
    def __init__(self, associativity):
        self.cache_lines_per_set = associativity
        self.miss_count = 0
        self.cache_lines = [CacheLine() for _ in range(self.cache_lines_per_set)]



class Cache:
    def __init__(self, name, id, size, block_size, associativity,recorder,latency,banks):
        self.size = size
        self.coreID=id
        self.name=name
        self.block_size = block_size #in bytes
        print("Linesize is ", self.block_size)
        self.associativity = associativity
        self.num_sets = size // (block_size * associativity)
        self.cache_sets = [CacheSet(associativity) for _ in range(self.num_sets)]
        #self.time_accumulated=0
        #self.pending_requests=[]
        #self.contention_time=0
        self.recorder=recorder
        self.latency=latency*1e-9
        self.banks=banks

    def calculate_index_and_tag_llc(self, address):
        #print(address)
        '''tag_and_index=address>>int(math.log2(self.block_size))

        tag=tag_and_index>>int(math.log2(self.associativity))
        set_index_bits=tag_and_index % self.associativity
        return set_index_bits,tag, tag_and_index'''

        offset_bits = int(math.log2(self.block_size))
        index_bits = int(math.log2(self.num_sets))

        set_index = (address >> offset_bits) & ((1 << index_bits) - 1)
        tag = address >> (offset_bits + index_bits)
        return set_index, tag, offset_bits,index_bits



    def operation(self,ip,lc,address,id,time,read):
        
        set_index, tag, offset_bits,index_bits = self.calculate_index_and_tag_llc(address)

        for line in self.cache_sets[set_index].cache_lines:
            if line.valid and line.address == tag:
                # Cache hit - return data and update the timeline
                line.timestamp = time
                self.recorder.update_total_stats("L30"+"_hit")
                return "Cache Hit"
        #miss...replace the line and send in requests    
        lru_line = min(self.cache_sets[set_index].cache_lines, key=lambda line: line.timestamp) #check this sentence
        if(lru_line.dirty==True):
            #writeback
            #evicted_address=bin(lru_line.address)+bin(set_index)[2:].zfill(int(math.log2(self.associativity)))
            #evicted_address=bin(lru_line.address)+bin(set_index)[2:].zfill(int(math.log2(self.associativity)))
            #evicted_address = bin(lru_line.address) + bin(set_index)[2:].zfill(int(math.log2(self.associativity)))
            # Assuming `set_index` and `tag` are correctly calculated
            evicted_address = (lru_line.address << (offset_bits + index_bits)) | (set_index << offset_bits)

            lru_line.timestamp=time
            lru_line.address=tag
            lru_line.valid=True
            if read==1:
                lru_line.dirty=False
            else:
                lru_line.dirty=True
            self.recorder.update_total_stats("L30"+"_miss")
            self.recorder.update_total_stats("L30"+"_writeback")
            
            self.recorder.record_stats(ip, lc, address, id, time, read)
            self.recorder.record_stats(ip, lc, evicted_address, id, time, read)
            #evicted_address=int(evicted_address,2)
            #evicted_address=evicted_address<<int(math.log2(self.block_size))
            #print(hex(evicted_address))
            return evicted_address  #This means there are 2 requests, miss and eviction
        
        else:

            lru_line.timestamp=time
            lru_line.address=tag
            lru_line.valid=True
            if read==1:
                lru_line.dirty=False
            else:
                lru_line.dirty=True
            self.recorder.update_total_stats("L30"+"_miss")
            self.recorder.record_stats(ip, lc, address, id, time, read)
            return "Cache miss" #This means there are 2 requests, miss and eviction
        
        
