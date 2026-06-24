#!/bin/bash

./dump_text.sh

./copy_image.sh

./insert_text.sh

#./insert_binary.sh

python3 insert_asm.py modded_dslayer2_work.bin ref/asm1.bin ref/asm2.bin
