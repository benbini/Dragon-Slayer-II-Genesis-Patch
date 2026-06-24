#!/bin/bash
TARGET_ROM=modded_dslayer2_work.bin
cp binary/* insert/
python3 Atlas/AtlasMain.py $TARGET_ROM text/script_init.txt

for script in text/script_??.txt
#for script in text/script_2E.txt
do
    script_name=$(echo -n "$script" | cut -d"/" -f2)
    if [ -f script_inserts/$script_name ]
    then
	echo "Copying new script $script_name into text/"
	cp script_inserts/$script_name text/
    fi
    python3 Atlas/AtlasMain.py $TARGET_ROM $script > logs/$script_name.log
done
echo "inserted text to $TARGET_ROM"
