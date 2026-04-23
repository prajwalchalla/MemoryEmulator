#include <bits/stdc++.h>
using namespace std;

struct DRAM {
    int num_channels;
    int num_ranks;
    int num_bank_groups_per_rank;
    int num_banks_per_group;
    int rows;
    int columns;
    int channel_size_mb;
    int dram_size_mb;
    int transaction_queue_length;
    int cmd_queue_length;
    string cmd_queue_per;
    double tCK;

    double CL;
    double tRCD;
    double tRP;
    double tRAS;
    double tWR;
    double tRTP;
    double CWL;
    double tCCD_S;
    double tCCD_L;
    double tRRD_S;
    double tRRD_L;
    double tRTRS;
    string address_mapping;

    // open_rows[channel][rank][bg][bank] = row
    map<int, map<int, map<int, map<int, long long>>>> open_rows;
    map<int, map<int, map<int, map<int, double>>>> bank_service_end_time;
    map<int, double> channel_service_end_time;
    map<int, map<int, double>> rank_service_end_time;
    map<int, double> last_completion_time;
    long long total_accesses = 0;
    long long row_hits = 0;
    long long row_misses = 0;
    int request_size_bytes = 64;

    map<tuple<int,int,int,int>, int> previous_channel_state;
    map<int, int> previous_rank_state;
    map<pair<int,int>, int> previous_bg_state;
    map<tuple<int,int,int>, int> previous_bank_state;

    map<int, vector<double>> channel_latencies;
    double total_blp = 0.0;
    long long total_blp_samples = 0;

    DRAM(int num_channels,
         int num_ranks,
         int num_bank_groups_per_rank,
         int num_banks_per_group,
         int rows,
         int columns,
         int channel_size_mb,
         int dram_size_mb,
         int transaction_queue_length,
         int cmd_queue_length,
         const string &cmd_queue_per,
         double tCK,
         int CL,
         int tRCD,
         int tRP,
         int tRAS,
         int tWR,
         int tRTP,
         int CWL,
         int tCCD_S,
         int tCCD_L,
         int tRRD_S,
         int tRRD_L,
         int tRTRS,
         const string &address_mapping)
    {
        this->num_channels = num_channels;
        this->num_ranks = num_ranks;
        this->num_bank_groups_per_rank = num_bank_groups_per_rank;
        this->num_banks_per_group = num_banks_per_group;
        this->rows = rows;
        this->columns = columns;
        this->channel_size_mb = channel_size_mb;
        this->dram_size_mb = dram_size_mb;
        this->transaction_queue_length = transaction_queue_length;
        this->cmd_queue_length = cmd_queue_length;
        this->cmd_queue_per = cmd_queue_per;
        this->tCK = tCK;

        this->CL = CL * tCK;
        this->tRCD = tRCD * tCK;
        this->tRP = tRP * tCK;
        this->tRAS = tRAS * tCK;
        this->tWR = tWR * tCK;
        this->tRTP = tRTP * tCK;
        this->CWL = CWL * tCK;
        this->tCCD_S = tCCD_S * tCK;
        this->tCCD_L = tCCD_L * tCK;
        this->tRRD_S = tRRD_S * tCK;
        this->tRRD_L = tRRD_L * tCK;
        this->tRTRS = tRTRS * tCK;
        this->address_mapping = address_mapping;
    }

