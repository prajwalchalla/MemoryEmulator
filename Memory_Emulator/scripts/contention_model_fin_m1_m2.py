#!/usr/bin/env python3

import os
import argparse
import pandas as pd
from collections import defaultdict
import configparser
import math

class DRAM:
    def __init__(self, num_channels, num_ranks, num_bank_groups_per_rank, num_banks_per_group, 
                 rows, columns, channel_size_mb, dram_size_mb, transaction_queue_length, cmd_queue_length, cmd_queue_per, 
                 tCK, CL, tRCD, tRP, tRAS, tWR, tRTP, CWL, tCCD_S, tCCD_L, tRRD_S, tRRD_L, tRTRS, address_mapping):
        self.num_channels = num_channels
        self.num_ranks = num_ranks
        self.num_bank_groups_per_rank = num_bank_groups_per_rank
        self.num_banks_per_group = num_banks_per_group
        self.rows = rows
        self.columns = columns
        self.channel_size_mb = channel_size_mb
        self.dram_size_mb = dram_size_mb
        self.transaction_queue_length = transaction_queue_length
        self.cmd_queue_length = cmd_queue_length
        self.cmd_queue_per = cmd_queue_per
        self.tCK = tCK
        
        # Translate timing cycles into real-time (ns)
        self.CL = CL * tCK
        self.tRCD = tRCD * tCK
        self.tRP = tRP * tCK
        self.tRAS = tRAS * tCK
        self.tWR = tWR * tCK
        self.tRTP = tRTP * tCK
        self.CWL = CWL * tCK
        self.tCCD_S = tCCD_S * tCK
        self.tCCD_L = tCCD_L * tCK
        self.tRRD_S = tRRD_S * tCK
        self.tRRD_L = tRRD_L * tCK
        self.tRTRS = tRTRS * tCK
        self.address_mapping = address_mapping
        
        # Data structures
        self.open_rows = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: None)))))
        self.bank_service_end_time = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: 0.0))))
        self.channel_service_end_time = defaultdict(float)
        self.rank_service_end_time = defaultdict(lambda: defaultdict(float))
        self.last_completion_time = defaultdict(float)
        self.total_accesses = 0
        self.row_hits = 0
        self.row_misses = 0
        self.request_size_bytes = 64
        
        # State tracking
        self.previous_channel_state = {}
        self.previous_rank_state = {}
        self.previous_bg_state = {}
        self.previous_bank_state = {}
        
        # Transaction queue
        self.transaction_queues = defaultdict(list)
        self.bank_cmd_queue = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
        
        # Statistics
        self.channel_latencies = defaultdict(list)
        self.total_blp = 0.0
        self.total_blp_samples = 0
    
    def decode_address(self, physical_address):
        num_channel_bits = int(math.log2(self.num_channels))
        num_rank_bits = int(math.log2(self.num_ranks))
        num_bankgroup_bits = int(math.log2(self.num_bank_groups_per_rank))
        num_banks_per_group_bits = int(math.log2(self.num_banks_per_group))
        num_row_bits = int(math.log2(self.rows))
        num_column_bits = int(math.log2(self.columns))
        
        field_widths = {'ch': num_channel_bits, 'ra': num_rank_bits, 'bg': num_bankgroup_bits, 
                        'ba': num_banks_per_group_bits, 'ro': num_row_bits, 'co': num_column_bits}
        field_pos = {'ch': 0, 'ra': 0, 'bg': 0, 'ba': 0, 'ro': 0, 'co': 0}
        
        pos = 0
        for i in range(len(self.address_mapping) - 2, -1, -2):
            token = self.address_mapping[i:i+2]
            field_pos[token] = pos
            pos += field_widths[token]
        
        channel = (physical_address >> field_pos['ch']) & ((1 << field_widths['ch']) - 1)
        rank = (physical_address >> field_pos['ra']) & ((1 << field_widths['ra']) - 1)
        bank_group = (physical_address >> field_pos['bg']) & ((1 << field_widths['bg']) - 1)
        bank = (physical_address >> field_pos['ba']) & ((1 << field_widths['ba']) - 1)
        row = (physical_address >> field_pos['ro']) & ((1 << field_widths['ro']) - 1)
        
        return channel, rank, bank_group, bank, row
    
    def access(self, channel, rank, bank_group, bank, row, timestamp, operation):
        self.total_accesses += 1
        previous_row = self.open_rows[channel][rank][bank_group][bank]
        access_type = 'row_hit' if previous_row == row else 'row_miss'
        if access_type == 'row_hit':
            self.row_hits += 1
        else:
            self.row_misses += 1
        
        service_start_time = max(
            timestamp, 
            self.bank_service_end_time[channel][rank][bank_group][bank]
        )
        
        service_time = self.calculate_service_time(channel, rank, bank_group, bank, previous_row, row, access_type, operation)
        
        completion_time = service_start_time + service_time
        self.bank_service_end_time[channel][rank][bank_group][bank] = completion_time
        self.channel_service_end_time[channel] = max(self.channel_service_end_time[channel], completion_time)
        self.rank_service_end_time[channel][rank] = max(self.rank_service_end_time[channel][rank], completion_time)
        self.last_completion_time[channel] = max(completion_time, self.last_completion_time[channel])
        
        latency = completion_time - timestamp
        self.channel_latencies[channel].append(latency)
        
        busy_banks = sum(
            self.bank_service_end_time[channel][rank][bg][b] > timestamp
            for r in self.bank_service_end_time[channel]
            for bg in self.bank_service_end_time[channel][rank]
            for b in self.bank_service_end_time[channel][rank][bg]
        )
        self.total_blp += busy_banks
        self.total_blp_samples += 1
        
        self.open_rows[channel][rank][bank_group][bank] = row
        self.previous_channel_state[(channel, rank, bank_group, bank)] = channel
        self.previous_rank_state[channel] = rank
        self.previous_bg_state[(channel, rank)] = bank_group
        self.previous_bank_state[(channel, rank, bank_group)] = bank
        
        return access_type, latency
    def access_queue(self, channel, rank, bank_group, bank, row, timestamp, operation, bank_end_time):
        #self.total_accesses += 1
        previous_row = self.open_rows[channel][rank][bank_group][bank]
        access_type = 'row_hit' if previous_row == row else 'row_miss'
        if access_type == 'row_hit':
            self.row_hits += 1
        else:
            self.row_misses += 1
        
        service_start_time = max(
            timestamp, 
            bank_end_time
        )
        
        service_time = self.calculate_service_time(channel, rank, bank_group, bank, previous_row, row, access_type, operation)
        
        completion_time = service_start_time + service_time
        
        latency = completion_time - timestamp
        
        self.open_rows[channel][rank][bank_group][bank] = row
        self.previous_channel_state[(channel, rank, bank_group, bank)] = channel

        self.previous_rank_state[channel] = rank
        self.previous_bg_state[(channel, rank)] = bank_group
        self.previous_bank_state[(channel, rank, bank_group)] = bank
        
        return access_type, latency
    
    def calculate_service_time(self, channel, rank, bank_group, bank, previous_row, row, access_type, operation):
        service_time = 0.0

        # Check for row conflict
        is_row_conflict = previous_row is not None and previous_row != row

        # Determine service time based on row hit or miss
        if access_type == 'row_hit':
            service_time = self.CL + (self.tRTP if operation == 'READ' else self.CWL + self.tWR)
        else:
            if is_row_conflict:
                service_time += self.tRP  # Precharge if previous row was different
            service_time += self.tRCD + self.CL
            if operation == 'READ':
                service_time += self.tRTP
            else:
                service_time += self.CWL + self.tWR

        # Add bank group delay if accessing the same bank group
        if self.previous_bg_state.get((channel, rank)) == bank_group:
            service_time += self.tCCD_L
        else:
            service_time += self.tCCD_S

        # Add rank switching delay if switching to a different rank
        if self.previous_rank_state.get(channel) != rank:
            service_time += self.tRTRS

        return service_time

    
    def get_statistics(self, last_timestamp, tot_rows, total_time_simulated=None):
        if total_time_simulated is None:
            total_time_simulated = max(self.last_completion_time.values())
        
        row_buffer_locality = self.row_hits / self.total_accesses if self.total_accesses > 0 else 0.0
        bank_level_parallelism = self.total_blp / self.total_blp_samples if self.total_blp_samples > 0 else 0.0
        total_bytes = self.total_accesses * self.request_size_bytes
        bandwidth_gbps_sim = (total_bytes * 1e9) / (total_time_simulated * 1024**3) if total_time_simulated else 0.0
        bandwidth_gbps_input = (tot_rows * self.request_size_bytes) / (last_timestamp) if last_timestamp else 0.0
        
        channel_avg_latencies = {
            channel: sum(latencies) / len(latencies) if latencies else 0 
            for channel, latencies in self.channel_latencies.items()
        }
        average_latency = sum(channel_avg_latencies.values()) / len(channel_avg_latencies) if channel_avg_latencies else 0
        
        return row_buffer_locality, bank_level_parallelism, bandwidth_gbps_sim, bandwidth_gbps_input, channel_avg_latencies, average_latency, total_time_simulated

