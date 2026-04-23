CC=g++
CFLAGS= -g -std=c++17
LDFLAGS= -Irapidjson/include/rapidjson

all: gen-trace-graph footprint dump-block-mapping

gen-trace-graph: main.cpp AccessTime.hpp Block.hpp Graph.hpp
	$(CC) $(CFLAGS) -o $@  $< $(LDFLAGS)


footprint: footprint.cpp AccessTime.hpp Block.hpp Graph.hpp
	$(CC) $(CFLAGS) -o $@  $< $(LDFLAGS)

dump-block-mapping: per_block_access.cpp AccessTime.hpp Block.hpp Graph.hpp
	$(CC) $(CFLAGS) -o $@  $< $(LDFLAGS)

clean:
	rm -rf gen-trace-graph footprint dump-block-mapping

.PHONY: clean