    tuple<int,int,int,int,long long> decode_address(unsigned long long physical_address) {
        int num_channel_bits = (int)log2(num_channels);
        int num_rank_bits = (int)log2(num_ranks);
        int num_bankgroup_bits = (int)log2(num_bank_groups_per_rank);
        int num_banks_per_group_bits = (int)log2(num_banks_per_group);
        int num_row_bits = (int)log2(rows);
        int num_column_bits = (int)log2(columns);

        map<string,int> field_widths{
            {"ch", num_channel_bits},
            {"ra", num_rank_bits},
            {"bg", num_bankgroup_bits},
            {"ba", num_banks_per_group_bits},
            {"ro", num_row_bits},
            {"co", num_column_bits}
        };
        map<string,int> field_pos{
            {"ch", 0},
            {"ra", 0},
            {"bg", 0},
            {"ba", 0},
            {"ro", 0},
            {"co", 0}
        };

        int pos = 0;
        for (int i = (int)address_mapping.size() - 2; i >= 0; i -= 2) {
            string token = address_mapping.substr(i, 2);
            field_pos[token] = pos;
            pos += field_widths[token];
        }

        auto mask = [](int bits) {
            if (bits <= 0) return 0ULL;
            return (1ULL << bits) - 1ULL;
        };

        int channel = (int)((physical_address >> field_pos["ch"]) & mask(field_widths["ch"]));
        int rank = (int)((physical_address >> field_pos["ra"]) & mask(field_widths["ra"]));
        int bank_group = (int)((physical_address >> field_pos["bg"]) & mask(field_widths["bg"]));
        int bank = (int)((physical_address >> field_pos["ba"]) & mask(field_widths["ba"]));
        long long row = (long long)((physical_address >> field_pos["ro"]) & mask(field_widths["ro"]));

        return make_tuple(channel, rank, bank_group, bank, row);
    }

    double calculate_service_time(int channel, int rank, int bank_group, int bank,
                                  long long previous_row, long long row,
                                  const string &access_type, const string &operation)
    {
        double service_time = 0.0;
        bool is_row_conflict = (previous_row != -1 && previous_row != row);

        if (access_type == "row_hit") {
            if (operation == "READ") {
                service_time = CL + tRTP;
            } else {
                service_time = CL + (CWL + tWR); // close to Python logic; CWL used for write
            }
        } else {
            if (is_row_conflict) {
                service_time += tRP;
            }
            service_time += tRCD + CL;
            if (operation == "READ") {
                service_time += tRTP;
            } else {
                service_time += CWL + tWR;
            }
        }

        auto it_bg = previous_bg_state.find({channel, rank});
        if (it_bg != previous_bg_state.end() && it_bg->second == bank_group) {
            service_time += tCCD_L;
        } else {
            service_time += tCCD_S;
        }

        auto it_rank = previous_rank_state.find(channel);
        if (it_rank == previous_rank_state.end() || it_rank->second != rank) {
            service_time += tRTRS;
        }

        return service_time;
    }

    pair<string,double> access(int channel, int rank, int bank_group, int bank,
                               long long row, double timestamp, const string &operation)
    {
        total_accesses += 1;
        long long previous_row = -1;
        if (open_rows[channel][rank][bank_group].count(bank)) {
            previous_row = open_rows[channel][rank][bank_group][bank];
        }

        string access_type = (previous_row == row ? "row_hit" : "row_miss");
        if (access_type == "row_hit") row_hits += 1;
        else row_misses += 1;

        double prev_end = bank_service_end_time[channel][rank][bank_group][bank];
        double service_start_time = max(timestamp, prev_end);
        double service_time = calculate_service_time(channel, rank, bank_group, bank,
                                                     previous_row, row, access_type, operation);
        double completion_time = service_start_time + service_time;
        bank_service_end_time[channel][rank][bank_group][bank] = completion_time;
        channel_service_end_time[channel] = max(channel_service_end_time[channel], completion_time);
        rank_service_end_time[channel][rank] = max(rank_service_end_time[channel][rank], completion_time);
        last_completion_time[channel] = max(last_completion_time[channel], completion_time);

        double latency = completion_time - timestamp;

        channel_latencies[channel].push_back(latency);

        int busy_banks = 0;
        // very literal but slightly off from Python structure; kept simple
        for (auto &r_pair : bank_service_end_time[channel]) {
            for (auto &bg_pair : r_pair.second) {
                for (auto &b_pair : bg_pair.second) {
                    if (b_pair.second > timestamp) busy_banks++;
                }
            }
        }
        total_blp += busy_banks;
        total_blp_samples += 1;

        open_rows[channel][rank][bank_group][bank] = row;
        previous_channel_state[{channel, rank, bank_group, bank}] = channel;
        previous_rank_state[channel] = rank;
        previous_bg_state[{channel, rank}] = bank_group;
        previous_bank_state[{channel, rank, bank_group}] = bank;

        return {access_type, latency};
    }