class CXL:
    def __init__(self, DRAM_OBJ):
        if not isinstance(DRAM_OBJ, DRAM):
            raise ValueError("Expected Initialized DRAM class object")

        #Lets just resuse the attributes of DRAM object
        self.__dict__.update(DRAM_OBJ.__dict__)

    def update_cxl_attribute(self, **new_values):
        for key, value in new_values.items():
            if key in self.__dict__:
                self.__dict__[key] = value
            else:
                raise KeyError(f"Attribute '{key}' does not exist in original DRAM object")

    def __str__(self):
        return f"CXL({self.__dict__})"

    def decode_address(self, physical_address):
        num_channel_bits = int(math.log2(self.num_channels))
        num_rank_bits = int(math.log2(self.num_ranks))
        num_bankgroup_bits = int(math.log2(self.num_bank_groups_per_rank))
        num_banks_per_group_bits = int(math.log2(self.num_banks_per_group))
        num_row_bits = int(math.log2(self.rows))
        num_column_bits = int(math.log2(self.columns))
        
        field_widths = {'ch': num_channel_bits, 'ra': num_rank_bits, 'bg': num_bankgroup_bits, 
                        'ba': num_banks_per_group_bits, 'ro': num_row_bits, 'co': num_column_bits}
        field_pos = {'ch': 0, 'ra': 0, 'bg': 0, 'ba': 0, 'ro': 0, 'co': 0}
        
        pos = 0
        for i in range(len(self.address_mapping) - 2, -1, -2):
            token = self.address_mapping[i:i+2]
            field_pos[token] = pos
            pos += field_widths[token]
        
        channel = (physical_address >> field_pos['ch']) & ((1 << field_widths['ch']) - 1)
        rank = (physical_address >> field_pos['ra']) & ((1 << field_widths['ra']) - 1)
        bank_group = (physical_address >> field_pos['bg']) & ((1 << field_widths['bg']) - 1)
        bank = (physical_address >> field_pos['ba']) & ((1 << field_widths['ba']) - 1)
        row = (physical_address >> field_pos['ro']) & ((1 << field_widths['ro']) - 1)
        
        return channel, rank, bank_group, bank, row

    def access(self, channel, rank, bank_group, bank, row, timestamp, operation):
        self.total_accesses += 1
        previous_row = self.open_rows[channel][rank][bank_group][bank]
        access_type = 'row_hit' if previous_row == row else 'row_miss'
        if access_type == 'row_hit':
            self.row_hits += 1
        else:
            self.row_misses += 1
        
        service_start_time = max(
            timestamp, 
            self.bank_service_end_time[channel][rank][bank_group][bank]
        )
        
        service_time = self.calculate_service_time(channel, rank, bank_group, bank, previous_row, row, access_type, operation)
        
        completion_time = service_start_time + service_time
        self.bank_service_end_time[channel][rank][bank_group][bank] = completion_time
        self.channel_service_end_time[channel] = max(self.channel_service_end_time[channel], completion_time)
        self.rank_service_end_time[channel][rank] = max(self.rank_service_end_time[channel][rank], completion_time)
        self.last_completion_time[channel] = max(completion_time, self.last_completion_time[channel])
        
        latency = completion_time - timestamp
        self.channel_latencies[channel].append(latency)
        
        busy_banks = sum(
            self.bank_service_end_time[channel][rank][bg][b] > timestamp
            for r in self.bank_service_end_time[channel]
            for bg in self.bank_service_end_time[channel][rank]
            for b in self.bank_service_end_time[channel][rank][bg]
        )
        self.total_blp += busy_banks
        self.total_blp_samples += 1
        
        self.open_rows[channel][rank][bank_group][bank] = row
        self.previous_channel_state[(channel, rank, bank_group, bank)] = channel
        self.previous_rank_state[channel] = rank
        self.previous_bg_state[(channel, rank)] = bank_group
        self.previous_bank_state[(channel, rank, bank_group)] = bank
        return access_type, latency

    def access_queue(self, channel, rank, bank_group, bank, row, timestamp, operation, bank_end_time):
        #self.total_accesses += 1
        previous_row = self.open_rows[channel][rank][bank_group][bank]
        access_type = 'row_hit' if previous_row == row else 'row_miss'
        if access_type == 'row_hit':
            self.row_hits += 1
        else:
            self.row_misses += 1
        
        service_start_time = max(
            timestamp, 
            bank_end_time
        )
        
        service_time = self.calculate_service_time(channel, rank, bank_group, bank, previous_row, row, access_type, operation)
        
        completion_time = service_start_time + service_time
        
        latency = completion_time - timestamp
        self.open_rows[channel][rank][bank_group][bank] = row
        self.previous_channel_state[(channel, rank, bank_group, bank)] = channel
        self.previous_rank_state[channel] = rank
        self.previous_bg_state[(channel, rank)] = bank_group
        self.previous_bank_state[(channel, rank, bank_group)] = bank
        
        return access_type, latency
    
    def calculate_service_time(self, channel, rank, bank_group, bank, previous_row, row, access_type, operation):
        service_time = 0.0

        # Check for row conflict
        is_row_conflict = previous_row is not None and previous_row != row

        # Determine service time based on row hit or miss
        if access_type == 'row_hit':
            service_time = self.CL + (self.tRTP if operation == 'READ' else self.CWL + self.tWR)
        else:
            if is_row_conflict:
                service_time += self.tRP  # Precharge if previous row was different
            service_time += self.tRCD + self.CL
            if operation == 'READ':
                service_time += self.tRTP
            else:
                service_time += self.CWL + self.tWR

        # Add bank group delay if accessing the same bank group
        if self.previous_bg_state.get((channel, rank)) == bank_group:
            service_time += self.tCCD_L
        else:
            service_time += self.tCCD_S

        # Add rank switching delay if switching to a different rank
        if self.previous_rank_state.get(channel) != rank:
            service_time += self.tRTRS

        return service_time

    
    def get_statistics(self, last_timestamp, tot_rows, total_time_simulated=None):
        if total_time_simulated is None:
            total_time_simulated = max(self.last_completion_time.values())
        
        row_buffer_locality = self.row_hits / self.total_accesses if self.total_accesses > 0 else 0.0
        bank_level_parallelism = self.total_blp / self.total_blp_samples if self.total_blp_samples > 0 else 0.0
        total_bytes = self.total_accesses * self.request_size_bytes
        bandwidth_gbps_sim = (total_bytes * 1e9) / (total_time_simulated * 1024**3) if total_time_simulated else 0.0
        bandwidth_gbps_input = (tot_rows * self.request_size_bytes) / (last_timestamp) if last_timestamp else 0.0
        
        channel_avg_latencies = {
            channel: sum(latencies) / len(latencies) if latencies else 0 
            for channel, latencies in self.channel_latencies.items()
        }
        average_latency = sum(channel_avg_latencies.values()) / len(channel_avg_latencies) if channel_avg_latencies else 0
        
        return row_buffer_locality, bank_level_parallelism, bandwidth_gbps_sim, bandwidth_gbps_input, channel_avg_latencies, average_latency, total_time_simulated

