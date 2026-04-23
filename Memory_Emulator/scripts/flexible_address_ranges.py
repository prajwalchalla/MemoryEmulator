import sys
import math

def print_report(page_counts, total_pages, title):
    """Prints a formatted report of page allocation."""
    print(f"--- {title} ---")
    if total_pages == 0:
        print("No pages to report.")
        print("---------------------------------")
        return

    dram_pages = page_counts.get('Node 0', 0) + page_counts.get('Node 1', 0)
    cxl_pages = page_counts.get('Node 2', 0)
    
    dram_percent = (dram_pages / total_pages) * 100 if total_pages > 0 else 0
    cxl_percent = (cxl_pages / total_pages) * 100 if total_pages > 0 else 0

    print(f"DRAM Total (Node 0 + Node 1): {dram_percent:.2f}% ({dram_pages} pages)")
    print(f"CXL Total (Node 2): {cxl_percent:.2f}% ({cxl_pages} pages)")
    print("-" * 20)

    for name, count in sorted(page_counts.items()):
        percentage = (count / total_pages) * 100 if total_pages > 0 else 0
        print(f"{name}: {percentage:.2f}% ({count}/{total_pages} pages)")
    print("---------------------------------\n")


def print_range_report_2(numa_nodes, final_addresses, moved_lists):
    """Prints a report on the new effective address ranges after reallocation."""
    print("--- Effective Address Ranges After Reallocation ---")
    
    # Node 0
    original_node0 = numa_nodes[0]
    print(f"Node 0 (Original): {original_node0['start']} - {original_node0['end']} ({hex(original_node0['start'])} - {hex(original_node0['end'])})")

    moved_from_2_0 = moved_lists['Node 2_0']
    if moved_from_2_0:
        start, end = min(moved_from_2_0), max(moved_from_2_0)
        print(f"Node 0 (+ Reallocated from N2): {start} - {end} ({hex(start)} - {hex(end)})")

    # Node 1
    original_node1 = numa_nodes[1]
    print(f"Node 1 (Original): {original_node1['start']} - {original_node1['end']} ({hex(original_node1['start'])} - {hex(original_node1['end'])})")

    moved_from_2_1 = moved_lists['Node 2_1']
    if moved_from_2_1:
        start, end = min(moved_from_2_1), max(moved_from_2_1)
        print(f"Node 1 (+ Reallocated from N2): {start} - {end} ({hex(start)} - {hex(end)})")
    
    # Node 2
    remaining_node2 = final_addresses['Node 2']
    if remaining_node2:
        start, end = min(remaining_node2), max(remaining_node2)
        print(f"Node 2: {start} - {end} ({hex(start)} - {hex(end)})")
    else:
        print("Node 2: No pages remain in this node.")
    print("-------------------------------------------------")

def print_range_report(numa_nodes, final_addresses, moved_lists):
    """Prints a report on the new effective address ranges after reallocation."""
    print("--- Effective Address Ranges After Reallocation ---")
    
    # Node 0
    remaining_node0 = final_addresses['Node 0']
    if remaining_node0:
        start, end = min(remaining_node0), max(remaining_node0)
        print(f"Node 0: {start} - {end} ({hex(start)} - {hex(end)})")
    else:
        print("Node 0: No pages remain in this node.")

    # Node 1
    remaining_node1 = final_addresses['Node 1']
    if remaining_node1:
        start, end = min(remaining_node1), max(remaining_node1)
        print(f"Node 1: {start} - {end} ({hex(start)} - {hex(end)})")
    else:
        print("Node 1: No pages remain in this node.")

    # Node 2's range is now discontiguous
    original_node2 = numa_nodes[2]
    print(f"Node 2 (Original): {original_node2['start']} - {original_node2['end']} ({hex(original_node2['start'])} - {hex(original_node2['end'])})")
    
    moved_from_0 = moved_lists['Node 0']
    if moved_from_0:
        start, end = min(moved_from_0), max(moved_from_0)
        print(f"Node 2 (+ Reallocated from N0): {start} - {end} ({hex(start)} - {hex(end)})")

    moved_from_1 = moved_lists['Node 1']
    if moved_from_1:
        start, end = min(moved_from_1), max(moved_from_1)
        print(f"Node 2 (+ Reallocated from N1): {start} - {end} ({hex(start)} - {hex(end)})")
    print("-------------------------------------------------")


