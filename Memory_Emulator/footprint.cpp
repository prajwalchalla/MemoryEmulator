#include <iostream>
#include <fstream>
#include <sstream>
#include <map>
#include <vector>
#include <string>
#include <stdexcept>
#include <filesystem>

// Include the RapidJSON headers
#include "rapidjson/include/rapidjson/document.h"
#include "rapidjson/include/rapidjson/istreamwrapper.h"
#include "rapidjson/include/rapidjson/error/en.h"

#include "AccessTime.hpp"
#include "Block.hpp"
#include "Graph.hpp"

using namespace std;

vector<AccessTime*> trace;
vector<Block*> blocks; // basic blocks
std::map<unsigned long, int> ip2blkCache;
std::map<int, int> nodeToCluster;
std::unordered_map<int, vector<long double>> blk2timestamps;


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

void readTrace(string fileName)
{
    cout << "Reading trace file ..." << endl;
    string ip, ldstr, addr, cpu, time, sampleID, dsoID, freq, per;

    unsigned long i = 0;

    ifstream traceFile(fileName);
    //<IP> <Addrs> <CPU> <time> <sampleID> <DSO_id>
    jumpToLine(traceFile, 4);
    while (traceFile >> ip >> ldstr >> addr >> cpu >> time >> sampleID >> dsoID)
    {
        trace.push_back(
            new AccessTime(
                stoul(ip, NULL, 16),
                stoull(addr, NULL, 16),
                stoi(cpu),
                stold(time),
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

// Function to load clusters_nodes.txt
void loadClusters(const std::string& clustersFile) {
    std::ifstream file(clustersFile);
    if (!file.is_open()) {
        throw std::runtime_error("Unable to open clusters file.");
    }
    std::string line;
    while (std::getline(file, line)) {
        // Find positions of ":" and ","
        size_t blockPos = line.find("BlockId :");
        size_t clusterPos = line.find("ClusterID :");

        if (blockPos == std::string::npos || clusterPos == std::string::npos) {
            std::cerr << "Error: Malformed data in line: " << line << std::endl;
            continue;
        }

        try {
            // Extract BlockId and ClusterID values by parsing substrings
            int blockId = std::stoi(line.substr(blockPos + 10, line.find(",", blockPos) - (blockPos + 10)));
            int clusterId = std::stoi(line.substr(clusterPos + 12));

            nodeToCluster[(blockId)] = (clusterId);
        } catch (const std::exception& ex) {
            std::cerr << "Error: Failed to parse numeric values in line: " << line << " (" << ex.what() << ")" << std::endl;
            continue;
        }
    }
    file.close();

    for(auto& ele : nodeToCluster) {
        std::cout << "BlkID : " << ele.first << " clusterID : " << ele.second << std::endl;
    }
}

void getblocktimestamps()
{
    for(auto t: trace) {
        unsigned long ip = t->ip;
        int blockId = getBlockId(t->ip);
        if(blockId != -1) {
           blk2timestamps[blockId].push_back(t->time); 
        }
    }
}

// Function to generate plot data
void generatePlotData(const std::string& outputFolder) {
    for (const auto& [blockId, timestamps] : blk2timestamps) {
        if (nodeToCluster.count(blockId) > 0 && !timestamps.empty()) {
            std::ofstream outFile(outputFolder + "/block_" + to_string(blockId) + "_accesses.txt");
            if (!outFile.is_open()) {
                throw std::runtime_error("Unable to create output plot file.");
            }
            
            outFile << std::fixed << std::setprecision(15);

            for (size_t i = 0; i < timestamps.size(); ++i) {
                outFile << i << " " << timestamps[i] << "\n";
            }

            outFile.close();
            std::cout << "Access pattern saved for Block ID " << to_string(blockId) << " to '"
                      << outputFolder + "/block_" + to_string(blockId) + "_accesses.txt" << "'\n";
        }
    }
}

// Main function
int main(int argc, char* argv[]) {
    if (argc != 5) {
        std::cerr << "Usage: " << argv[0]
                  << " <topk_clusters.txt> <block_freq_mapping.txt> <trace.txt> <blocks.json>\n";
        return 1;
    }

    // Input file arguments
    std::string clustersFile = argv[1];
    std::string freq_mapping = argv[2];
    std::string traceFile = argv[3];
    std::string blocksFile = argv[4];
    std::string outputFolder = "/home/chal962/cluster-anlys/sw4lite/plots"; // Folder for plot data files

    try {
        // Step 1: Load trace and JSON blocks data
        readTrace(traceFile);
        readBlocks(blocksFile);

        // Step 2: Load clusters_nodes.txt data
        loadClusters(clustersFile);

        // Step 3: Parse the trace file and compute block accesses
        getblocktimestamps();

        // Step 4: Generate plot data for block accesses
        // generatePlotData(outputFolder);

    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
