#!/bin/bash

test_dir=$1

for i in 3; do
    out_dir=$test_dir/out-$i
    mkdir -p $out_dir
    ./gen-trace-graph $test_dir/remapped-bc-memgaze.trace $test_dir/basicblocks.json $i > $out_dir/trace-graph-output.txt
    # python scripts/gen-id2block-mapping.py $out_dir/trace-graph-output.txt > $out_dir/id2blk.json
    python scripts/generate_block_freq.py $out_dir/trace-graph-output.txt $out_dir/block_freq_mapping.txt
    
    python scripts/generate_cxl_freq.py $out_dir/trace-graph-output.txt $out_dir/block_cxl_freq_mapping.txt
    
    python scripts/generate_dram_freq.py $out_dir/trace-graph-output.txt $out_dir/block_dram_freq_mapping.txt
    
    python scripts/generate-edge-list.py $out_dir/trace-graph-output.txt > $out_dir/trace-graph.el
    python scripts/createDOT.py $out_dir/trace-graph.el $test_dir/basicblocks.json
    dot -Tpdf $out_dir/trace-graph.el.dot > $out_dir/trace-graph.pdf
    ./DirectedLouvain/bin/community -f $out_dir/trace-graph.el -w -l -1 -v > $out_dir/trace-graph-community.tree
    python scripts/communities.py $test_dir $i
done
