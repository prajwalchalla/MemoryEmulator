#pragma once

#include <vector>
#include <algorithm>

class Block
{
public:
    int id;
    unsigned long start;
    unsigned long end;
    unsigned long size;

    bool contains(unsigned long _ip) {
        return start<=_ip && _ip<=end;
    }

    Block(
        int _id,
        unsigned long _start,
        unsigned long _end
    ) {
        id = _id;
        start = _start;
        end = _end;
        size = _end - _start;
    }
};