def analyze_and_reallocate(trace_file_path, dram_target_percent):
    """
    Analyzes and reallocates memory pages from a trace file based on a
    target DRAM vs. CXL percentage.
    """
    numa_nodes = [
        {'name': 'Node 0', 'start': 4294967296, 'end': 551903297535},
        {'name': 'Node 1', 'start': 1649267441664, 'end': 2199023255551},
        {'name': 'Node 2', 'start': 9345848836096, 'end': 9895604649983}
    ]

    
    node_addresses = {node['name']: [] for node in numa_nodes}
    node_addresses['Uncategorized'] = []
    
    try:
        with open(trace_file_path, 'r') as f:
            next(f)
            for line in f:
                parts = line.strip().split(',')
                if len(parts) < 3: continue
                try:
                    addr = int(parts[2], 16)
                    #print("addrs : ",addr)
                    categorized = False
                    for node in numa_nodes:
                        if node['start'] <= addr <= node['end']:
                            node_addresses[node['name']].append(addr)
                            categorized = True; break
                    if not categorized:
                        node_addresses['Uncategorized'].append(addr)
                except ValueError: continue
    except FileNotFoundError:
        print(f"Error: The file '{trace_file_path}' was not found."); return

    initial_page_counts = {name: len(addrs) for name, addrs in node_addresses.items()}
    total_pages = sum(initial_page_counts.values())
    if total_pages == 0:
        print("No valid memory accesses found in the trace file."); return

    print_report(initial_page_counts, total_pages, "Initial Allocation Report")

    initial_dram_pages = initial_page_counts['Node 0'] + initial_page_counts['Node 1']
    target_dram_pages = math.floor(total_pages * (dram_target_percent / 100.0))
    pages_to_reallocate = initial_dram_pages - target_dram_pages

    if pages_to_reallocate <= 0:
        pages_to_reallocate = -1 * pages_to_reallocate
        print(f"Targeting {dram_target_percent}% DRAM: Attempting to reallocate {pages_to_reallocate} pages from CXL to DRAM.\n")
        reallocated_addresses = {name: list(addrs) for name, addrs in node_addresses.items()}
        realloc_from_node2 = min(len(reallocated_addresses['Node 2']), math.ceil(pages_to_reallocate / 1.0))
        reallocated_addresses['Node 2'].sort(reverse=True)

        moved_from_2_to_0 = reallocated_addresses['Node 2'][:int(realloc_from_node2 / 2)]
        reallocated_addresses['Node 0'].extend(moved_from_2_to_0)
        reallocated_addresses['Node 2'] = reallocated_addresses['Node 2'][int(realloc_from_node2 / 2):]


        moved_from_2_to_1 = reallocated_addresses['Node 2'][:int(realloc_from_node2 / 2)]
        reallocated_addresses['Node 1'].extend(moved_from_2_to_1)
        reallocated_addresses['Node 2'] = reallocated_addresses['Node 2'][int(realloc_from_node2 / 2):]

        final_page_counts = {name: len(addrs) for name, addrs in reallocated_addresses.items()}
        print_report(final_page_counts, total_pages, "Reallocated Allocation Report")
        
        moved_lists = {'Node 2_0': moved_from_2_to_0, 'Node 2_1': moved_from_2_to_1}
        print_range_report_2(numa_nodes, reallocated_addresses, moved_lists)

        return

    print(f"Targeting {dram_target_percent}% DRAM: Attempting to reallocate {pages_to_reallocate} pages from DRAM to CXL.\n")
    
    reallocated_addresses = {name: list(addrs) for name, addrs in node_addresses.items()}
    realloc_from_node0 = min(len(reallocated_addresses['Node 0']), math.ceil(pages_to_reallocate / 2.0))
    realloc_from_node1 = min(len(reallocated_addresses['Node 1']), pages_to_reallocate - realloc_from_node0)

    # Sort to find highest addresses
    reallocated_addresses['Node 0'].sort(reverse=True)
    reallocated_addresses['Node 1'].sort(reverse=True)

    moved_from_0 = reallocated_addresses['Node 0'][:int(realloc_from_node0)]
    reallocated_addresses['Node 2'].extend(moved_from_0)
    reallocated_addresses['Node 0'] = reallocated_addresses['Node 0'][int(realloc_from_node0):]
    
    moved_from_1 = reallocated_addresses['Node 1'][:int(realloc_from_node1)]
    reallocated_addresses['Node 2'].extend(moved_from_1)
    reallocated_addresses['Node 1'] = reallocated_addresses['Node 1'][int(realloc_from_node1):]

    final_page_counts = {name: len(addrs) for name, addrs in reallocated_addresses.items()}
    print_report(final_page_counts, total_pages, "Reallocated Allocation Report")

    moved_lists = {'Node 0': moved_from_0, 'Node 1': moved_from_1}
    print_range_report(numa_nodes, reallocated_addresses, moved_lists)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python numa_alloc_analyzer.py <path_to_trace_file> <dram_target_percentage>")
        print("Example: python numa_alloc_analyzer.py trace.txt 50")
        sys.exit(1)
        
    trace_file = sys.argv[1]
    try:
        dram_target = float(sys.argv[2])
        if not (0 <= dram_target <= 100):
            raise ValueError("Percentage must be between 0 and 100.")
    except ValueError as e:
        print(f"Error: Invalid percentage provided. {e}")
        sys.exit(1)

    analyze_and_reallocate(trace_file, dram_target)