    pair<string,double> access_queue(int channel, int rank, int bank_group, int bank,
                                     long long row, double timestamp,
                                     const string &operation, double bank_end_time)
    {
        long long previous_row = -1;
        if (open_rows[channel][rank][bank_group].count(bank)) {
            previous_row = open_rows[channel][rank][bank_group][bank];
        }
        string access_type = (previous_row == row ? "row_hit" : "row_miss");
        if (access_type == "row_hit") row_hits += 1;
        else row_misses += 1;

        double service_start_time = max(timestamp, bank_end_time);
        double service_time = calculate_service_time(channel, rank, bank_group, bank,
                                                     previous_row, row, access_type, operation);
        double completion_time = service_start_time + service_time;
        double latency = completion_time - timestamp;

        open_rows[channel][rank][bank_group][bank] = row;
        previous_channel_state[{channel, rank, bank_group, bank}] = channel;
        previous_rank_state[channel] = rank;
        previous_bg_state[{channel, rank}] = bank_group;
        previous_bank_state[{channel, rank, bank_group}] = bank;

        return {access_type, latency};
    }

    tuple<double,double,double,double,map<int,double>,double,double>
    get_statistics(double last_timestamp, long long tot_rows, double total_time_simulated = -1.0)
    {
        if (total_time_simulated < 0.0) {
            total_time_simulated = 0.0;
            for (auto &p : last_completion_time) {
                total_time_simulated = max(total_time_simulated, p.second);
            }
        }

        double row_buffer_locality = (total_accesses > 0)
            ? (double)row_hits / (double)total_accesses : 0.0;
        double bank_level_parallelism = (total_blp_samples > 0)
            ? total_blp / (double)total_blp_samples : 0.0;

        double total_bytes = (double)total_accesses * (double)request_size_bytes;
        double bandwidth_gbps_sim = (total_time_simulated > 0.0)
            ? (total_bytes * 1e9) / (total_time_simulated * pow(1024.0, 3.0))
            : 0.0;
        double bandwidth_gbps_input = (last_timestamp > 0.0)
            ? (tot_rows * (double)request_size_bytes) / last_timestamp
            : 0.0;

        map<int,double> channel_avg_latencies;
        for (auto &p : channel_latencies) {
            double sum = 0.0;
            for (double v : p.second) sum += v;
            channel_avg_latencies[p.first] =
                (!p.second.empty() ? sum / (double)p.second.size() : 0.0);
        }

        double average_latency = 0.0;
        if (!channel_avg_latencies.empty()) {
            double sum = 0.0;
            for (auto &p : channel_avg_latencies) sum += p.second;
            average_latency = sum / (double)channel_avg_latencies.size();
        }

        return make_tuple(row_buffer_locality,
                          bank_level_parallelism,
                          bandwidth_gbps_sim,
                          bandwidth_gbps_input,
                          channel_avg_latencies,
                          average_latency,
                          total_time_simulated);
    }
};

// --- Simple data structures mirroring the CSV columns ---

static inline void trim_string(string &s) {
    while (!s.empty() && isspace((unsigned char)s.back())) s.pop_back();
    size_t i = 0;
    while (i < s.size() && isspace((unsigned char)s[i])) i++;
    s = s.substr(i);
}

struct AccessRecord {
    string instruction_pointer;
    string access_type;
    string physical_address_str;
    string id;
    double timestamp_ns;
    string rw;
};