def read_input_file(filename):
    return pd.read_csv(filename)


def model_contention_with_queue(accesses, dram_system, queue_filename):
    results = {
        'Instruction Pointer': [],
        'Physical Address': [],
        'Input Timestamp (ns)': [],
        'Output Timestamp (ns)': [],
        'Latency (ns)': [],
        'Accepted into Queue': [],
        'Operation': [],
        'Tque': [],
        'CMD_que': [],
        'Channel': [],
        'Rank': [],
        'BG': [],
        'bank': [], 
        'Tque_issue_all':[],
        'Tque_issue':[],
        'CMD_que_issue':[]  
    }
    avg_queue_latencies = defaultdict(float)
    queue_counts = defaultdict(int)
    
    # Reset DRAM state before processing
    dram_system.bank_service_end_time = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: 0.0))))
    dram_system.open_rows = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: None)))))
    dram_system.channel_service_end_time = defaultdict(float)
    dram_system.rank_service_end_time = defaultdict(lambda: defaultdict(float))
    dram_system.transaction_queues = defaultdict(list)
    dram_system.bank_cmd_queue = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    
    for index, access in accesses.iterrows():
        InstructionPointer = access['Instruction Pointer']
        physical_address = int(access['Physical Address'], 16)
        timestamp = access['Time Compressed Timestamp (ns)']
        operation = access['RW']
        (channel, rank, bank_group, bank, row) = dram_system.decode_address(physical_address)
        
        #Make changes here... Accept the transaction in trans queue of cmd queue...
        # Add to bank_cmd_queue or transaction_queues based on queue length
        if len(dram_system.transaction_queues[channel]) < dram_system.transaction_queue_length:
            accepted = True
            tqueue_length_issue = len(dram_system.transaction_queues[channel])
            cmdqueue_length_issue = len(dram_system.bank_cmd_queue[channel][rank][bank_group][bank])
            all_tqueue_lengths_issue = [len(dram_system.transaction_queues[ch]) for ch in range(dram_system.num_channels)]
            if len(dram_system.bank_cmd_queue[channel][rank][bank_group][bank]) < dram_system.cmd_queue_length:
                dram_system.bank_cmd_queue[channel][rank][bank_group][bank].append((physical_address, timestamp, operation, accepted, channel, rank, bank_group, bank, row, tqueue_length_issue, all_tqueue_lengths_issue, cmdqueue_length_issue))
            else:
                dram_system.transaction_queues[channel].append((physical_address, timestamp, operation, accepted, channel, rank, bank_group, bank, row, tqueue_length_issue, all_tqueue_lengths_issue, cmdqueue_length_issue))    
        else:
            accepted = False

        # Store keys in list for efficiency
        bank_cmd_keys = list(dram_system.bank_cmd_queue.keys())

        for f_channel in bank_cmd_keys:
            for f_rank in list(dram_system.bank_cmd_queue[f_channel].keys()):
                for f_bank_group in list(dram_system.bank_cmd_queue[f_channel][f_rank].keys()):
                    for f_bank in list(dram_system.bank_cmd_queue[f_channel][f_rank][f_bank_group].keys()):
                        
                        while dram_system.bank_cmd_queue[f_channel][f_rank][f_bank_group][f_bank]:
                            # Get and process first transaction (FIFO)
                            queued_physical_address, input_timestamp, queued_operation, queue_accepted, q_channel, q_rank, q_bank_group, q_bank, q_row, q_tqueue_length_issue, q_all_tqueue_lengths_issue, q_cmdqueue_length_issue = dram_system.bank_cmd_queue[f_channel][f_rank][f_bank_group][f_bank][0]
                            #queued_physical_address, input_timestamp, queued_operation, queue_accepted, q_channel, q_rank, q_bank_group, q_bank, q_row = dram_system.bank_cmd_queue[f_channel][f_rank][f_bank_group][f_bank][0]

                            #_, lat = dram_system.access(q_channel, q_rank, q_bank_group, q_bank, q_row, input_timestamp, queued_operation)
                            _, lat = dram_system.access_queue(q_channel, q_rank, q_bank_group, q_bank, q_row, input_timestamp, queued_operation,dram_system.bank_service_end_time[q_channel][q_rank][q_bank_group][q_bank])
                            
                            #dram_system.calculate_service_time(self, channel, rank, bank_group, bank, previous_row, row, access_type, operation):
                            output_timestamp = input_timestamp + lat

                            if output_timestamp <= timestamp:
                                # Remove processed transaction (FIFO)
                                dram_system.bank_cmd_queue[q_channel][q_rank][q_bank_group][q_bank].pop(0)
                                dram_system.bank_service_end_time[q_channel][q_rank][q_bank_group][q_bank]=output_timestamp
                                # Store results
                                results['Instruction Pointer'].append(InstructionPointer)
                                results['Physical Address'].append(queued_physical_address)
                                results['Input Timestamp (ns)'].append(input_timestamp)
                                results['Output Timestamp (ns)'].append(output_timestamp)
                                results['Latency (ns)'].append(lat)
                                results['Accepted into Queue'].append(queue_accepted)
                                results['Operation'].append(queued_operation)
                                results['Tque'].append(len(dram_system.transaction_queues[q_channel]))
                                results['CMD_que'].append(len(dram_system.bank_cmd_queue[q_channel][q_rank][q_bank_group][q_bank]))
                                results['Channel'].append(q_channel)
                                results['Rank'].append(q_rank)
                                results['BG'].append(q_bank_group)
                                results['bank'].append(q_bank)
                                results['Tque_issue_all'].append(q_all_tqueue_lengths_issue)  # Store all T_Queue lengths at issue time
                                results['Tque_issue'].append(q_tqueue_length_issue)
                                results['CMD_que_issue'].append(q_cmdqueue_length_issue)  # Store CMD_Queue length at issue time
                                

                                avg_queue_latencies[q_channel] += lat
                                queue_counts[q_channel] += 1
                                
                                for i, transaction in enumerate(dram_system.transaction_queues[q_channel]):

                                    (t_physical_address, t_timestamp, t_operation, t_accepted, t_channel, t_rank, t_bg, t_bank, t_row, t_tqueue_length_issue, t_all_tqueue_lengths_issue, t_cmdqueue_length_issue) = transaction
                                    #(t_physical_address, t_timestamp, t_operation, t_accepted, t_channel, t_rank, t_bg, t_bank, t_row) = transaction

                                    # Check if transaction matches the current bank
                                    if (t_channel == q_channel and t_rank == q_rank and 
                                        t_bg == q_bank_group and t_bank == q_bank):
                                    
                                        if(len(dram_system.bank_cmd_queue[q_channel][q_rank][q_bank_group][q_bank]) < dram_system.cmd_queue_length):    
                                        # Move transaction from transaction_queue to bank_cmd_queue
                                            dram_system.transaction_queues[q_channel].pop(i)  # Remove from FIFO queue
                                            
                                            dram_system.bank_cmd_queue[q_channel][q_rank][q_bank_group][q_bank].append(
                                                #(t_physical_address, t_timestamp, t_operation, t_accepted, t_channel, t_rank, t_bg, t_bank, t_row)
                                                (t_physical_address, t_timestamp, t_operation, t_accepted, t_channel, t_rank, t_bg, t_bank, t_row, t_tqueue_length_issue, t_all_tqueue_lengths_issue, t_cmdqueue_length_issue)
                                            )
                                        else:
                                            break 

                            else:
                                break

    avg_queue_latency = {
        channel: (avg_queue_latencies[channel] / queue_counts[channel]) if queue_counts[channel] > 0 else 0
        for channel in avg_queue_latencies
    }

    df = pd.DataFrame(results)
    df.to_csv(queue_filename, index=False)
    
    return results, avg_queue_latency


