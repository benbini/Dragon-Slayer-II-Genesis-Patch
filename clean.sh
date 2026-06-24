#!/bin/bash

rm text/script_*.txt
rm text/atlas_index.txt
rm text/atlas_pc.txt
rm text/atlas_ptrtable.txt
rm text/strings.txt
cp .textfiles/* text/
rm -rf insert
rm -rf logs
rm -rf binary
rm *.bin