// simple CSV parser: assumes header present and comma-separated, no quotes
vector<AccessRecord> read_input_file(const string &filename) {
    vector<AccessRecord> records;
    ifstream fin(filename);
    if (!fin.is_open()) {
        cerr << "Failed to open input file: " << filename << "\n";
        return records;
    }
    string line;
    // skip header
    if (!getline(fin, line)) {
        return records;
    }
    while (getline(fin, line)) {
        if (line.empty()) continue;
        vector<string> cols;
        string cur;
        stringstream ss(line);
        while (getline(ss, cur, ',')) {
            trim_string(cur);
            cols.push_back(cur);
        }
        // expecting at least relevant fields by index:
        // we will map roughly by name: 
        // "Instruction Pointer","Access Type","Physical Address","ID","Time Compressed Timestamp (ns)","RW",...
        if (cols.size() < 6) continue;
        AccessRecord ar;
        ar.instruction_pointer = cols[0];
        ar.access_type = cols[1];
        ar.physical_address_str = cols[2];
        ar.id = cols[3];
        ar.timestamp_ns = stod(cols[4]);
        ar.rw = cols[5];
        records.push_back(ar);
    }
    return records;
}

// memory parameters struct
struct MemoryParameters {
    int channels;
    int ranks;
    int bankgroups;
    int banks_per_group;
    int rows;
    int columns;
    int channel_size_mb;
    int dram_size_mb;
    int transaction_queue_length;
    int cmd_queue_length;
    string cmd_queue_per;
    double tCK;
    int CL;
    int tRCD;
    int tRP;
    int tRAS;
    int tWR;
    int tRTP;
    int CWL;
    int tCCD_S;
    int tCCD_L;
    int tRRD_S;
    int tRRD_L;
    int tRTRS;
    string address_mapping;
};

// naive INI parser for [MemoryParameters] section
MemoryParameters load_memory_parameters(const string &filename) {
    MemoryParameters mp{};
    mp.transaction_queue_length = 32;
    mp.cmd_queue_length = 8;
    mp.cmd_queue_per = "";
    mp.address_mapping = "rochrababgco";

    ifstream fin(filename);
    if (!fin.is_open()) {
        cerr << "Failed to open ini file: " << filename << "\n";
        return mp;
    }
    string line;
    bool in_section = false;
    while (getline(fin, line)) {
        if (line.empty()) continue;
        // trim
        auto trim = [](string &s){
            while (!s.empty() && isspace((unsigned char)s.back())) s.pop_back();
            size_t i = 0;
            while (i < s.size() && isspace((unsigned char)s[i])) i++;
            s = s.substr(i);
        };
        trim(line);
        if (line.empty() || line[0] == '#') continue;
        if (line[0] == '[') {
            in_section = (line == "[MemoryParameters]");
            continue;
        }
        if (!in_section) continue;
        size_t eq = line.find('=');
        if (eq == string::npos) continue;
        string key = line.substr(0, eq);
        string val = line.substr(eq + 1);
        trim(key);
        trim(val);

        if (key == "channels") mp.channels = stoi(val);
        else if (key == "ranks") mp.ranks = stoi(val);
        else if (key == "bankgroups") mp.bankgroups = stoi(val);
        else if (key == "banks_per_group") mp.banks_per_group = stoi(val);
        else if (key == "rows") mp.rows = stoi(val);
        else if (key == "columns") mp.columns = stoi(val);
        else if (key == "channel_size_mb") mp.channel_size_mb = stoi(val);
        else if (key == "dram_size_mb") mp.dram_size_mb = stoi(val);
        else if (key == "transaction_queue_length") mp.transaction_queue_length = stoi(val);
        else if (key == "cmd_queue_length") mp.cmd_queue_length = stoi(val);
        else if (key == "cmd_queue_per") mp.cmd_queue_per = val;
        else if (key == "tCK") mp.tCK = stod(val);
        else if (key == "CL") mp.CL = stoi(val);
        else if (key == "tRCD") mp.tRCD = stoi(val);
        else if (key == "tRP") mp.tRP = stoi(val);
        else if (key == "tRAS") mp.tRAS = stoi(val);
        else if (key == "tWR") mp.tWR = stoi(val);
        else if (key == "tRTP") mp.tRTP = stoi(val);
        else if (key == "CWL") mp.CWL = stoi(val);
        else if (key == "tCCD_S") mp.tCCD_S = stoi(val);
        else if (key == "tCCD_L") mp.tCCD_L = stoi(val);
        else if (key == "tRRD_S") mp.tRRD_S = stoi(val);
        else if (key == "tRRD_L") mp.tRRD_L = stoi(val);
        else if (key == "tRTRS") mp.tRTRS = stoi(val);
        else if (key == "address_mapping") mp.address_mapping = val;
    }
    return mp;
}

