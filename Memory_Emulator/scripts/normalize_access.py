import argparse
import random
import json
import os
import pandas as pd
from collections import defaultdict
import configparser
import math

output_folder = "/tmp"

def read_input_file(filename):
    return pd.read_csv(filename)

def get_bw_lat(NodeId, perblk_path):
    input_filee = f'{perblk_path}/block_{NodeId}.csv'
    if not os.path.exists(input_filee):
        return 0, 0, 0

    apps = ["bc"]  # Example application names
    run_numbers = ['0']  # Example run numbers

    # Open the summary.txt file in the output folder
    summary_file = os.path.join("/tmp", "summary.txt")
    with open(summary_file, "w") as summary:
        for app in apps:
            for run_number in run_numbers:
                input_file = f'{perblk_path}/block_{NodeId}.csv'
                accesses = read_input_file(input_file)
                correct_average_latency = accesses['Latency (ns)'].mean()
                avg_tq = accesses['Tque_issue'].mean()
                avg_cmd_q = accesses['CMD_que_issue'].mean()
                throttle_metric = (0.8 * avg_tq) + (0.2 * avg_cmd_q)
                #print(throttle_metric)
                correct_average_bandwidth = 64 / (1024 * 1024 * 1024 * correct_average_latency)
                return correct_average_bandwidth, correct_average_latency, throttle_metric

def calculate_node_frequencies(clusters_file, block_freq_file, perblk_path):
    # Initialize dictionaries to store node counts, nodes, and frequencies by cluster
    nodes_by_cluster = {}
    node_count_by_cluster = {}
    cluster_frequency_sum = {}
    cluster_uniqcnt_sum = {}
    node_to_cluster_map = {}
    frequency_by_node = {}
    uniqcount_by_node = {}

    # Read cluster nodes file
    with open(clusters_file, 'r') as f:
        for line in f:
            node_id, cluster_id = line.strip().split()
            cluster_id = cluster_id.strip()
            node_to_cluster_map[node_id] = cluster_id

            # Store node ID in the cluster's list
            if cluster_id in nodes_by_cluster:
                nodes_by_cluster[cluster_id].append(node_id)
            else:
                nodes_by_cluster[cluster_id] = [node_id]

            # Increase node count for the cluster
            if cluster_id in node_count_by_cluster:
                node_count_by_cluster[cluster_id] += 1
            else:
                node_count_by_cluster[cluster_id] = 1
        

    # Read block frequency mapping file
    with open(block_freq_file, 'r') as f:
        for line in f:
            parts = line.strip().split('Freq:')
            block_info_part = parts[0].strip()
            frequency_part = parts[1].strip().split('UniqCounts:')
        
            frequency = int(frequency_part[0].strip())
            uniq_counts = int(frequency_part[1].strip())
            block_info = block_info_part.split(':')
            block_id = block_info[1].strip()

            cluster_id = node_to_cluster_map.get(block_id)
            
            frequency_by_node[block_id] = frequency
            uniqcount_by_node[block_id] = uniq_counts
            
            # Aggregate frequency per assumed cluster_id, modify logic as needed
            if cluster_id in cluster_frequency_sum:
                cluster_frequency_sum[cluster_id] += frequency
            else:
                cluster_frequency_sum[cluster_id] = frequency

            if cluster_id in cluster_uniqcnt_sum:
                cluster_uniqcnt_sum[cluster_id] += uniq_counts
            else:
                cluster_uniqcnt_sum[cluster_id] = uniq_counts
            
    # Calculate and print total nodes, ratio, and node details per cluster
    cluster_metrics = []
    total_frequency_count = sum(cluster_frequency_sum.values())
    for cluster_id in node_count_by_cluster:
        total_nodes = node_count_by_cluster[cluster_id]
        total_frequency = cluster_frequency_sum.get(cluster_id, 1)  # Avoid division by zero
        total_uniqcnts = cluster_uniqcnt_sum.get(cluster_id, 1)  # Avoid division by zero
        ratio = total_frequency / total_nodes
        nodes = ', '.join(nodes_by_cluster[cluster_id])
        cluster_metrics.append((cluster_id, total_nodes, total_frequency, nodes, ratio, total_uniqcnts))
        #print(f"{cluster_id} | {total_nodes} | {ratio:.2f} | {nodes} | {total_frequency}")

    cluster_metrics.sort(key=lambda x: x[4], reverse=True)
    
    sorted_frequencies = [item[2] for item in cluster_metrics]  # Extract total frequencies
    cumulative_frequency = 0
    clusters_for_90_percent = []

    for cluster_id, _, total_frequency, _, _, _ in cluster_metrics:
        cumulative_frequency += total_frequency
        clusters_for_90_percent.append(cluster_id)
        if cumulative_frequency >= 0.90 * total_frequency_count:
            break

    cumulative_bandwidth = 0
    cumulative_latency = 0
    print("ClusterID | NodeID | Total Nodes | (Sum of Frequencies / Total Nodes) | Frequency | Bandwidth | Latency | FootPrint | FootPrint Growth | Throttle")

    for cluster_id, total_nodes, total_frequency, nodes, ratio, total_uniqcnts in cluster_metrics:
        total_bandwidth = 0
        total_latency = 0

        # Calculate total bandwidth and total latency for this cluster_id
        for node_id in nodes_by_cluster[cluster_id]:
            bandwidth, latency, throttle = get_bw_lat(node_id, perblk_path)
            total_bandwidth += bandwidth
            total_latency += latency
            cumulative_bandwidth += bandwidth
            cumulative_latency += latency

        # Print cluster-level metrics (first row)
        footprint = total_uniqcnts / total_frequency
        print(f"{cluster_id} |     | {total_nodes} | {ratio:.2f} | {total_frequency} | {total_bandwidth} | {total_latency} | {total_uniqcnts} | {footprint:.2f} | {throttle}")

        # Print individual node-level metrics (subsequent rows, leaving ClusterID column blank)
        for node_id in nodes_by_cluster[cluster_id]:
            bandwidth, latency, throttle = get_bw_lat(node_id, perblk_path)
            node_frequency = frequency_by_node.get(node_id, 0)
            node_uniqcount = uniqcount_by_node.get(node_id, 0)
            node_footprint = node_uniqcount / node_frequency if node_frequency > 0 else 0
            print(f"   | {node_id} |  1  | {node_frequency} | {node_frequency} | {bandwidth} | {latency} | {node_uniqcount} | {node_footprint:.2f} | {throttle}")

    print("\nTotal Frequency:", total_frequency_count)
    print(f"Number of clusters accounting for 90% of total frequency count: {len(clusters_for_90_percent)}")
    print("\nTotal Bandwidth:", cumulative_bandwidth)
    print("\nTotal Latency:", cumulative_latency)

    for cluster_id in clusters_for_90_percent:
        for node_id in nodes_by_cluster[cluster_id]:
            print(f"BlockId : {node_id} , ClusterID : {cluster_id}")

def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Process clustering and block frequency mapping files.')
    parser.add_argument('clusters_file', help='The clusters nodes file')
    parser.add_argument('block_freq_file', help='The block frequency mapping file')
    parser.add_argument('perblk_path', help='The path containing perblk .csv')

    # Parse the arguments
    args = parser.parse_args()

    # Process the files based on the arguments
    calculate_node_frequencies(args.clusters_file, args.block_freq_file, args.perblk_path)

if __name__ == '__main__':
    main()
