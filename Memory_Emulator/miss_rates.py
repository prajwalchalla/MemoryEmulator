'''
This script evaluates the miss rates for differnt runs. 
Also make another script that does the same thing with pagemapping
'''


import os
import subprocess
import datetime
from pathlib import Path
import argparse
import json
import glob
import csv
import math
import numpy as np


def calculate_miss_rates(json_file, output_file,filename):
    # Read the JSON file
    with open(json_file, 'r') as file:
        data = json.load(file)

    # Initialize variables to accumulate L2 and L3 hits and misses
    l2_hits_total = 0
    l2_misses_total = 0
    l3_hits_total = 0
    l3_misses_total = 0

    # Iterate over the keys and values in the JSON data
    for key, value in data.items():
        # Check if the key belongs to L2 or L3 and calculate miss rates
        if 'L2' in key:
            if 'hit' in key:
                l2_hits_total += value
            elif 'miss' in key:
                l2_misses_total += value
                # Calculate miss rate for this specific L2 level
                cpu, level = key.split('_')
                miss_rate = (value / (data[f'{cpu}_hit'] + value))
                print(f'L2 misses for {filename}: CPU {cpu[-1]}, {level} miss rate: {miss_rate}')
                output_file.write(f'L2 misses for {filename}: CPU {cpu[-1]}, {level} miss rate: {miss_rate}\n')
        elif 'L3' in key:
            if 'hit' in key:
                l3_hits_total += value
            elif 'miss' in key:
                l3_misses_total += value

    # Calculate overall L2 and L3 miss rates
    overall_l2_miss_rate = (l2_misses_total / (l2_hits_total + l2_misses_total))
    overall_l3_miss_rate = (l3_misses_total / (l3_hits_total + l3_misses_total))

    # Print and write the overall miss rates to the output file
    print(f"Overall L2 and L3 miss rate for {filename} is {overall_l2_miss_rate} and {overall_l3_miss_rate}")
    output_file.write(f'Overall L2 and L3 miss rate for {filename} is {overall_l2_miss_rate} and {overall_l3_miss_rate} \n')
    #print(f'Overall L2 miss rate: {overall_l2_miss_rate:.2f}%')
    #print(f'Overall L3 miss rate: {overall_l3_miss_rate:.2f}%')
    #output_file.write(f'Overall L2 miss rate: {overall_l2_miss_rate:.2f}%\n')
    #output_file.write(f'Overall L3 miss rate: {overall_l3_miss_rate:.2f}%\n')


def parse_miss_rates(results_folder, runs,applications, buffer, period):
    
    output="{}/miss_rate_results.txt".format(results_folder)
    with open(output, 'w') as output_file:
    # List of JSON files to process
        for run in range(0, runs):
            for app in applications:
                for buff in buffer:
                    for p in period:
                        json_file="{}/{}_run{}_b{}_p{}_total_stats.json".format(results_folder,app,run,buff,p)
                        filename="{}_run{}_b{}_p{}".format(app,run,buff,p)
                        print(json_file)
                        print(output_file)
                        print(filename)
                        calculate_miss_rates(json_file, output_file,filename)
                          


def run_main_script(source_folder, input_folder,results_folder, runs,applications, buffer, period):
    # Ensure the source folder contains main.py
    main_py_path = Path(source_folder) / "main.py"
    if not main_py_path.exists():
        print(f"Error: 'main.py' not found in {source_folder}")
        return

    # Check if the results folder exists; if not, create it
    results_path = Path(results_folder)
    if not results_path.exists():
        print(f"Creating results folder at: {results_folder}")
        results_path.mkdir(parents=True, exist_ok=True)

    # Loop to run main.py the specified number of times
    os.chdir(source_folder)
    for run in range(0, runs):
        for app in applications:
            for buff in buffer:
                for p in period:    
                    print(f"Run {run}, {app}, {buff}, {p}: Executing 'main.py'")
                    # Command to execute main.py
                    #modify the input folder accordingly...
                    final_input="{}/run_{}/{}-memgaze-trace-b{}-p{}/{}-memgaze.trace".format(input_folder,run,app,buff,p,app)
                    out_filename="{}_run{}_b{}_p{}".format(app,run,buff,p)
                    cmd = ['python3', 'main.py', '--input', final_input, '--outfolder', str(results_folder),'--filename', str(out_filename)]
                    subprocess.run(cmd)  # run the command

def resolve_pagemaps(directory,out_dir,app,run,buffer,period):
    # Initialize an empty dictionary to hold the mappings
    mappings = {}

    # Get a list of all files in the directory that start with 'pagemap_info'
    files = glob.glob(os.path.join(directory, 'pagemap_info*'))

    # Sort the files by their modification time in ascending order
    files.sort(key=os.path.getmtime)

    # Loop through each file
    for filename in files:
        # Open the file and read each line
        with open(filename, 'r') as file:
            print(filename)
            for line in file:
                if line.startswith('Incomplete'):
                    # Print the line and skip processing it
                    #print(line)
                    continue
                # Split the line into virtual and physical addresses
                virtual, physical = line.strip().split()

                # Update the dictionary with the latest physical address for this virtual address
                mappings[virtual] = physical
    map_file='{}_run{}_b{}_p{}_mappings.txt'.format(app,run,buffer,period)
    with open(os.path.join(out_dir, map_file), 'w') as file:
        # Write the length of the dictionary
        #file.write(f'Number of mappings: {len(mappings)}\n')

        # Write the mappings, sorted by virtual address
        for virtual in sorted(mappings.keys()):
            file.write(f'{virtual} {mappings[virtual]}\n')
    
    return mappings

