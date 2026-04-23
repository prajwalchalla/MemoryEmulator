#include <fstream>
#include <iostream>
#include <set>
#include <string>
#include <vector>
#include <limits>
#include <map>
#include <unordered_map>
#include <sstream>
#include <unordered_map>
#include <set>
#include <utility>
#include <iostream>
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
std::unordered_map<int, std::pair<int, std::set<unsigned long long>>> blk2freq; //blkid-> {total accesses, uniq virtual addresses}
std::unordered_map<int, int> blk2dramfreq;
std::unordered_map<int, int> blk2cxlfreq;
map<unsigned long, int> ip2blkCache;
map<unsigned long, int> mem2blkCache;

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

void printBlocksInfo()
{
    cout << "Printing blocks info ..." << endl;
    cout << "Block, Start, End, Size" << endl;
    for(auto block: blocks) {
        cout << block->id << ", "
            << hex 
            << "0x" << block->start << ", "
            << "0x" << block->end << ", "
            << dec
            << block->size << endl;
    }
    cout << "Printing blocks info done." << endl;
}

void readBinAnalysis(string fileName) {
    std::ifstream file(fileName);
    if (!file.is_open()) {
        std::cerr << "Failed to open the file." << std::endl;
        return;
    }

    std::string line;
    int i = 0;
    while (std::getline(file, line)) {
        i++;

        std::istringstream iss(line);
        
        std::string col1, col2, col3, col4, col5, col6, col7;
        
        iss >> col1 >> col2 >> col3 >> col4 >> col5 >> col6 >> col7;

        if(ip2funcaddr.count(col1) > 0) {
            std::cout << " IP : " << col1 << " Exists in map "  << std::endl;
        }

        ip2funcaddr[col1] = col6;
    }
        cout << "Number of ip funcaddrs recorded " << ip2funcaddr.size() << " Read Lines : "<< i << endl;
        i = 0;
        for(auto& kv : ip2funcaddr) {
            std::cout << " Key " << kv.first << "" << "Value " << kv.second << std::endl;
            if (i == 10) break;
            i++;
        }
    file.close();
}

void readTrace(string fileName)
{
    cout << "Reading trace file ..." << endl;
    string ip, ldstr, addr, cpu, time, sampleID, dsoID, freq, per;

    unsigned long i = 0;

    ifstream traceFile(fileName);
    //<IP> <Addrs> <CPU> <time> <sampleID> <DSO_id>
    jumpToLine(traceFile, 5);
    while (traceFile >> ip >> ldstr >> addr >> cpu >> time >> sampleID >> dsoID)
    {
        //std::cout << "ip : " << ip << std::endl;
        if(addr.size() >= 19) continue;

        trace.push_back(
            new AccessTime(
                stoul(ip, NULL, 16),
                stoull(addr, NULL, 16),
                stoi(cpu),
                stoull(time, NULL, 10),
                i
            )
        );

        i++;
    }
    cout << "Number of traces read: " << trace.size() << endl;
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

void generateIPGraph()
{
    cout << "Graph Variant: IP Graph" << endl;
    cout << "Generating graph ..." << endl;
    Graph g(blocks.size());
    int prevBlockId = getBlockId(trace[0]->ip);
    for(auto t: trace)
    {
        int blockId = getBlockId(t->ip);
        if (prevBlockId != blockId)
            g.addEdge(prevBlockId, blockId);
        prevBlockId = blockId;
    }
    g.print();
}


void generateMemGraph()
{
    cout << "Graph Variant: Mem Graph" << endl;
    cout << "Generating graph ..." << endl;
    Graph g(blocks.size()+7);
    int prevBlockId = getBlockId(trace[0]->ip);
    int prevAddr = trace[0]->addr;
    for(auto t: trace)
    {
        int blockId = getBlockId(t->ip);
        int addr = t->addr;
        if(blockId != -1 && prevBlockId != -1) {
            if (prevBlockId != blockId && prevAddr != addr)
                g.addEdge(prevBlockId, blockId);
            prevBlockId = blockId;
            prevAddr = addr;

        }
    }
    g.print();
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
            
            //blk2freq[blockId]++;
            auto it = blk2freq.find(blockId);
            if (it != blk2freq.end()) {
                // Block ID exists, update frequency and add address
                it->second.first++; // Increment frequency counter
                it->second.second.insert(addr); // Add virtual address to the set
            } else {
                // Block ID doesn't exist, create a new entry
                blk2freq[blockId] = {1, {addr}}; // Initialize frequency to 1 and add address
            }            
            if ((blockId != -1 && prevBlockId != -1) && prevBlockId != blockId && (prevIP != ip || prevAddr != addr)) {
                g.addEdge(prevBlockId, blockId);
            }
            prevBlockId = blockId;
            prevAddr = addr;
        }
    }
    g.print();

    for(auto& ele : blk2freq) {
        std::cout << "BlockID: " << ele.first << " Freq: " << ele.second.first << " UniqCounts: " << ele.second.second.size() << std::endl;
    }

    for(auto& cle : blk2cxlfreq) {
        std::cout << " CXL_BLK_ID : " << cle.first << " Freq : " << cle.second << std::endl;
    }
    
    for(auto& dle : blk2dramfreq) {
        std::cout << " DRAM_BLK_ID : " << dle.first << " Freq : " << dle.second << std::endl;
    }

}

int main(int argc, char** argv)
{
    if(argc != 4)
    {
        cout << "Invalid arguments!" << endl;
        cout << "Usage: ./cluster-anlys <tracefile> <blocksfile> <graph-variant>" << endl;
        cout << "graph-variant:" << endl;
        cout << "\t0 - All (default)" << endl;
        cout << "\t1 - IP Graph" << endl;
        cout << "\t2 - Mem Graph" << endl;
        cout << "\t3 - IP+Mem Graph" << endl;
        return 1;
    }

    char* traceFile = argv[1];
    char* blocksFile = argv[2];
    int graphVariant = atoi(argv[3]);
    //char* binanalysisFile = argv[4];
    
    readTrace(traceFile);
    readBlocks(blocksFile);

    switch(graphVariant) {
        case 1:
            generateIPGraph();
            break;
        case 2:
            generateMemGraph();
            break;
        case 3:
            generateIPMemGraph();
            break;
        case 0:
        default:
            cout << "Generating all graph variants" << endl;
            generateIPGraph();
            generateMemGraph();
            generateIPMemGraph();
    }
    return 0;
}