// globals as in Python code
long long TOTAL_DRAM_VOTES = 0;
long long TOTAL_CXL_VOTES = 0;
long long TOTAL_STALL = 0;
long long CXL_ONLY_STALL = 0;
long long DRAM_ONLY_STALL = 0;


// model_contention equivalent
tuple<map<int,double>, map<int,double>, map<int,double>,
      double, long long,
      map<string, vector<string>>>
model_contention(const vector<AccessRecord> &accesses,
                 const string &ini_file,
                 const string &cxl_ini_file)
{
    map<int,double> read_latency_total;
    map<int,double> write_latency_total;
    map<int,int> read_count;
    map<int,int> write_count;
    map<int,double> interarrival_latency;

    map<string, vector<string>> results;
    vector<string> keys = {
        "Instruction Pointer","Access Type","Physical Address","ID",
        "Time Compressed Timestamp (ns)","RW","service_latency","row_hit/miss",
        "operation","channel","rank","bank_group","bank","row",
        "New Time Stamp (ns)","Stall"
    };
    for (auto &k : keys) results[k] = {};

    double time_offset = 0.0;
    long long stall = 0;
    long long block_id = 0;

    MemoryParameters memory_parameters = load_memory_parameters(ini_file); //DRAM Config
    MemoryParameters cxl_memory_parameters = load_memory_parameters(cxl_ini_file); //CXL Config

    TOTAL_DRAM_VOTES = 0;
    TOTAL_CXL_VOTES = 0;
    TOTAL_STALL = 0;
    CXL_ONLY_STALL = 0;
    DRAM_ONLY_STALL = 0;

    double last_chunk_completed_ts = 0.0;
    double last_dram_ts_in_chunk = -1.0;
    double last_dram_ets_in_chunk = -1.0;
    double last_cxl_ts_in_chunk = -1.0;
    double last_cxl_ets_in_chunk = -1.0;
    long long index = 0;
    long long i = 0;

    
    vector<double> chunk_end_50_50;
    vector<double> chunk_end_100_dram;
    // ---------------------------------------------------------

    for (i = 0; i < (long long)accesses.size(); i += 512) {
        DRAM local_dram_obj(
            memory_parameters.channels,
            memory_parameters.ranks,
            memory_parameters.bankgroups,
            memory_parameters.banks_per_group,
            memory_parameters.rows,
            memory_parameters.columns,
            memory_parameters.channel_size_mb,
            memory_parameters.dram_size_mb,
            memory_parameters.transaction_queue_length,
            memory_parameters.cmd_queue_length,
            memory_parameters.cmd_queue_per,
            memory_parameters.tCK,
            memory_parameters.CL,
            memory_parameters.tRCD,
            memory_parameters.tRP,
            memory_parameters.tRAS,
            memory_parameters.tWR,
            memory_parameters.tRTP,
            memory_parameters.CWL,
            memory_parameters.tCCD_S,
            memory_parameters.tCCD_L,
            memory_parameters.tRRD_S,
            memory_parameters.tRRD_L,
            memory_parameters.tRTRS,
            memory_parameters.address_mapping
        );

        DRAM local_cxl_obj(
            cxl_memory_parameters.channels,
            cxl_memory_parameters.ranks,
            cxl_memory_parameters.bankgroups,
            cxl_memory_parameters.banks_per_group,
            cxl_memory_parameters.rows,
            cxl_memory_parameters.columns,
            cxl_memory_parameters.channel_size_mb,
            cxl_memory_parameters.dram_size_mb,
            cxl_memory_parameters.transaction_queue_length,
            cxl_memory_parameters.cmd_queue_length,
            cxl_memory_parameters.cmd_queue_per,
            cxl_memory_parameters.tCK,
            cxl_memory_parameters.CL,
            cxl_memory_parameters.tRCD,
            cxl_memory_parameters.tRP,
            cxl_memory_parameters.tRAS,
            cxl_memory_parameters.tWR,
            cxl_memory_parameters.tRTP,
            cxl_memory_parameters.CWL,
            cxl_memory_parameters.tCCD_S,
            cxl_memory_parameters.tCCD_L,
            cxl_memory_parameters.tRRD_S,
            cxl_memory_parameters.tRRD_L,
            cxl_memory_parameters.tRTRS,
            cxl_memory_parameters.address_mapping
        );

        long long start_idx = i;
        long long end_idx = min((long long)accesses.size(), i + 512);

        if (start_idx >= (long long)accesses.size()) break;

        if (index % 512000 == 0) {
            //cout << "New Block : " << block_id << "\n";
        }

        double dram_latency = 0.0;
        double cxl_latency = 0.0;
        
        TOTAL_STALL = TOTAL_STALL + stall;

        for (long long idx = start_idx; idx < end_idx; ++idx) {
            const AccessRecord &access = accesses[idx];

            unsigned long long physical_address = strtoull(access.physical_address_str.c_str(), nullptr, 16);
            double timestamp = access.timestamp_ns;
            string operation = access.rw;

            if ((index % 512 == 0) && (last_chunk_completed_ts > timestamp)) {
                time_offset = last_chunk_completed_ts - timestamp;
            } else if ((index % 512 == 0) && (timestamp >= last_chunk_completed_ts)) {
                time_offset = 0;
            }

            if (time_offset < 0) {
                cerr << "Assertion failed: time_offset >= 0\n";
                time_offset = 0.0;
            }

            double effective_timestamp = timestamp + time_offset;


            // Obtained by DMESG SRAT
            bool is_dram =
                (0ULL <= physical_address && physical_address <= 2147483647ULL) ||
                (4294967296ULL <= physical_address && physical_address <= 277025390591ULL) ||
                (6730213752832ULL <= physical_address && physical_address <= 7005091659775ULL);

            dram_latency = 0.0;
            cxl_latency = 0.0;

            string access_type;
            int channel, rank, bank_group, bank;
            long long row;

            if (is_dram) {
                tie(channel, rank, bank_group, bank, row) = local_dram_obj.decode_address(physical_address);
                {
                    auto res = local_dram_obj.access(channel, rank, bank_group, bank, row, effective_timestamp, operation);
                    access_type = res.first;
                    dram_latency = res.second;
                }
                last_dram_ets_in_chunk = effective_timestamp;
            } else {
                tie(channel, rank, bank_group, bank, row) = local_cxl_obj.decode_address(physical_address);
                {
                    auto res = local_cxl_obj.access(channel, rank, bank_group, bank, row, effective_timestamp, operation);
                    access_type = res.first;
                    cxl_latency = res.second;
                }
                last_cxl_ets_in_chunk = effective_timestamp;
            }

            double latency = max(dram_latency, cxl_latency);

            if (operation == "READ") {
                read_latency_total[channel] += latency;
                read_count[channel] += 1;
            } else {
                write_latency_total[channel] += latency;
                write_count[channel] += 1;
            }

            // push to results
            results["Instruction Pointer"].push_back(access.instruction_pointer);
            results["Access Type"].push_back(access.access_type);
            results["Physical Address"].push_back(access.physical_address_str);
            results["ID"].push_back(access.id);
            results["Time Compressed Timestamp (ns)"].push_back(to_string(timestamp));
            results["RW"].push_back(access.rw);
            results["service_latency"].push_back(to_string(latency));
            results["row_hit/miss"].push_back(access_type);
            results["operation"].push_back(operation);
            results["channel"].push_back(to_string(channel));
            results["rank"].push_back(to_string(rank));
            results["bank_group"].push_back(to_string(bank_group));
            results["bank"].push_back(to_string(bank));
            results["row"].push_back(to_string(row));
            results["New Time Stamp (ns)"].push_back(to_string(effective_timestamp));
            results["Stall"].push_back(to_string(stall));

            index++;
        }

        double this_chunk_dram_completion_time = last_dram_ets_in_chunk + dram_latency;
        double this_chunk_cxl_completion_time  = last_cxl_ets_in_chunk + cxl_latency;

        last_chunk_completed_ts = max(this_chunk_dram_completion_time, this_chunk_cxl_completion_time);
        stall = llabs((long long)(this_chunk_dram_completion_time - this_chunk_cxl_completion_time));


        if (this_chunk_dram_completion_time > this_chunk_cxl_completion_time) {
            TOTAL_DRAM_VOTES += 1;
            DRAM_ONLY_STALL += stall;
            std::cout << "STALL BY DRAM : " << stall << " " << this_chunk_dram_completion_time<< std::endl;
        } else {
            TOTAL_CXL_VOTES += 1;
            CXL_ONLY_STALL += stall;
            std::cout << "STALL BY CXL : " << stall << " " << this_chunk_cxl_completion_time<< std::endl;
        }
        block_id += 1;
    }


    map<int,double> avg_read_latency;
    for (auto &p : read_latency_total) {
        int channel = p.first;
        if (read_count[channel] > 0) {
            avg_read_latency[channel] = p.second / (double)read_count[channel];
        } else {
            avg_read_latency[channel] = 0.0;
        }
    }

    map<int,double> avg_write_latency;
    for (auto &p : write_latency_total) {
        int channel = p.first;
        if (write_count[channel] > 0) {
            avg_write_latency[channel] = p.second / (double)write_count[channel];
        } else {
            avg_write_latency[channel] = 0.0;
        }
    }

    map<int,double> avg_interarrival;
    for (auto &p : interarrival_latency) {
        int channel = p.first;
        int total = read_count[channel] + write_count[channel];
        if (total > 1) {
            avg_interarrival[channel] = p.second / (double)(total - 1);
        } else {
            avg_interarrival[channel] = 0.0;
        }
    }

    double last_timestamp = 0.0;
    if (!accesses.empty()) {
        last_timestamp = accesses.back().timestamp_ns;
    }
    long long total_rows = (long long)accesses.size();

    return make_tuple(avg_read_latency,
                      avg_write_latency,
                      avg_interarrival,
                      last_timestamp,
                      total_rows,
                      results);
}