def get_cache_and_memory_info(virtual_address, physical_address):
    # Extract the cache parameters
    global cache_parameters
    global memory_parameters
    
    cache_size = cache_parameters['size']
    cache_associativity = cache_parameters['associativity']
    cache_line_size = cache_parameters['line_size']

    # Calculate the number of sets in the cache
    num_cache_sets = cache_size // (cache_associativity * cache_line_size)

    # Calculate the cache set number
    cache_set = (virtual_address // cache_line_size) % num_cache_sets

    # Extract the memory parameters
    num_channels = memory_parameters['channels']
    num_ranks = memory_parameters['ranks']
    num_bankgroups = memory_parameters['bankgroups']
    num_banks_per_group = memory_parameters['banks_per_group']
    num_rows = memory_parameters['rows']
    num_columns = memory_parameters['columns']

    # Calculate the number of bits for each parameter
    num_channel_bits = int(math.log2(num_channels))
    num_rank_bits = int(math.log2(num_ranks))
    num_bankgroup_bits = int(math.log2(num_bankgroups))
    num_banks_per_group_bits = int(math.log2(num_banks_per_group))
    num_row_bits = int(math.log2(num_rows))
    num_column_bits = int(math.log2(num_columns))

    # Define the address mapping scheme
    address_mapping = 'rochrababgco'

    # Define the field widths and initial positions
    field_widths = {'ch': num_channel_bits, 'ra': num_rank_bits, 'bg': num_bankgroup_bits, 'ba': num_banks_per_group_bits, 'ro': num_row_bits, 'co': num_column_bits}
    field_pos = {'ch': 0, 'ra': 0, 'bg': 0, 'ba': 0, 'ro': 0, 'co': 0}

    # Calculate the field positions based on the address mapping scheme
    pos = 0
    for i in range(len(address_mapping) - 2, -1, -2):
        token = address_mapping[i:i+2]
        field_pos[token] = pos
        pos += field_widths[token]

    # Extract the channel, rank, bank group, bank, and row numbers
    channel = (physical_address >> field_pos['ch']) & ((1 << field_widths['ch']) - 1)
    rank = (physical_address >> field_pos['ra']) & ((1 << field_widths['ra']) - 1)
    bankgroup = (physical_address >> field_pos['bg']) & ((1 << field_widths['bg']) - 1)
    bank = (physical_address >> field_pos['ba']) & ((1 << field_widths['ba']) - 1)
    row = (physical_address >> field_pos['ro']) & ((1 << field_widths['ro']) - 1)

    return cache_set, channel, rank, bankgroup, bank, row



def map_addresses(csv_filename, mappings_filename, output_filename, page_size=4096):
    # Load the mappings into a dictionary
    mappings = {}
    with open(mappings_filename, 'r') as file:
        for line in file:
            virtual, physical = line.strip().split()
            mappings[int(virtual, 16)] = int(physical, 16)
            #print(f"Virtual address : {virtual} Physical address : {physical} mappings[{int(virtual, 16)}] = [{int(physical, 16)}] ")

    # Initialize the distributions
    distributions = {'cache_set': {}, 'channel': {}, 'rank': {}, 'bankgroup': {}, 'bank': {}, 'row_info': {}}

    # Open the CSV file and create a CSV reader
    with open(csv_filename, 'r') as csv_file:
        reader = csv.reader(csv_file)
        headers = next(reader)  # Skip the header row

        # Open the output file and create a CSV writer
        with open(output_filename, 'w', newline='') as out_file:
            writer = csv.writer(out_file)
            writer.writerow(headers + ['Physical address', 'Cache set', 'Channel', 'Rank', 'Bank group', 'Bank', 'Row'])  # Write the header row

            # Process each row in the CSV file
            for row in reader:
                #print(row)
                # Parse the address
                address = int(row[2], 16)

                # Calculate the page number and offset within the page
                page_number = address // page_size
                offset = address % page_size

                # Look up the physical page in the mappings
                physical_page = mappings.get(page_number * page_size, 0)

                # Calculate the physical address
                physical_address = physical_page + offset
                #print(f"Original addr : {row[2]} New address : {address} Page number : {page_number} offset : {offset} Physical page : {physical_page} Physical address : {physical_address}")

                # Format the time, address, and physical address
                time = '{:.15f}'.format(float(row[4]))
                rw='{}'.format(int(row[5]))
                address = '0x{:016x}'.format(address)
                physical_address = '0x{:016x}'.format(physical_address)

                # Get the cache and memory info
                address_int = int(address, 16)
                phy_int=int(physical_address,16)
                cache_set, channel, rank, bankgroup, bank, row_info = get_cache_and_memory_info(address_int, phy_int)

                # Update the distributions
                distributions['cache_set'][cache_set] = distributions['cache_set'].get(cache_set, 0) + 1
                distributions['channel'][channel] = distributions['channel'].get(channel, 0) + 1
                distributions['rank'][rank] = distributions['rank'].get(rank, 0) + 1
                distributions['bankgroup'][bankgroup] = distributions['bankgroup'].get(bankgroup, 0) + 1
                distributions['bank'][bank] = distributions['bank'].get(bank, 0) + 1
                distributions['row_info'][row_info] = distributions['row_info'].get(row_info, 0) + 1

                # Write the row to the output file with the physical address and cache and memory info
                writer.writerow(row[:2] + [address] + row[3:4] + [time,rw, physical_address, cache_set, channel, rank, bankgroup, bank, row_info])

    # Print the distributions
    #print(f'Distributions for {csv_filename}:')
    for key, distribution in distributions.items():
        if key in ['cache_set', 'row_info']:
            # Calculate the standard deviation for the cache set and row distributions
            values = list(distribution.values())
            std_dev = np.std(values)
            print(f'{csv_filename}  {key}  {std_dev}')
        else:
            # Print the other distributions as before
            print(f'{csv_filename}  {key} ', end=' ')
            for value, count in sorted(distribution.items()):
                print(f'{value} {count}', end=' ')
            print()

def pagemapping(input_folder,out_dir,applications,runs,buffer,period):
    
    for run in range(0,runs):
        for app in applications:
            for buff in buffer:
                for p in period:
                    folder_name='{}/run_{}/{}_ls_b{}_p{}'.format(input_folder,run,app,buff,p)
                    mappings=resolve_pagemaps(folder_name,out_dir,app,run,buff,p)
                    #can use the mappings information in phy_address_builder
                    
                    
def phy_address_builder(directory,applications,runs,buffer,period):
    #read csv, read address, read virtual address and add physical address.
    #then add the bank, channel and set information
    for run in range(0,runs):
        for app in applications:
            for buff in buffer:
                for p in period:
                    csv_filename='{}/{}_run{}_b{}_p{}_stats.csv'.format(directory,app,run,buff,p)
                    mappings_filename='{}/{}_run{}_b{}_p{}_mappings.txt'.format(directory,app,run,buff,p)
                    output_filename='{}/{}_run{}_b{}_p{}_stats_updated.csv'.format(directory,app,run,buff,p)
                    map_addresses(csv_filename, mappings_filename, output_filename, page_size=4096)
                    #can use the mappings information in phy_address_builder
    pass                   
    
    



def main():
    now = datetime.datetime.now()
    destination="/data/users/chal962/run_0"
    datetime_str = now.strftime("%Y_%m_%d_%H%M")
    # Combine "text" with the formatted datetime to create the folder name
    folder_name = f"bfs_bm_run0_test_{datetime_str}"
    default_results_folder = os.path.join(destination, folder_name)
    default_source_folder='/home/MemSim_SRC'
    default_input_folder='/data-ext/memgaze_results/memgaze_april_24_24/2024-06-21_run5_g22'
    default_number_runs=1
    
    
    parser = argparse.ArgumentParser(description="Run a Python script multiple times with specified input and output directories.")
    parser.add_argument('--source_folder', type=str, help='Folder where main.py is located', default=default_source_folder)
    parser.add_argument('--input_folder', type=str, help='Folder where main.py is located', default=default_input_folder)
    parser.add_argument('--results_folder', type=str, help='Folder to store results', default=default_results_folder)
    parser.add_argument('--runs', type=int, help='Number of times to run the script', default=default_number_runs)

    args = parser.parse_args()
    applications=["bfs"]
    buffer=["8193"]
    period=["0"]
    
    run_main_script(args.source_folder, args.input_folder, args.results_folder, args.runs, applications, buffer, period)
    parse_folder=args.results_folder
    

    #Function
    parse_miss_rates(parse_folder,args.runs,applications, buffer, period)
    
    
    pagemap_dir=args.input_folder
    out_pagemap_dir=args.results_folder
    #Function
    pagemapping(pagemap_dir,out_pagemap_dir,applications,default_number_runs,buffer,period)
    
    directory=args.results_folder
    
    phy_address_builder(directory,applications,default_number_runs,buffer,period)
    
    
cache_parameters = {
    'size': 1024*1024*32,  # 32MB
    'associativity': 16,
    'line_size': 64  # 64 bytes
}

memory_parameters = {
    'channels': 4,  # Dual-channel memory
    'ranks': 2,  # Typical for DDR4 and DDR5 memory
    'bankgroups': 4,  # Typical for DDR4 and DDR5 memory
    'banks_per_group': 4,  # Typical for DDR4 and DDR5 memory
    'rows': 65536,  # Typical for DDR4 and DDR5 memory
    'columns': 1024  # Typical for DDR4 and DDR5 memory
}

if __name__ == "__main__":
    main()

