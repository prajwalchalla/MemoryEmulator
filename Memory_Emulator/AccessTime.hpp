#pragma once

#include <string>

class AccessTime
{
public:
    unsigned long ip;
    unsigned long long addr;
    int cpu;
    long double time;
    unsigned long freq;

    AccessTime(
        unsigned long _ip,
        unsigned long long _addr,
        int _cpu,
        unsigned long _time,
        int _freq
    )
    {
        ip = _ip;
        addr = _addr;
        cpu = _cpu;
        time = _time;
        freq = _freq;
    }
};