def model_contention(accesses, dram_system):
    read_latency_total = defaultdict(float)
    write_latency_total = defaultdict(float)
    read_count = defaultdict(int)
    write_count = defaultdict(int)
    interarrival_latency = defaultdict(float)
    previous_timestamp = None
    results = {
        'Instruction Pointer': [],
        'Access Type': [],
        'Physical Address': [],
        'ID': [],
        'Time Compressed Timestamp (ns)': [],
        'RW': [],
        'service_latency': [],
        'row_hit/miss': [],
        'operation': [],
        'channel': [],
        'rank': [],
        'bank_group': [],
        'bank': [],
        'row': []
    }
    
    for index, access in accesses.iterrows():
        physical_address = int(access['Physical Address'], 16)
        timestamp = access['Time Compressed Timestamp (ns)']
        operation = access['RW']
        
        (channel, rank, bank_group, bank, row) = dram_system.decode_address(physical_address)
        
        access_type, latency = dram_system.access(
            channel, rank, bank_group, bank, row, timestamp, operation
        )
        
        if operation == 'READ':
            read_latency_total[channel] += latency
            read_count[channel] += 1
        else:
            write_latency_total[channel] += latency
            write_count[channel] += 1
        
        results['Instruction Pointer'].append(access['Instruction Pointer'])
        results['Access Type'].append(access['Access Type'])
        results['Physical Address'].append(access['Physical Address'])
        results['ID'].append(access['ID'])
        results['Time Compressed Timestamp (ns)'].append(access['Time Compressed Timestamp (ns)'])
        results['RW'].append(access['RW'])
        results['service_latency'].append(latency)
        results['row_hit/miss'].append(access_type)
        results['operation'].append(operation)
        results['channel'].append(channel)
        results['rank'].append(rank)
        results['bank_group'].append(bank_group)
        results['bank'].append(bank)
        results['row'].append(row)
        
        if previous_timestamp is not None:
            interarrival_latency[channel] += (timestamp - previous_timestamp)
        previous_timestamp = timestamp
    
    avg_read_latency = {channel: (read_latency_total[channel] / read_count[channel]) if read_count[channel] > 0 else 0.0 
                        for channel in read_latency_total}
    avg_write_latency = {channel: (write_latency_total[channel] / write_count[channel]) if write_count[channel] > 0 else 0.0 
                         for channel in write_latency_total}
    avg_interarrival = {channel: (interarrival_latency[channel] / (read_count[channel] + write_count[channel] - 1)) if (read_count[channel] + write_count[channel]) > 1 else 0.0
                        for channel in interarrival_latency}
    
    last_timestamp = accesses['Time Compressed Timestamp (ns)'].iloc[-1]
    total_rows = len(accesses)
    
    return avg_read_latency, avg_write_latency, avg_interarrival, last_timestamp, total_rows, results

