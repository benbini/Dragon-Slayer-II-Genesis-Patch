#!/bin/bash
ROM=modded_dslayer2_work.bin
python3 slayer2_dumper.py insert-file $ROM 0-57 -o finalmod_$ROM
echo "inserted to finalmod_$ROM"
