
'''
Implementing MESI cache policy. for our work, coherence is only applied on the first level of the cache hierarchy.
Also unlike the cache communication, directory maintains the cache states. And we are implementing neither inclusive nor exclusive policy (NINE).
If there is a cache miss, then the block is evicted into lower levels of memory.
In case the block was invalid, then do not write back. Exclusive state helps keeps track of writebacks. Only writeback if in M state...

'''


class Directory:
    #Need to pass the directory to cache.py later. Now set cache.py to be called from system...
    def __init__(self, name,id):
        self.name=name
        self.directory={} #search via address. Cache state list is according to their ids. Directory is dict within a dict
        self.cacheid=id


    def add_entry(self,address,id):
        #might save the id obtained from cacheid_dict
        #If accessed for the first time, all the other states are invalid
        #add "E" to id entry
        #return the added entry..
        a={}
        for core in self.cacheid: 
            a[core]='I'
        a[id]='E'
        self.directory[address]=a
        return self.directory[address]



    def read_dir(self,address,id):
        #if read for the first time, then add_entry. else address the query

        #Cache would be doing read ask(if a miss) and update(before miss has received. The miss would go ahead to the core). to avoid any conflicts and hazard.
        #Since updates are made in L1 cache they would be instantaneous
        #for a cache miss, read for L1 and update the state invalid state of L2 to invalidate
        if address in self.directory:
            state=self.directory[address] 
            return state
        
        
        else:
            state=self.add_entry(address,id)
            return state
        

    def del_entry(self,address):
        #if all the addresses are invalid, then delete the entry from the dictionary to save space
        del self.directory[address]

    def write_dir(self,address,id, entry):
        #if a cache write is made, then update the directory
        #for each cache eviction, update the data as invalid
        #delete dir entry through the cache since it will read and update all the other states
        #Cache read current directory state and writes a new state
        self.directory[address]=entry


    def print_dir(self):
        print(self.directory)    