def save_results(data, filename):
    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)

def load_memory_parameters(filename):
    config = configparser.ConfigParser()
    config.read(filename)
    memory_parameters = {
        'channels': config.getint('MemoryParameters', 'channels'),
        'ranks': config.getint('MemoryParameters', 'ranks'),
        'bankgroups': config.getint('MemoryParameters', 'bankgroups'),
        'banks_per_group': config.getint('MemoryParameters', 'banks_per_group'),
        'rows': config.getint('MemoryParameters', 'rows'),
        'columns': config.getint('MemoryParameters', 'columns'),
        'channel_size_mb': config.getint('MemoryParameters', 'channel_size_mb'),
        'dram_size_mb': config.getint('MemoryParameters', 'dram_size_mb'),
        'transaction_queue_length': config.getint('MemoryParameters', 'transaction_queue_length', fallback=32),
        'cmd_queue_length': config.getint('MemoryParameters', 'cmd_queue_length', fallback=8),
        'cmd_queue_per': config.get('MemoryParameters', 'cmd_queue_per'),
        'tCK': config.getfloat('MemoryParameters', 'tCK'),
        'CL': config.getint('MemoryParameters', 'CL'),
        'tRCD': config.getint('MemoryParameters', 'tRCD'),
        'tRP': config.getint('MemoryParameters', 'tRP'),
        'tRAS': config.getint('MemoryParameters', 'tRAS'),
        'tWR': config.getint('MemoryParameters', 'tWR'),
        'tRTP': config.getint('MemoryParameters', 'tRTP'),
        'CWL': config.getint('MemoryParameters', 'CWL'),
        'tCCD_S': config.getint('MemoryParameters', 'tCCD_S'),
        'tCCD_L': config.getint('MemoryParameters', 'tCCD_L'),
        'tRRD_S': config.getint('MemoryParameters', 'tRRD_S'),
        'tRRD_L': config.getint('MemoryParameters', 'tRRD_L'),
        'tRTRS': config.getint('MemoryParameters', 'tRTRS'),
        'address_mapping': config.get('MemoryParameters', 'address_mapping', fallback='rochrababgco')
    }
    return memory_parameters

