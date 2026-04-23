import os
import csv
from datetime import datetime

def load_page_map(page_map_file):
    page_map = {}
    with open(page_map_file, 'r') as infile:
        for line in infile:
            virtual, physical = line.strip().split()
            page_map[int(virtual, 16) // 4096] = int(physical, 16)
    print(page_map)
    return page_map

def convert_virtual_to_physical(virtual_address, page_map, page_size=4096):
    page_number = virtual_address // page_size
    offset = virtual_address % page_size
    if page_number not in page_map:
        #print("pagenumber not in pg map")
        return None
    physical_address_base = page_map[page_number]
    physical_address = physical_address_base + offset
    return physical_address

def generate_dram_input(input_csv, output_csv, page_map, compression_factor, page_size=4096):
    with open(input_csv, 'r') as infile, open(output_csv, 'w', newline='') as outfile:
        reader = csv.reader(infile)
        writer = csv.writer(outfile)

        writer.writerow([
            "Instruction Pointer", "Access Type", "Physical Address",
            "ID", "Time Compressed Timestamp (ns)", "RW"
        ])

        next(reader)  # Skip the header
        for row in reader:
            instruction_pointer = row[0]
            access_type = row[1]
            virtual_address = int(row[2], 16)
            process_id = row[3]
            time_seconds = float(row[4])
            rw_flag = row[5]

            physical_address = convert_virtual_to_physical(virtual_address, page_map, page_size)
            #print(row)
            #print(physical_address)
            if physical_address is None:
                continue

            compressed_time_ns = int((time_seconds * 1e9) * compression_factor)
            rw_operation = "READ" if rw_flag == '1' else "WRITE"

            writer.writerow([
                instruction_pointer, access_type, f"0x{physical_address:x}",
                process_id, compressed_time_ns, rw_operation
            ])

def process_applications(input_folder, base_output_folder, app_names, drop_rates, run_numbers, buffer_size, period):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_folder = os.path.join(base_output_folder, timestamp)
    os.makedirs(output_folder, exist_ok=True)

    for app_name in app_names:
        drop_rate = drop_rates.get(app_name, 0)
        compression_factor = 1 - (drop_rate / 100)

        for run_number in range(run_numbers):
            stats_file = f"{input_folder}/{app_name}_run{run_number}_b{buffer_size}_p{period}_stats.csv"
            mapping_file = f"{input_folder}/{app_name}_run{run_number}_b{buffer_size}_p{period}_mappings.txt"

            if not (os.path.exists(stats_file) and os.path.exists(mapping_file)):
                print(f"Missing files for {app_name} run {run_number}; skipping this configuration.")
                continue

            page_map = load_page_map(mapping_file)

            output_csv = f"{output_folder}/{app_name}_run{run_number}_dram_input.csv"
            generate_dram_input(stats_file, output_csv, page_map, compression_factor)
            print(f"Generated DRAM input for {app_name} run {run_number} at {output_csv}")

if __name__ == "__main__":
    input_folder = "/data/run_x/bc_bm_run0_test_2025_08_06"
    base_output_folder = "/data/users/run_x/bc_bm_run0_test_2025_08_06/dram_model_results"
    app_names=["bc"]
    run_numbers = 1
    buffer_size = 8193
    period = 0
    drop_rates = {
        "bc": 97.95,  # Example drop rates for each application
        "bfs": 98.34,
        "cc": 98.33,
        "pr": 98.39,
        "sssp": 99.11,
        "tc": 98.9,
        "cc_sv": 98.09,
        "pr_spmv": 98.41,
        "bt.A.x": 99.66,
        "cg.B.x": 99.96,
        "ep.C.x": 98.80,	
        "ft.B.x": 98.67, 
        "is.C.x": 96.205, 
        "lu.A.x": 98.429, 
        "mg.C.x": 99.28,	
        "sp.B.x": 99.93, 
        "miniVite-v1": 99.59, 
        "miniVite-v2": 98.98,	
        "miniVite-v3": 99.37, 
        "miniVite-v4": 99.49, 
        "amg": 99.841, 
        "sw4lite": 99.9
    }

    process_applications(input_folder, base_output_folder, app_names, drop_rates, run_numbers, buffer_size, period)
