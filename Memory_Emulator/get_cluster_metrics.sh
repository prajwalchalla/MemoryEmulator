#!/usr/bin/bash

## Get Dyninst Mappings File for current trace
scripts/filter-dynist-mappings.sh /data-ext/users/gaja579/pnnl/pnnl/memgaze_results/memgaze_april_24_24/2024-06-21_run5_g22/run_0/bfs_ls_b8193_p0/bfs-memgaze.binanlys.log /data/users/chal962/run_0/mappings.txt  

## Convert existing .trace file to remapped .trace file
python3 scripts/map-memgaze-ips.py /data/users/chal962/run_0/mappings.txt /data-ext/users/gaja579/pnnl/pnnl/memgaze_results/memgaze_april_24_24/2024-06-21_run5_g22/run_0/bfs-memgaze-trace-b8193-p0/bfs-memgaze.trace /data/users/chal962/run_0/remapped-bfs-memgaze.trace 

##Get Basicblocks.json
#python3 scripts/process-binanlys-log.py /data-ext/users/gaja579/pnnl/pnnl/memgaze_results/memgaze_april_24_24/2024-06-21_run5_g22/run_0/bfs_ls_b8193_p0/bfs-memgaze.binanlys.log > /data/users/chal962/run_0/basicblocks.json 

##Run cluster analysis
#sh run-cluster-analys.sh /data/users/chal962/run_0

## Run miss_rates.py
#python3 miss_rates.py


## Run HOME to DRAM model
#python3 home_to_dram.py


##Include remmaped IP as column in HOME's DRAM trace file output.
#python3 scripts/map-memgaze-ips-HOME.py /data/users/chal962/run_0/mappings.txt /data/users/chal962/run_0/HOME_OUTPUT/results_bfs_0.csv /data/users/chal962/run_0/HOME_OUTPUT/remapped_results_bfs_0.csv 

## Get per block DRAM accesses
#./dump-block-mapping /data/users/chal962/run_0/HOME_OUTPUT/remapped_results_bfs_0.csv /data/users/chal962/run_0/basicblocks.json /data/users/chal962/run_0/perblk2

##Get per cluster metrics
python3 scripts/normalize_access.py /data/users/chal962/run_0/out-3/clusters_nodes.txt /data/users/chal962/run_0/out-3/block_freq_mapping.txt UNUSED UNUSED