def main(output_folder, input_file):
    ini_file = 'memory_config.ini'
    apps = ["bfs"]  # Example application names
    run_numbers = ['0']  # Example run numbers

    # Ensure the output folder exists
    os.makedirs(output_folder, exist_ok=True)

    memory_parameters = load_memory_parameters(ini_file)

    # Open the summary.txt file in the output folder
    summary_file = os.path.join(output_folder, "summary.txt")
    with open(summary_file, "w") as summary:
        for app in apps:
            for run_number in run_numbers:

                dram_system = DRAM(
                    memory_parameters['channels'],
                    memory_parameters['ranks'],
                    memory_parameters['bankgroups'],
                    memory_parameters['banks_per_group'],
                    memory_parameters['rows'],
                    memory_parameters['columns'],
                    memory_parameters['channel_size_mb'],
                    memory_parameters['dram_size_mb'],
                    memory_parameters['transaction_queue_length'],
                    memory_parameters['cmd_queue_length'],
                    memory_parameters['cmd_queue_per'],
                    memory_parameters['tCK'],
                    memory_parameters['CL'],
                    memory_parameters['tRCD'],
                    memory_parameters['tRP'],
                    memory_parameters['tRAS'],
                    memory_parameters['tWR'],
                    memory_parameters['tRTP'],
                    memory_parameters['CWL'],
                    memory_parameters['tCCD_S'],
                    memory_parameters['tCCD_L'],
                    memory_parameters['tRRD_S'],
                    memory_parameters['tRRD_L'],
                    memory_parameters['tRTRS'],
                    memory_parameters['address_mapping']
                )
                accesses = read_input_file(input_file)
                avg_read_latency, avg_write_latency, avg_interarrival, last_timestamp, tot_rows, results = model_contention(accesses, dram_system)

                queue_file = os.path.join(output_folder, f"out_queue_{app}_{run_number}.csv")
                queue_results, avg_queue_latency = model_contention_with_queue(accesses, dram_system, queue_file)

                row_buffer_locality, bank_level_parallelism, bandwidth_gbps_sim, bandwidth_gbps_input, channel_avg_latencies, average_latency, total_time = dram_system.get_statistics(last_timestamp, tot_rows)

                # Prepare output file names
                results_file = os.path.join(output_folder, f"results_{app}_{run_number}.csv")

                # Write results to CSV
                save_results(results, results_file)
                #save_results(cxl_results, cxl_results_file)

                # Prepare and write summary content
                summary_content = f"{app} - Run {run_number}\n"
                summary_content += "Latency Calculations:\n"
                for channel in avg_read_latency:
                    summary_content += (
                        f"Channel {channel} - Average Read Latency: {avg_read_latency[channel]:.2f} ns, "
                        f"Average Write Latency: {avg_write_latency[channel]:.2f} ns, "
                        f"Average Interarrival Latency: {avg_interarrival[channel]:.2f} ns\n"
                        f"Channel {channel} - Average Queue Latency: {avg_queue_latency[channel]:.2f} ns\n"
                    )
                summary_content += "\nOverall:\n"
                summary_content += f"Row Buffer Locality (hit ratio): {row_buffer_locality:.2f}\n"
                summary_content += f"Bank Level Parallelism (avg busy banks): {bank_level_parallelism:.2f}\n"
                summary_content += f"Bandwidth with last simulated time: {bandwidth_gbps_sim:.2f} GB/s\n"
                summary_content += f"Bandwidth with last input timestamp: {bandwidth_gbps_input:.2f} GB/s\n"
                summary_content += f"Averaged Latency Across Channels: {average_latency:.2f} ns\n"
                summary_content += f"Total Simulated Time: {total_time:.2f} ns\n\n"

                print(summary_content)  # Print to console
                summary.write(summary_content)  # Write to summary.txt
               
                del summary_content

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process an input file and specify an output folder.")
    
    # Add arguments for output folder and input file
    parser.add_argument('--output_folder', type=str, required=True, help="Path to the output folder.")
    parser.add_argument('--input_file', type=str, required=True, help="Path to the input file.")
    # Parse the arguments
    args = parser.parse_args()
    # Call the main function and pass parsed arguments
    main(output_folder=args.output_folder, input_file=args.input_file)
