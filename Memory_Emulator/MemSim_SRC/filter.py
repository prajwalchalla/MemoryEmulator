#Filter function. Uses L2 buffer to flter out the accesses to the L3 cache.


from filter_cache import Filter_Cache





class Filter:
    def __init__(self,coreids,size,assoc,line,latency,recorder,directory=None) -> None:
        self.caches={}
        self.directory=directory
        self.latency=latency*1e-9
        self.recorder=recorder
        self.size=size
        self.assoc=assoc
        for id in coreids:
            cache=Filter_Cache(id,id,size,line,assoc,self.latency,directory)
            self.caches[id]=cache

    def request_filter(self, ip, lc, address, id, time,read):
        #read is either 0 or 1
        if(self.directory==None):
            filter_value=self.caches[id].filter(address,time,read)
            
        else:
            #print("Filter_dir called")
            filter_value=self.caches[id].filter_dir(address,time,read)

        if(filter_value=="Cache Hit"):
            # value gets filtered out
            self.recorder.update_total_stats("L2"+str(id)+"_hit")
            return None
        elif(filter_value=="Cache miss"):
            packet=[ip,lc,address,id,time+self.latency,read]
            self.recorder.update_total_stats("L2"+str(id)+"_miss")
            return packet
        else:
            #it is a cache miss + a write back
            packet=[ip,lc,address,id,time+self.latency,read]
            packet2=[None, None, filter_value,id,time+self.latency,0]
            self.recorder.update_total_stats("L2"+str(id)+"_miss")
            self.recorder.update_total_stats("L2"+str(id)+"_writeback")
            new_packet=[packet,packet2]
            return new_packet