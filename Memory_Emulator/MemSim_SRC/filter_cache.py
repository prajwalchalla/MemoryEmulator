
import math
from directory import Directory


class Filter_CacheLine:
    def __init__(self):
        self.valid = False
        self.dirty = False
        self.address = None
        self.timestamp = 0  # For LRU replacement
        self.evicted=False #change to true when the line is evicted
    #This function was for debugging
    def print_line(self):
        print(self.valid,self.dirty,self.address,self.timestamp,self.evicted)

class Filter_CacheSet:
    #CacheSet class is passed to the cache. We can use it to trace the cache misses due to associativity if needed.
    def __init__(self, associativity):
        self.cache_lines_per_set = associativity
        self.miss_count = 0
        self.cache_lines = [Filter_CacheLine() for _ in range(self.cache_lines_per_set)]



class Filter_Cache:
    def __init__(self, name, id, size, block_size, associativity,latency,directory=None):
        self.size = size
        self.coreID=id
        print("Core id is", self.coreID)
        self.name=name
        self.block_size = block_size #in bytes
        self.associativity = associativity
        self.num_sets = size // (block_size * associativity)
        self.cache_sets = [Filter_CacheSet(associativity) for _ in range(self.num_sets)]
        self.directory=directory


    def calculate_index_and_tag(self, address):
        offset_bits = int(math.log2(self.block_size))
        index_bits = int(math.log2(self.num_sets))

        set_index = (address >> offset_bits) & ((1 << index_bits) - 1)
        tag = address >> (offset_bits + index_bits)
        tag_and_index=address >> offset_bits
        return set_index,tag, tag_and_index, offset_bits,index_bits

    def filter(self,address,time,read):
        set_index, tag, tag_and_index,offset_bits,index_bits = self.calculate_index_and_tag(address)

        for line in self.cache_sets[set_index].cache_lines:
            if line.valid and line.address == tag:
                # Cache hit - return data and update the timeline
                line.timestamp = time
                return "Cache Hit"
        #miss...replace the line and send in requests    
        lru_line = min(self.cache_sets[set_index].cache_lines, key=lambda line: line.timestamp)
        if(lru_line.dirty==True):
            #writeback
            #evicted_address=bin(lru_line.address)+bin(set_index)[2:].zfill(int(math.log2(self.associativity)))
            evicted_address = (lru_line.address << (offset_bits + index_bits)) | (set_index << offset_bits)
            lru_line.timestamp=time
            lru_line.address=tag
            lru_line.valid=True
            if read==1:
                lru_line.dirty=False
            else:
                lru_line.dirty=True
            #evicted_address=int(evicted_address,2)
            #evicted_address=evicted_address<<int(math.log2(self.block_size))
            return evicted_address  #This means there are 2 requests, miss and eviction
        
        else:

            lru_line.timestamp=time
            lru_line.address=tag
            lru_line.valid=True
            if read==1:
                lru_line.dirty=False
            else:
                lru_line.dirty=True
            return "Cache miss" #This means there are 2 requests, miss and eviction
        
    
    def cache_search_dir(self,tag,set_index,time,read,offset_bits,index_bits):
        
        for line in self.cache_sets[set_index].cache_lines:
            if line.valid and line.address == tag:
                # Cache hit - return data and update the timeline
                line.timestamp = time
                return "Cache Hit"
        #miss...replace the line and send in requests    
        lru_line = min(self.cache_sets[set_index].cache_lines, key=lambda line: line.timestamp)
        if lru_line.address is not None:
            #evicted_address=bin(lru_line.address)+bin(set_index)[2:].zfill(int(math.log2(self.associativity)))
            evicted_address = (lru_line.address << (offset_bits + index_bits)) | (set_index << offset_bits)
            state=self.directory.read_dir(evicted_address,self.coreID)
            state[self.coreID]='I'
            shared_state_count=0
            for key,value in state.items():
                if value=='S':
                    shared_state_count+=1
                    key_shared=key
            if shared_state_count==1:
                state[key_shared]='E'

            if all(value == 'I' for value in state.values()):
                self.directory.del_entry(evicted_address)
            else:
                self.directory.write_dir(evicted_address,self.coreID,state)

        if(lru_line.dirty==True):
            #writeback
            lru_line.timestamp=time
            lru_line.address=tag
            lru_line.valid=True
            if read==1:
                lru_line.dirty=False
            else:
                lru_line.dirty=True
            #evicted_address=int(evicted_address,2)
            #evicted_address=evicted_address<<int(math.log2(self.block_size))
            return evicted_address  #This means there are 2 requests, miss and eviction
        else:

            lru_line.timestamp=time
            lru_line.address=tag
            lru_line.valid=True
            if read==1:
                lru_line.dirty=False
            else:
                lru_line.dirty=True
            return "Cache miss" #This means there are 2 requests, miss and eviction

    
    def filter_dir(self,address,time,read):
        #assume MESI directory. If invalid, load the data from L3, update directory
        #if M then use as it is. If s and read then use as it is. It write then change to M
        set_index, tag, tag_and_index,offset_bits,index_bits = self.calculate_index_and_tag(address)
        if read==0:
            #it is write
            state=self.directory.read_dir(tag_and_index,self.coreID)
            for key,value in state.items():
                    state[key]='I'
            state[self.coreID]='M'
            self.directory.write_dir(tag_and_index,self.coreID,state)
            return self.cache_search_dir(tag,set_index,time,read,offset_bits,index_bits)
            
        else:
            #Now it is a read operation.
            state=self.directory.read_dir(tag_and_index,self.coreID)
            
            state_id=state[self.coreID]
            #print(state, state_id, hex(address))
            if state_id=='M' or state_id=='E' or state_id=='S':
                return self.cache_search_dir(tag,set_index,time,read,offset_bits,index_bits)
            
            if state_id=='I':
                #change dir to S and other non invalid data to shared
                #print("Invalid state detected.")
                for key, value in state.items():
                    if value=='E' or value=='M' or value=='S':
                        state[key]='S'
                state[self.coreID]='S' 
                #invalid..definately causes a cache miss...
                lru_line = min(self.cache_sets[set_index].cache_lines, key=lambda line: line.timestamp)
                if lru_line.address is not None:
                    #evicted_address=bin(lru_line.address)+bin(set_index)[2:].zfill(int(math.log2(self.associativity)))
                    evicted_address = (lru_line.address << (offset_bits + index_bits)) | (set_index << offset_bits)
                    state=self.directory.read_dir(evicted_address,self.coreID)
                    state[self.coreID]='I'
                    shared_state_count=0

                    for key,value in state.items():
                        if value=='S':
                            shared_state_count+=1
                            key_shared=key
                    if shared_state_count==1:
                        state[key_shared]='E'

                    if all(value == 'I' for value in state.values()):
                        self.directory.del_entry(evicted_address)
                    else:
                        self.directory.write_dir(evicted_address,self.coreID,state)
                
                if(lru_line.dirty==True):
                    #writeback
                    lru_line.timestamp=time
                    lru_line.address=tag
                    lru_line.valid=True
                    if read==1:
                        lru_line.dirty=False
                    else:
                        lru_line.dirty=True
                    #evicted_address=int(evicted_address,2)
                    #evicted_address=evicted_address<<int(math.log2(self.block_size))
                    return evicted_address  #This means there are 2 requests, miss and eviction
                else:

                    lru_line.timestamp=time
                    lru_line.address=tag
                    lru_line.valid=True
                    if read==1:
                        lru_line.dirty=False
                    else:
                        lru_line.dirty=True
                    return "Cache miss" #This means there are 2 requests, miss and eviction
       

            

