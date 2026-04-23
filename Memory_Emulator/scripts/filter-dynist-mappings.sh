#!/bin/bash

set -e

logfile=$1
outfile=$2

startline=$(expr $(grep -n 'Start Writing to a file' $logfile | cut -f1 -d: | sed 's/$/ + 1/'))

endline=$(expr $(grep -n 'Wrote to a file named' $logfile | cut -f1 -d: | sed 's/$/ - 1/'))

sed -n "$startline,$endline p" $logfile > $outfile
