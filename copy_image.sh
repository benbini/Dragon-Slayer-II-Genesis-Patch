#!/bin/bash
SOURCE_ROM=dslayer2_work.bin
TARGET_ROM=modded_$SOURCE_ROM
cp $SOURCE_ROM $TARGET_ROM
python3 atlas/AtlasMain.py $TARGET_ROM text/rom_expand.txt
