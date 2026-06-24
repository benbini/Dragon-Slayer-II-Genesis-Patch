#!/bin/bash

mkdir binary
mkdir insert
mkdir logs
ROM_MD5=4c1a1583bd29071300fd1488aa7d0cc1
SOURCE_ROM=$(openssl dgst -md5 ref/* | grep $ROM_MD5 | sed -E 's/MD5\((.+)\).+$/\1/g')
TARGET_ROM=dslayer2_work.bin
if [ -z "$SOURCE_ROM" ]
then
    echo "Could not find ROM (MD5 $ROM_MD5) in ref/"
    exit
fi
cp "$SOURCE_ROM" "$TARGET_ROM"
./slayer2_dumper.py dump-file $TARGET_ROM $@
./slayer2_dumper.py dump-strings $TARGET_ROM $@