void save_results(const map<string, vector<string>> &data,
                  const string &filename)
{
    ofstream fout(filename);
    if (!fout.is_open()) {
        cerr << "Failed to open output file: " << filename << "\n";
        return;
    }

    // header
    bool first = true;
    for (auto &p : data) {
        if (!first) fout << ",";
        fout << p.first;
        first = false;
    }
    fout << "\n";

    size_t nrows = 0;
    for (auto &p : data) {
        nrows = max(nrows, p.second.size());
    }

    for (size_t r = 0; r < nrows; ++r) {
        bool first_col = true;
        for (auto &p : data) {
            if (!first_col) fout << ",";
            if (r < p.second.size()) fout << p.second[r];
            first_col = false;
        }
        fout << "\n";
    }
}

int main(int argc, char *argv[]) {
    string output_folder;
    string input_file;

    // very simple arg parsing: --output_folder X --input_file Y
    for (int i = 1; i < argc; ++i) {
        string arg = argv[i];
        if (arg == "--output_folder" && i + 1 < argc) {
            output_folder = argv[++i];
        } else if (arg == "--input_file" && i + 1 < argc) {
            input_file = argv[++i];
        }
    }

    if (output_folder.empty() || input_file.empty()) {
        cerr << "Usage: " << argv[0]
             << " --output_folder <path> --input_file <path>\n";
        return 1;
    }

    string ini_file = "memory_config.ini";
    string cxl_ini_file = "cxl_memory_config.ini";
    vector<string> apps = {"bfs"};
    vector<string> run_numbers = {"0"};

    // create output folder (POSIX style)
    string mkdir_cmd = "mkdir -p \"" + output_folder + "\"";
    system(mkdir_cmd.c_str());

    MemoryParameters memory_parameters = load_memory_parameters(ini_file);

    string summary_file = output_folder + "/summary.txt";
    ofstream summary(summary_file);
    if (!summary.is_open()) {
        cerr << "Failed to open summary file: " << summary_file << "\n";
        return 1;
    }

    for (const string &app : apps) {
        for (const string &run_number : run_numbers) {
            vector<AccessRecord> accesses = read_input_file(input_file);
            auto mc_res = model_contention(accesses, ini_file, cxl_ini_file);

            map<int,double> avg_read_latency = get<0>(mc_res);
            map<int,double> avg_write_latency = get<1>(mc_res);
            map<int,double> avg_interarrival = get<2>(mc_res);
            double last_timestamp = get<3>(mc_res);
            long long tot_rows = get<4>(mc_res);
            map<string, vector<string>> results = get<5>(mc_res);

            // create a DRAM object just to get_statistics
            DRAM dram_system(
                memory_parameters.channels,
                memory_parameters.ranks,
                memory_parameters.bankgroups,
                memory_parameters.banks_per_group,
                memory_parameters.rows,
                memory_parameters.columns,
                memory_parameters.channel_size_mb,
                memory_parameters.dram_size_mb,
                memory_parameters.transaction_queue_length,
                memory_parameters.cmd_queue_length,
                memory_parameters.cmd_queue_per,
                memory_parameters.tCK,
                memory_parameters.CL,
                memory_parameters.tRCD,
                memory_parameters.tRP,
                memory_parameters.tRAS,
                memory_parameters.tWR,
                memory_parameters.tRTP,
                memory_parameters.CWL,
                memory_parameters.tCCD_S,
                memory_parameters.tCCD_L,
                memory_parameters.tRRD_S,
                memory_parameters.tRRD_L,
                memory_parameters.tRTRS,
                memory_parameters.address_mapping
            );

            auto stats = dram_system.get_statistics(last_timestamp, tot_rows);
            double row_buffer_locality = get<0>(stats);
            double bank_level_parallelism = get<1>(stats);
            double bandwidth_gbps_sim = get<2>(stats);
            double bandwidth_gbps_input = get<3>(stats);
            map<int,double> channel_avg_latencies = get<4>(stats);
            double average_latency = get<5>(stats);
            double total_time = get<6>(stats);

            string results_file = output_folder + "/results_" + app + "_" + run_number + ".csv";
            save_results(results, results_file);

            stringstream ss;
            ss << app << " - Run " << run_number << "\n";
            ss << "Latency Calculations:\n";
            for (auto &p : avg_read_latency) {
                int channel = p.first;
                ss << "Channel " << channel
                   << " - Average Read Latency: " << fixed << setprecision(2)
                   << avg_read_latency[channel] << " ns, "
                   << "Average Write Latency: " << avg_write_latency[channel] << " ns, "
                   << "Average Interarrival Latency: " << avg_interarrival[channel] << " ns\n";
            }
            ss << "\nOverall:\n";
            ss << "Row Buffer Locality (hit ratio): " << fixed << setprecision(2)
               << row_buffer_locality << "\n";
            ss << "Bank Level Parallelism (avg busy banks): " << fixed << setprecision(2)
               << bank_level_parallelism << "\n";
            ss << "Bandwidth with last simulated time: " << fixed << setprecision(2)
               << bandwidth_gbps_sim << " GB/s\n";
            ss << "Bandwidth with last input timestamp: " << fixed << setprecision(2)
               << bandwidth_gbps_input << " GB/s\n";
            ss << "Averaged Latency Across Channels: " << fixed << setprecision(2)
               << average_latency << " ns\n";
            ss << "Total Simulated Time: " << fixed << setprecision(2)
               << total_time << " ns\n\n";

            string summary_content = ss.str();
            cout << summary_content;
            summary << summary_content;

            std::cout << "DRAM VOTES : " << TOTAL_DRAM_VOTES << std::endl;
            std::cout << "CXL VOTES  : " << TOTAL_CXL_VOTES << std::endl;
            std::cout << "TOTAL STALL : " << TOTAL_STALL << std::endl;
            std::cout << "DRAM ONLY STALL : " << DRAM_ONLY_STALL << std::endl;
            std::cout << "CXL ONLY STALL  : " << CXL_ONLY_STALL << std::endl;
        }
    }

    return 0;
}
