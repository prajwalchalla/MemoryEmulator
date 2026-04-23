#pragma once

#include <algorithm>
#include <iostream>
#include <vector>

using namespace std;

class Graph
{
    vector<vector<pair<int,int>>> adjList; // [ (vertex, weight) ]
public:

    Graph(int n)
    {
        adjList.resize(n);
    }

    void addEdge(int src, int dest)
    {
        auto it = find_if
        (
            adjList[src].begin(), adjList[src].end(), 
            [dest](pair<int, int> p) { return p.first == dest; }
        );
        if (it != adjList[src].end()) {
            (*it).second++; // update edge weight
        }
        else {
            //std::cout << "Adding 1 weight from " << src << " to " << dest << std::endl;
            adjList[src].push_back(make_pair(dest, 1));
        }
    }

    void printEdgeInformation(int src)
    {
        if (src < 0 || src >= adjList.size()) {
            std::cout << "Invalid source vertex." << std::endl;
            return;
        }

        std::cout << "Edges from vertex " << src << " -> ";
        for (auto &edge : adjList[src])
        {
            std::cout << "{" << edge.first << "," << edge.second << "} ";
        }
        std::cout << std::endl;
    }

    void print()
    {
        int i = 0;
        for(auto v: adjList)
        {
            cout << i++ << " -> ";
            for(auto p: v)
            {
                cout << "{" << p.first << "," << p.second << "} ";
            }
            cout << endl;
        }
    }
};
