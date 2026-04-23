#include <fstream>
#include <iostream>
#include <set>
#include <string>
#include <vector>
#include <limits>
#include <map>
#include <unordered_map>
#include <sstream>
//-----------------------

#include "rapidjson/include/rapidjson/document.h"
#include "rapidjson/include/rapidjson/istreamwrapper.h"
#include "rapidjson/include/rapidjson/writer.h"
#include "rapidjson/include/rapidjson/stringbuffer.h"

#include "AccessTime.hpp"
#include "Block.hpp"
#include "Graph.hpp"

// -----------------------

using namespace std;

vector<AccessTime*> trace;
vector<Block*> blocks; // basic blocks
std::unordered_map<string, string> ip2funcaddr;
std::unordered_map<int, int> blk2freq;
std::unordered_map<int, int> blk2dramfreq;
std::unordered_map<int, int> blk2cxlfreq;
map<unsigned long, int> ip2blkCache;
map<unsigned long, int> mem2blkCache;

struct TraceEntry {
    std::string instructionPointer;  // First column (IP)
    std::string physicalAddress;     // Third column (Physical Address)
    std::string inputtimestamp;             // Fourth column (ID)
    std::string outputtimestamp;           // Fifth column (Timestamp as string)
    std::string latency;                  // Seventh column (latency)
    std::string Tque_issue_all;
    std::string Tque_issue;
    std::string CMD_que_issue;
    unsigned long mappedIP; // Seventh column (converted to unsigned long long)

    TraceEntry(
        const std::string& ip,
        const std::string& physicalAddr,
        const std::string& inputtime,
        const std::string& outputtime,
        const std::string& latency,
        const std::string& tq_all,
        const std::string& tq,
        const std::string& cmdq,
        unsigned long long mappedIP
    ) : instructionPointer(ip),
        physicalAddress(physicalAddr),
        inputtimestamp(inputtime),
        outputtimestamp(outputtime),
        latency(latency),
        Tque_issue_all(tq_all),
        Tque_issue(tq),
        CMD_que_issue(cmdq),
        mappedIP(mappedIP) {}
};

vector<TraceEntry> traceEntries;

void jumpToLine(std::istream& os, int n)
{
	// Clear error flags, just in case.
	os.clear();
	
	// Start reading from the beginning of the file.
	os.seekg(0, std::ios::beg);
	
	// Skip to line n.
	for (int i = 1; i < n; ++i)
	{
		os.ignore(numeric_limits<streamsize>::max(), '\n');
	}
}
int getBlockId(unsigned long ip)
{
    if (ip2blkCache.find(ip) == ip2blkCache.end()) {
        int blockId = -1;
        for(auto b: blocks)
        {
            if(b->contains(ip))
            {
                blockId = b->id;
                break;
            }
        }
        ip2blkCache[ip] = blockId;
    } 
    return ip2blkCache.at(ip);
}

void readTrace2(string fileName) {
    cout << "Reading trace file in CSV format..." << endl;

    // Open the CSV file
    ifstream traceFile(fileName);

    jumpToLine(traceFile, 2);

    if (!traceFile.is_open()) {
        throw runtime_error("Could not open trace file: " + fileName);
    }

    string line;

    // Read each line of the CSV file
    while (getline(traceFile, line))
    {
        // Use a stringstream to parse the line
        stringstream ss(line);
        // Instruction Pointer,Physical Address,Input Timestamp (ns),Output Timestamp (ns),Latency (ns),Accepted into Queue,Operation,Tque,CMD_que,Channel,Rank,BG,bank
        string instructionPointer, physicalAddress, inputtimestamp, outputtimestamp, latency, AINTOQ, ops, TXNQ, CMDQ, channel, rank, bankgrp, bank,Tque_issue_all,Tque_issue,CMD_que_issue,mappedIPStr;

        // Read fields using comma as the delimiter
        getline(ss, instructionPointer, ',');
        getline(ss, physicalAddress, ',');
        getline(ss, inputtimestamp, ',');
        getline(ss, outputtimestamp, ',');
        getline(ss, latency, ',');
        getline(ss, AINTOQ, ',');
        getline(ss, ops, ',');
        getline(ss, TXNQ, ',');
        getline(ss, CMDQ, ',');
        getline(ss, channel, ',');
        getline(ss, rank, ',');
        getline(ss, bankgrp, ',');
        getline(ss, bank, ',');
        getline(ss, Tque_issue_all, ',');
        getline(ss, Tque_issue, ',');
        getline(ss, CMD_que_issue, ',');
        getline(ss, mappedIPStr, ',');

        //std::cout << "mappedIP : " << mappedIPStr << std::endl;
        // Convert the last column (compressedTimestampStr) to unsigned long
        unsigned long mappedIP = stoull(mappedIPStr, nullptr, 16); // Convert from hex

        // Create a TraceEntry struct and add it to the vector
        traceEntries.emplace_back(
            instructionPointer,
            physicalAddress,
            inputtimestamp,
            outputtimestamp,
            latency,
            Tque_issue_all,
            Tque_issue,
            CMD_que_issue,
            mappedIP
        );
    }

    traceFile.close();

    // Log the number of entries read
    cout << "Number of trace entries read: " << traceEntries.size() << endl;

    int i = 0;
    // (Optional) Print some entries for debugging
    for (const auto& entry : traceEntries)
    {
        cout << entry.instructionPointer << ',' << entry.physicalAddress << ',' << entry.inputtimestamp << ',' 
             << entry.outputtimestamp << ',' << entry.latency<< ',' << "0x" << std::hex 
             << entry.mappedIP << endl;
        i++;
        if(i == 10) break;
    }
}

void readBlocks(string fileName)
{
    cout << "Reading blocks file ..." << endl;
    int i = 0;
    string bStart, bEnd;
    ifstream blocksFile(fileName);
    rapidjson::IStreamWrapper isw { blocksFile };
    rapidjson::Document blks {};
    blks.ParseStream(isw);
    for (auto i = blks.MemberBegin(); i != blks.MemberEnd(); ++i)
    {
        blocks.push_back(new Block(
            stoi(i->name.GetString()),
            stoull(i->value["start"].GetString(), NULL, 16),
            stoull(i->value["end"].GetString(), NULL, 16)
        ));
    }

    cout << "Number of blocks read: " << blocks.size() << endl;
}

void dump_perblock_accesses(const char* outputdir)
{
    // Create a map of file streams for each block ID
    std::unordered_map<int, ofstream> blockFiles;

    for (const auto& trace : traceEntries)
    {
        // Get the instruction pointer from the trace entry (string)
        unsigned long ip = trace.mappedIP;  
        int blockId = getBlockId(ip);  // Determine the block ID for the instruction pointer

        if (blockId != -1)
        {
            // Open the file for the corresponding block ID if not already open
            if (blockFiles.find(blockId) == blockFiles.end())
            {
                std::string blockFileName = std::string(outputdir) + "/block_" + std::to_string(blockId) + ".csv";
                blockFiles[blockId].open(blockFileName, ios::out);

                blockFiles[blockId] << "Instruction Pointer,Physical Address,Input Timestamp (ns),Output Timestamp (ns),Latency (ns),Tque_issue_all,Tque_issue,CMD_que_issue" << endl;
            }

            // Write trace entry to the block file in the specified format
            blockFiles[blockId] << trace.instructionPointer << ","
                                << trace.physicalAddress << ","
                                << trace.inputtimestamp << ","
                                << trace.outputtimestamp << ","
                                << trace.latency << ","
                                << trace.Tque_issue_all << ","
                                << trace.Tque_issue << ","
                                << trace.CMD_que_issue << endl;
        }
    }

    // Close all open file streams
    for (auto& pair : blockFiles)
    {
        pair.second.close();
    }

    cout << "Dumped per-block accesses to CSV files." << endl;
}



void generateIPMemGraph()
{
    cout << "Graph Variant: IP+Mem Graph" << endl;
    cout << "Generating graph ..." << endl;
    Graph g(blocks.size() + 7);
    int prevBlockId = getBlockId(trace[0]->ip);
    unsigned long prevIP = trace[0]->ip;
    unsigned long prevAddr = trace[0]->addr;
    for(auto t: trace) {
        unsigned long ip = t->ip;
        unsigned long addr = t->addr;
        int blockId = getBlockId(t->ip);
        
        if(blockId != -1) {
            
            blk2freq[blockId]++;
        
            if ((blockId != -1 && prevBlockId != -1) && prevBlockId != blockId && (prevIP != ip || prevAddr != addr)) {
                g.addEdge(prevBlockId, blockId);
            }
            prevBlockId = blockId;
            prevAddr = addr;
        }
    }

}

int main(int argc, char** argv)
{
    if(argc != 4)
    {
        cout << "Invalid arguments!" << endl;
        cout << "Usage: ./perblkaccesses <tracefile> <blocksfile> <output-folder>" << endl;
        return 1;
    }

    char* traceFile = argv[1];
    char* blocksFile = argv[2];
    char* outputfolder = argv[3];
   
    try {
        readTrace2(traceFile);
        readBlocks(blocksFile);
        dump_perblock_accesses(outputfolder);

    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
    return 0;
}
